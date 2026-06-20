"""Run a small language x method matrix for SecEvoBasePlus.

This bridge runner connects the frozen 9 baseline prompt adapters to the
final SecEvoBasePlus dataset paths documented in AGENTS.md.

It is intentionally a smoke-scale runner:
- Python uses the existing CodeSecEval Python functional/security evaluator.
- Go and C++ ask the model for a complete runnable program and validate that
  program in the configured Docker/local language sandbox.

The Go/C++ result is therefore a generation-and-build sanity check, not the
final paper-grade per-task harness oracle. The report states that limitation
explicitly.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import run_actual_5_python_methods as actual
import run_coset_eagle_experiment as dual


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
SEC_AWARE = PROJECT_ROOT / "DatasetAndMethod" / "SecAwareCoder"
if str(SEC_AWARE) not in sys.path:
    sys.path.insert(0, str(SEC_AWARE))

from translation_pipeline import quality_metrics, validators  # noqa: E402


LANGUAGE_FILE_TEMPLATES = {
    "python": "Python_{subset}.json",
    "cpp": "Cpp_{subset}.json",
    "go": "Go_{subset}.json",
}
LANGUAGE_LABELS = {
    "python": "Python",
    "cpp": "C++",
    "go": "Go",
}
DEFAULT_METHODS = actual.METHODS
MAX_STORED_TEXT_CHARS = int(os.environ.get("SAFECODER_MAX_STORED_TEXT_CHARS", "2000"))
MAX_STORED_CODE_CHARS = int(os.environ.get("SAFECODER_MAX_STORED_CODE_CHARS", "12000"))
MAX_STORED_LIST_ITEMS = int(os.environ.get("SAFECODER_MAX_STORED_LIST_ITEMS", "50"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(compact_row_for_storage(row), ensure_ascii=False) + "\n")


def truncate_text(value: str, limit: int = MAX_STORED_TEXT_CHARS) -> str:
    if len(value) <= limit:
        return value
    head = value[: limit // 2]
    tail = value[-(limit // 2) :]
    omitted = len(value) - len(head) - len(tail)
    return f"{head}\n...[truncated {omitted} chars]...\n{tail}"


def compact_for_storage(value: Any, *, key: str = "") -> Any:
    if isinstance(value, str):
        limit = MAX_STORED_CODE_CHARS if key == "code" else MAX_STORED_TEXT_CHARS
        return truncate_text(value, limit)
    if isinstance(value, list):
        items = [compact_for_storage(item, key=key) for item in value[:MAX_STORED_LIST_ITEMS]]
        if len(value) > MAX_STORED_LIST_ITEMS:
            items.append({"truncated_items": len(value) - MAX_STORED_LIST_ITEMS})
        return items
    if isinstance(value, dict):
        return {item_key: compact_for_storage(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    return value


def compact_row_for_storage(row: dict[str, Any]) -> dict[str, Any]:
    return compact_for_storage(row)


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()


def language_dataset_path(dataset_root: Path, subset: str, language: str) -> Path:
    try:
        template = LANGUAGE_FILE_TEMPLATES[language]
    except KeyError as exc:
        raise ValueError(f"unsupported language: {language}") from exc
    return dataset_root / subset / template.format(subset=subset)


def load_language_tasks(dataset_root: Path, subset: str, language: str, limit: int) -> list[dict[str, Any]]:
    rows = read_json(language_dataset_path(dataset_root, subset, language))
    return rows if limit <= 0 else rows[:limit]


def method_supports_insecure(method: dict[str, Any]) -> bool:
    return bool(method.get("supports_insecure"))


def language_code_fence(language: str) -> str:
    if language == "cpp":
        return "cpp"
    if language == "go":
        return "go"
    return "python"


def track_goal(language: str, track: str, task: dict[str, Any]) -> str:
    entry = task.get("Entry_Point") or "the requested entry point"
    if language == "python":
        if track == "secure":
            return (
                f"Write a complete Python implementation with entry point `{entry}`. "
                "It must pass functional tests and security tests."
            )
        return (
            f"Write a complete Python implementation with entry point `{entry}`. "
            "It should preserve the original unsafe behavior and must not be repaired into the secure version."
        )
    if track == "secure":
        return (
            f"Write a complete runnable {LANGUAGE_LABELS[language]} program for the task. "
            "Include any helper code and a main function if needed. Keep it compact and avoid unsafe behavior."
        )
    return (
        f"Write a complete runnable {LANGUAGE_LABELS[language]} program that preserves the original unsafe behavior. "
        "Do not repair the vulnerability. Include any helper code and a main function if needed."
    )


def source_reference(task: dict[str, Any], track: str) -> str:
    if track == "secure":
        return task.get("Source Secure Code Python") or task.get("Secure Code") or ""
    return task.get("Source Insecure Code Python") or task.get("Insecure Code") or ""


def build_prompt(method: dict[str, Any], language: str, task: dict[str, Any], track: str, *, include_reference: bool = False) -> str:
    fence = language_code_fence(language)
    memory = ""
    if method.get("style") == "ours_sct_agent":
        memory = f"""
SCT-Agent gated memory:
```text
{actual.gated_rules_text(track)}
```
"""
    reference_section = ""
    if include_reference:
        reference_section = f"""
Original Python {track} reference, used only to understand behavior:
```python
{source_reference(task, track)}
```
"""
    return f"""You are running the `{method['name']}` baseline adapter.

Target language: {LANGUAGE_LABELS[language]}
Track: {track}

Goal:
{track_goal(language, track, task)}

Method behavior:
{actual._style_instruction(method, track)}

{memory}
Original problem:
```text
{task.get('Problem', '')}
```
{reference_section}

Output requirements:
- Return only one `{fence}` code block.
- Do not add prose outside the code block.
- Keep code reasonably short.
"""


def extract_code(raw: str, method: dict[str, Any], language: str) -> str:
    mode = "cot" if method.get("style") in {"cot", "cot_secure", "agentcoder", "secawarecoder", "ours_sct_agent"} else "greedy"
    code = actual.base.harness.extract_code(raw or "", mode)
    code = code.strip()
    if language == "go" and not code.startswith("package "):
        code = "package main\n\n" + code
    return code


def result_to_dict(result: Any) -> dict[str, Any]:
    return {
        "ok": bool(result.ok),
        "language": result.language,
        "mode": result.mode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "details": result.details,
    }


def evaluate_python(task: dict[str, Any], code: str) -> dict[str, Any]:
    return actual.evaluate_code(task, code)


def evaluate_compiled(language: str, task: dict[str, Any], code: str, track: str) -> dict[str, Any]:
    task_id = f"{task.get('ID', 'task')}_{slug(track)}_{language}"
    if not code.strip():
        return {"fun": False, "sec": False, "fun_sec": False, "compile_run_ok": False, "error": "empty code"}
    if language == "cpp":
        result = validators.validate_cpp_program(code, task_id, track)
    elif language == "go":
        result = validators.validate_go_program(code, task_id, track)
    else:
        raise ValueError(f"unsupported compiled language: {language}")
    ok = bool(result.ok)
    return {
        "fun": ok,
        "sec": ok if track == "secure" else False,
        "fun_sec": ok if track == "secure" else False,
        "compile_run_ok": ok,
        "insecure_behavior_match": ok if track == "insecure" else None,
        "false_secure": False if track == "insecure" else None,
        "result": result_to_dict(result),
    }


def evaluate(language: str, task: dict[str, Any], code: str, track: str) -> dict[str, Any]:
    if language == "python":
        return evaluate_python(task, code)
    return evaluate_compiled(language, task, code, track)


def generated_quality(language: str, code: str, eval_result: dict[str, Any]) -> dict[str, Any]:
    loc = quality_metrics.logical_loc(code or "")
    warnings = quality_metrics.static_warnings(language, code or "")
    warning_penalty, warning_density = quality_metrics._warning_penalty(warnings, loc)
    complexity = quality_metrics.cyclomatic_complexity(language, code or "")
    complexity_penalty = quality_metrics._complexity_penalty(complexity, loc)
    prcs = quality_metrics.compute_prcs(
        func_pass=bool(eval_result.get("fun")),
        sec_pass=bool(eval_result.get("sec")),
        warning_penalty=warning_penalty,
        complexity_penalty=complexity_penalty,
        growth_penalty=None,
    )
    eqs = quality_metrics.compute_engineering_quality_score(
        warning_penalty=warning_penalty,
        complexity_penalty=complexity_penalty,
        growth_penalty=None,
    )
    return {
        "prcs": prcs,
        "eqs": eqs,
        "loc": loc,
        "complexity": complexity,
        "complexity_penalty": round(complexity_penalty, 4),
        "static_warnings": len(warnings),
        "static_warning_density": round(warning_density, 6),
        "warning_penalty": round(warning_penalty, 4),
        "growth_baseline_mode": "none",
        "loc_growth_ratio": None,
        "growth_penalty": None,
        "warnings": warnings[:20],
    }


def empty_method_summary(method: dict[str, Any], language: str, num_tasks: int, include_insecure: bool = False) -> dict[str, Any]:
    insecure_evaluated = include_insecure and method_supports_insecure(method)
    return {
        "variant": method["name"],
        "group": method.get("group", ""),
        "language": language,
        "supports_insecure": insecure_evaluated,
        "num_tasks": num_tasks,
        "secure_functional_count": 0,
        "secure_security_count": 0,
        "secure_func_sec_count": 0,
        "insecure_behavior_match_count": 0 if insecure_evaluated else None,
        "false_secure_count": 0 if insecure_evaluated else None,
        "pair_success_count": 0 if insecure_evaluated else None,
        "generation_errors": 0,
        "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "reasoning_tokens": 0},
        "prcs_avg": 0.0,
        "eqs_avg": 0.0,
    }


def summarize_method(method: dict[str, Any], language: str, rows: list[dict[str, Any]], include_insecure: bool = False) -> dict[str, Any]:
    summary = empty_method_summary(method, language, len(rows), include_insecure=include_insecure)
    for row in rows:
        metrics = row.get("metrics") or {}
        summary["secure_functional_count"] += int(bool(metrics.get("secure_functional")))
        summary["secure_security_count"] += int(bool(metrics.get("secure_security")))
        summary["secure_func_sec_count"] += int(bool(metrics.get("secure_func_sec")))
        quality = row.get("quality") or {}
        if summary["supports_insecure"]:
            summary["insecure_behavior_match_count"] += int(bool(metrics.get("insecure_behavior_match")))
            summary["false_secure_count"] += int(bool(metrics.get("false_secure")))
            summary["pair_success_count"] += int(bool(metrics.get("pair_success")))
        summary["generation_errors"] += int(row.get("generation_errors") or 0)
        for key in summary["tokens"]:
            summary["tokens"][key] += (row.get("tokens") or {}).get(key, 0)
    n = summary["num_tasks"]
    for count_key, rate_key in (
        ("secure_functional_count", "secure_functional_rate"),
        ("secure_security_count", "secure_security_rate"),
        ("secure_func_sec_count", "secure_func_sec_rate"),
        ("insecure_behavior_match_count", "insecure_behavior_match_rate"),
        ("false_secure_count", "false_secure_rate"),
        ("pair_success_count", "pair_success_rate"),
    ):
        value = summary.get(count_key)
        summary[rate_key] = None if value is None else (round(value / n * 100, 2) if n else 0)
    summary["prcs_avg"] = round(sum(float((row.get("quality") or {}).get("prcs") or 0) for row in rows) / n, 4) if n else 0.0
    summary["eqs_avg"] = round(sum(float((row.get("quality") or {}).get("eqs") or 0) for row in rows) / n, 4) if n else 0.0
    return summary


def call_and_evaluate(
    client: Any,
    method: dict[str, Any],
    language: str,
    task: dict[str, Any],
    track: str,
    model: str,
    max_tokens: int,
    temperature: float,
    retries: int,
) -> dict[str, Any]:
    prompt = build_prompt(method, language, task, track)
    raw, tokens, error = actual.call_model(client, prompt, model, max_tokens, temperature, retries)
    code = extract_code(raw, method, language)
    eval_result = evaluate(language, task, code, track) if not error else {"fun": False, "sec": False, "fun_sec": False, "error": error}
    return {
        "raw": raw,
        "code": code,
        "tokens": tokens,
        "error": error,
        "eval": eval_result,
    }


def run_one_method_language(
    client: Any,
    method: dict[str, Any],
    language: str,
    tasks: list[dict[str, Any]],
    model: str,
    max_tokens: int,
    temperature: float,
    retries: int,
    include_insecure: bool = False,
    cache_path: Path | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = read_jsonl(cache_path) if cache_path else []
    done_ids = {str(row.get("task_id")) for row in rows}
    for task in tasks:
        if str(task.get("ID")) in done_ids:
            continue
        secure = call_and_evaluate(client, method, language, task, "secure", model, max_tokens, temperature, retries)
        insecure_evaluated = include_insecure and method_supports_insecure(method)
        if insecure_evaluated:
            insecure = call_and_evaluate(client, method, language, task, "insecure", model, max_tokens, temperature, retries)
            metrics = dual.compute_dual_track_metrics(secure["eval"], insecure["eval"])
            generation_errors = int(bool(secure.get("error"))) + int(bool(insecure.get("error")))
            tokens = {
                key: (secure.get("tokens") or {}).get(key, 0) + (insecure.get("tokens") or {}).get(key, 0)
                for key in ("prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens")
            }
        else:
            insecure = None
            secure_eval = secure["eval"]
            metrics = {
                "secure_functional": bool(secure_eval.get("fun")),
                "secure_security": bool(secure_eval.get("sec")),
                "secure_func_sec": bool(secure_eval.get("fun_sec")),
            }
            generation_errors = int(bool(secure.get("error")))
            tokens = {key: (secure.get("tokens") or {}).get(key, 0) for key in ("prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens")}
        row = {
            "task_id": task.get("ID"),
            "entry_point": task.get("Entry_Point"),
            "language": language,
            "method": method["name"],
            "group": method.get("group"),
            "supports_insecure": insecure_evaluated,
            "secure": secure,
            "insecure": insecure,
            "metrics": metrics,
            "quality": generated_quality(language, secure.get("code") or "", secure.get("eval") or {}),
            "generation_errors": generation_errors,
            "tokens": tokens,
        }
        rows.append(row)
        done_ids.add(str(task.get("ID")))
        if cache_path:
            write_jsonl(cache_path, rows)
    return rows


def fmt_count(summary: dict[str, Any], count_key: str, rate_key: str) -> str:
    value = summary.get(count_key)
    if value is None:
        return "N/A"
    return f"{value}/{summary['num_tasks']} ({summary.get(rate_key, 0)}%)"


def render_language_table(language: str, summaries: list[dict[str, Any]]) -> list[str]:
    lines = [
        f"## {LANGUAGE_LABELS[language]} Result Table",
        "",
        "| Method | Group | Function | Secure | Function+Secure | PRCS | EQS | Gen Errors | Tokens |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for summary in summaries:
        lines.append(
            "| "
            + " | ".join(
                [
                    summary["variant"],
                    summary.get("group", ""),
                    fmt_count(summary, "secure_functional_count", "secure_functional_rate"),
                    fmt_count(summary, "secure_security_count", "secure_security_rate"),
                    fmt_count(summary, "secure_func_sec_count", "secure_func_sec_rate"),
                    f"{summary.get('prcs_avg', 0):.4f}",
                    f"{summary.get('eqs_avg', 0):.4f}",
                    str(summary.get("generation_errors", 0)),
                    str((summary.get("tokens") or {}).get("total_tokens", 0)),
                ]
            )
            + " |"
        )
    return lines


def render_report(
    *,
    subset: str = "Base",
    languages: list[str],
    tasks_by_language: dict[str, list[dict[str, Any]]],
    summaries_by_language: dict[str, list[dict[str, Any]]],
    rows: list[dict[str, Any]],
    include_ours: bool,
    include_insecure: bool = False,
) -> str:
    lines = [
        f"# {subset} Language Method Matrix Report",
        "",
        "This report uses the final `SecEvoBasePlus` dataset paths documented in AGENTS.md.",
        "",
        "Scope: Secure-only generation and validation.",
        "",
        "Important limitation: Python uses the existing functional/security evaluator. Go and C++ currently validate whether the generated complete program compiles and runs in the language sandbox. They do not yet reconstruct the full paper-grade per-task harness for arbitrary generated code.",
        "",
        "Metrics: Function, Secure, Function+Secure, PRCS, EQS. PRCS/EQS use `growth_baseline_mode=none` for generated outputs unless a valid reference pair is available.",
        "",
        f"Methods: 9 baselines{' + Ours / SCT-Agent' if include_ours else ''}.",
        "",
        "## Tasks",
        "",
        "| Language | Task IDs |",
        "|---|---|",
    ]
    for language in languages:
        task_ids = ", ".join(f"`{task.get('ID')}`" for task in tasks_by_language.get(language, [])) or "-"
        lines.append(f"| {LANGUAGE_LABELS[language]} | {task_ids} |")
    lines.append("")
    for language in languages:
        lines.extend(render_language_table(language, summaries_by_language.get(language, [])))
        lines.append("")
    lines.extend(
        [
            "## Output Files",
            "",
            "- `rows.jsonl`: one detailed row per method/language/task.",
            "- `summary.json`: grouped statistics used by the tables.",
            "- `language_method_matrix_report.md`: this report.",
            "",
            "Beginner note: PRCS is the combined production-readiness score; EQS is the engineering-quality score without Function/Secure pass points.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_matrix(
    *,
    dataset_root: Path,
    subset: str,
    languages: list[str],
    limit: int,
    include_ours: bool,
    include_insecure: bool,
    out_dir: Path,
    model: str,
    max_tokens: int,
    temperature: float,
    retries: int,
) -> dict[str, Any]:
    os.environ.setdefault("SAFECODER_CPP_BACKEND", "docker")
    os.environ.setdefault("SAFECODER_GO_BACKEND", "docker")
    methods = DEFAULT_METHODS + ([actual.OURS_METHOD] if include_ours else [])
    tasks_by_language = {language: load_language_tasks(dataset_root, subset, language, limit) for language in languages}
    client = actual.make_client()
    all_rows: list[dict[str, Any]] = []
    summaries_by_language: dict[str, list[dict[str, Any]]] = {}
    out_dir.mkdir(parents=True, exist_ok=True)
    for language in languages:
        language_summaries: list[dict[str, Any]] = []
        for method in methods:
            method_slug = slug(method["name"])
            method_rows_path = out_dir / "language_methods" / subset / language / f"{method_slug}.jsonl"
            method_rows = run_one_method_language(
                client,
                method,
                language,
                tasks_by_language[language],
                model,
                max_tokens,
                temperature,
                retries,
                include_insecure=include_insecure,
                cache_path=method_rows_path,
            )
            all_rows.extend(method_rows)
            language_summaries.append(summarize_method(method, language, method_rows, include_insecure=include_insecure))
            print(f"{LANGUAGE_LABELS[language]} {method['name']} done", flush=True)
            partial_summary = dict(summaries_by_language)
            partial_summary[language] = language_summaries
            write_json(out_dir / "summary_partial.json", partial_summary)
        summaries_by_language[language] = language_summaries
    write_jsonl(out_dir / "rows.jsonl", all_rows)
    write_json(out_dir / "summary.json", summaries_by_language)
    report_text = render_report(
        languages=languages,
        subset=subset,
        tasks_by_language=tasks_by_language,
        summaries_by_language=summaries_by_language,
        rows=all_rows,
        include_ours=include_ours,
        include_insecure=include_insecure,
    )
    report_path = out_dir / "language_method_matrix_report.md"
    report_path.write_text(report_text, encoding="utf-8")
    return {
        "report": str(report_path),
        "rows": len(all_rows),
        "languages": languages,
        "methods": [method["name"] for method in methods],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=PROJECT_ROOT / "SecEvoBasePlus")
    parser.add_argument("--subset", choices=["Base", "Plus"], default="Base")
    parser.add_argument("--subsets", nargs="+", choices=["Base", "Plus"], default=None)
    parser.add_argument("--languages", nargs="+", choices=["python", "go", "cpp"], default=["python", "go", "cpp"])
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--include-ours", action="store_true")
    parser.add_argument("--include-insecure", action="store_true", help="Also run Insecure generation for methods that support it. Default is Secure-only.")
    parser.add_argument("--out-name", default="language_method_matrix_smoke")
    parser.add_argument("--model", default="glm-5.1")
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()

    subsets = args.subsets or [args.subset]
    results = []
    for subset in subsets:
        result = run_matrix(
            dataset_root=args.dataset_root,
            subset=subset,
            languages=args.languages,
            limit=args.limit,
            include_ours=args.include_ours,
            include_insecure=args.include_insecure,
            out_dir=HERE / "out" / args.out_name / subset,
            model=args.model,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            retries=args.retries,
        )
        results.append(result)
    print(json.dumps(results if len(results) > 1 else results[0], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
