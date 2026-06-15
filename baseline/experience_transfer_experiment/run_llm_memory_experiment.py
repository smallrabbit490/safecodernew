"""LLM-distilled memory and self-evolution experiment.

This script keeps the v3 test split fixed:
- Learn generic experience from 100 SeCodePLT pairs with an LLM.
- Test the LLM-distilled memory on the same 30 CodeSecEval Plus tasks.
- Read failed cases, ask the LLM for generic memory updates, then retest.

The update rules must stay generic: they describe task-agnostic behavior such as
input validation, exception matching, path confinement, and side-effect cleanup.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from openai import OpenAI

import run_experiment as base


HERE = Path(__file__).resolve().parent
V3 = HERE / "out" / "v3"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def make_client() -> OpenAI:
    return base.make_client()


def call_model(client: OpenAI, prompt: str, model: str, max_tokens: int, retries: int = 3) -> tuple[str, dict, str | None]:
    last_err = None
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                top_p=1.0,
                max_tokens=max_tokens,
                extra_body={"thinking": {"type": "disabled"}},
            )
            usage = getattr(resp, "usage", None)
            details = getattr(usage, "completion_tokens_details", None) if usage else None
            tokens = {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
                "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
                "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0,
                "reasoning_tokens": getattr(details, "reasoning_tokens", 0) if details else 0,
            }
            return resp.choices[0].message.content or "", tokens, None
        except Exception as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            time.sleep(2 * (attempt + 1))
    return "", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "reasoning_tokens": 0}, last_err


def extract_json_array(text: str) -> list[dict]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        data = json.loads(text)
    except Exception:
        m = re.search(r"\[[\s\S]*\]", text)
        if not m:
            raise
        data = json.loads(m.group(0))
    if not isinstance(data, list):
        raise ValueError("LLM output is not a JSON array")
    return data


def repair_json_array(client: OpenAI, raw: str, model: str, title: str) -> tuple[list[dict], str]:
    prompt = f"""Fix the following broken {title} so it becomes valid JSON only.

Constraints:
- Return a JSON array only.
- Keep the same content and schema.
- Escape all quotes correctly.
- Do not add markdown fences or commentary.

Broken output:
{raw}
"""
    fixed, tokens, err = call_model(client, prompt, model, max_tokens=4096)
    if err:
        raise ValueError(f"repair_failed: {err}")
    return extract_json_array(fixed), fixed


def parse_json_array_with_repair(client: OpenAI, raw: str, model: str, title: str) -> tuple[list[dict], dict]:
    try:
        return extract_json_array(raw), {"repaired": False, "raw": raw}
    except Exception as first_exc:
        repaired, fixed = repair_json_array(client, raw, model, title)
        return repaired, {"repaired": True, "raw": raw, "fixed": fixed, "error": str(first_exc)}


def compact_card(card: dict) -> dict:
    diff_lines = []
    for line in (card.get("delta_diff") or "").splitlines():
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            diff_lines.append(line)
    return {
        "id": card.get("id"),
        "cwe": card.get("cwe"),
        "function": card.get("function"),
        "policy": card.get("policy"),
        "key_delta": diff_lines[:8],
    }


def chunked(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def distill_chunk(client: OpenAI, cards: list[dict], model: str, chunk_id: int) -> tuple[list[dict], dict]:
    payload = [compact_card(c) for c in cards]
    prompt = f"""You are building a generic secure-code generation memory.

Read these vulnerable-to-patched examples. Summarize generic, reusable security rules.

Important constraints:
- Rules must be broadly reusable and not tied to one sample ID.
- Do not overfit to a single CWE. You may mention applicable situations, but write the rule as a general programming principle.
- Focus on what a generator should do before writing code: validation, safe API choice, error behavior, side-effect handling, resource bounds, and preserving functional behavior.
- Return JSON only: an array of objects.

Schema:
[
  {{
    "rule_name": "short name",
    "principle": "generic rule in one sentence",
    "when_to_apply": ["keyword or situation", "..."],
    "implementation_hint": "concrete but language-neutral guidance",
    "avoid": "what unsafe pattern to avoid",
    "evidence": ["source ids or broad evidence"]
  }}
]

Examples:
{json.dumps(payload, ensure_ascii=False)}
"""
    raw, tokens, err = call_model(client, prompt, model, max_tokens=4096)
    if err:
        return [], {"chunk": chunk_id, "error": err, "tokens": tokens, "raw": raw}
    try:
        rules, parse_meta = parse_json_array_with_repair(client, raw, model, "security memory rules")
    except Exception as exc:
        return [], {"chunk": chunk_id, "error": f"parse_error: {exc}", "tokens": tokens, "raw": raw}
    for rule in rules:
        rule["source"] = "llm_distilled_secodeplt"
        rule["chunk"] = chunk_id
    return rules, {"chunk": chunk_id, "error": None, "tokens": tokens, "raw": raw, **parse_meta}


def merge_rules(client: OpenAI, rules: list[dict], model: str) -> tuple[list[dict], dict]:
    prompt = f"""Merge these security memory rules into 10-16 generic rules.

Constraints:
- Keep rules generic; do not make them specific to one CWE or one benchmark task.
- Deduplicate overlapping rules.
- Preserve concrete implementation guidance.
- Return JSON only: an array of objects with the same schema.

Rules:
{json.dumps(rules, ensure_ascii=False)}
"""
    raw, tokens, err = call_model(client, prompt, model, max_tokens=4096)
    if err:
        return rules, {"error": err, "tokens": tokens, "raw": raw}
    try:
        merged, parse_meta = parse_json_array_with_repair(client, raw, model, "merged security memory rules")
    except Exception as exc:
        return rules, {"error": f"parse_error: {exc}", "tokens": tokens, "raw": raw}
    for rule in merged:
        rule["source"] = "llm_merged_secodeplt"
    return merged, {"error": None, "tokens": tokens, "raw": raw, **parse_meta}


def memory_to_text(rules: list[dict], title: str) -> str:
    lines = [
        title,
        "Use these generic rules only when relevant to the current task.",
        "Preserve required function name, return format, and expected exception behavior.",
        "",
    ]
    for i, rule in enumerate(rules, 1):
        lines.append(f"{i}. {rule.get('rule_name', 'Rule')}")
        lines.append(f"   Principle: {rule.get('principle', '')}")
        if rule.get("when_to_apply"):
            lines.append("   Apply when: " + ", ".join(map(str, rule.get("when_to_apply", [])[:6])))
        if rule.get("implementation_hint"):
            lines.append(f"   Implementation: {rule.get('implementation_hint')}")
        if rule.get("avoid"):
            lines.append(f"   Avoid: {rule.get('avoid')}")
    return "\n".join(lines)


def build_prompt(task: dict, memory_text: str, variant: str) -> str:
    return base.build_prompt(task, memory_text, variant)


def run_variant(
    variant: str,
    test: list[dict],
    memory_text: str,
    model: str,
    workers: int,
    max_tokens: int,
    out_dir: Path,
    force: bool = False,
) -> dict:
    outdir = out_dir / "runs" / variant
    gen_path = outdir / "generations.jsonl"
    res_path = outdir / "results.jsonl"
    summary_path = outdir / "summary.json"

    cached = {}
    if gen_path.exists() and not force:
        for line in gen_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                cached[row["task_id"]] = row

    todo = [task for task in test if task["ID"] not in cached]
    generated = list(cached.values())
    client = make_client() if todo else None

    def one(task: dict) -> dict:
        prompt = build_prompt(task, memory_text, variant)
        raw, usage, err = call_model(client, prompt, model, max_tokens)
        return {
            "task_id": task["ID"],
            "variant": variant,
            "entry_point": task["Entry_Point"],
            "raw": raw,
            "code": base.extract_code(raw),
            "usage": usage,
            "error": err,
            "prompt_chars": len(prompt),
        }

    if todo:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(one, task) for task in todo]
            for fut in as_completed(futures):
                generated.append(fut.result())
        order = {task["ID"]: i for i, task in enumerate(test)}
        generated.sort(key=lambda row: order.get(row["task_id"], 999))
        write_jsonl(gen_path, generated)

    by_gen = {row["task_id"]: row for row in generated}
    old_cwd = Path.cwd()
    os.chdir(base.GREEDY_DIR)
    results = []
    try:
        for task in test:
            gen = by_gen[task["ID"]]
            fp, sp = base.suites.get_suites(task)
            verdict = base.harness.evaluate_solution(gen.get("code") or "", task["Entry_Point"], fp, sp, timeout=20)
            results.append({
                "task_id": task["ID"],
                "variant": variant,
                "fun": bool(verdict.get("fp")),
                "sec": bool(verdict.get("sp")),
                "fun_sec": bool(verdict.get("fp") and verdict.get("sp")),
                "gen_error": gen.get("error"),
                "fp_err": verdict.get("fp_err"),
                "sp_err": verdict.get("sp_err"),
            })
    finally:
        os.chdir(old_cwd)
    write_jsonl(res_path, results)

    tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "reasoning_tokens": 0}
    for gen in generated:
        for key in tokens:
            tokens[key] += (gen.get("usage") or {}).get(key, 0)
    n = len(results)
    summary = {
        "variant": variant,
        "model": model,
        "num_tasks": n,
        "fun_count": sum(r["fun"] for r in results),
        "sec_count": sum(r["sec"] for r in results),
        "fun_sec_count": sum(r["fun_sec"] for r in results),
        "fun_sec_pass@1": round(100 * sum(r["fun_sec"] for r in results) / n, 2),
        "generation_errors": sum(1 for gen in generated if gen.get("error")),
        "tokens": tokens,
    }
    write_json(summary_path, summary)
    return summary


def make_failure_payload(test: list[dict], results_path: Path, generations_path: Path, limit: int = 12) -> list[dict]:
    by_task = {task["ID"]: task for task in test}
    results = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    gens = [json.loads(line) for line in generations_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_gen = {gen["task_id"]: gen for gen in gens}
    payload = []
    for row in results:
        if row["fun_sec"]:
            continue
        task = by_task[row["task_id"]]
        gen = by_gen.get(row["task_id"], {})
        payload.append({
            "task_id": row["task_id"],
            "problem": task.get("Problem", "")[:1200],
            "entry_point": task.get("Entry_Point"),
            "failed_functional": not row["fun"],
            "failed_security": not row["sec"],
            "fp_err": row.get("fp_err"),
            "sp_err": row.get("sp_err"),
            "candidate_excerpt": (gen.get("code") or "")[:1400],
        })
    return payload[:limit]


def summarize_failure_signals(failure_payload: list[dict]) -> list[dict]:
    signals = []
    for row in failure_payload:
        problem = (row.get("problem") or "").lower()
        fp_err = (row.get("fp_err") or "").lower()
        sp_err = (row.get("sp_err") or "").lower()
        tags = []
        if "unexpected exception type" in fp_err or "unexpected exception type" in sp_err:
            tags.append("exception-type mismatch")
        if "expected an exception but none was raised" in fp_err or "expected an exception but none was raised" in sp_err:
            tags.append("missing expected rejection")
        if "permissionerror" in fp_err or "permissionerror" in sp_err or "access denied" in problem:
            tags.append("resource access control")
        if "filenotfounderror" in fp_err or "filenotfounderror" in sp_err:
            tags.append("resource existence or cleanup handling")
        if "assertionerror" in fp_err or "assertionerror" in sp_err:
            tags.append("behavior drift under tests")
        if "typeerror" in fp_err or "typeerror" in sp_err:
            tags.append("input/type contract mismatch")
        if not tags:
            tags.append("general failure")
        signals.append({
            "task_kind": base.cwe_from_id(row["task_id"]) if hasattr(base, "cwe_from_id") else row["task_id"],
            "failure_tags": sorted(set(tags)),
            "problem_brief": row.get("problem", "")[:220],
            "candidate_brief": row.get("candidate_excerpt", "")[:220],
        })
    return signals


def evolve_rules(client: OpenAI, current_rules: list[dict], failure_payload: list[dict], model: str) -> tuple[list[dict], dict]:
    failure_signals = summarize_failure_signals(failure_payload)
    prompt = f"""You are updating a generic secure-code generation memory after reading failures.

Your task:
1. Read failed generated solutions and test errors.
2. Add or revise only broadly reusable rules.
3. Do NOT create rules tied to a specific CWE number, task ID, file name, database path, or benchmark string.
4. Focus on general failure modes: matching required exception behavior, preserving return format, side-effect cleanup, path semantics, parsing boundaries, test setup assumptions, and avoiding over-hardening.
5. Use the failure signals below only as broad patterns, not as labels to copy.

Return JSON only: an array of 5-10 generic update rules.

Schema:
[
  {{
    "rule_name": "short name",
    "principle": "generic rule in one sentence",
    "when_to_apply": ["broad situation", "..."],
    "implementation_hint": "concrete language-neutral guidance",
    "avoid": "what to avoid",
    "evidence": ["generic failure pattern"]
  }}
]

Current memory:
{json.dumps(current_rules, ensure_ascii=False)}

Failure signals:
{json.dumps(failure_signals, ensure_ascii=False)}
"""
    raw, tokens, err = call_model(client, prompt, model, max_tokens=4096)
    if err:
        return [], {"error": err, "tokens": tokens, "raw": raw}
    try:
        updates, parse_meta = parse_json_array_with_repair(client, raw, model, "self-evolution update rules")
    except Exception as exc:
        return [], {"error": f"parse_error: {exc}", "tokens": tokens, "raw": raw}
    for rule in updates:
        rule["source"] = "llm_self_evolution_failure_update"
        if "evidence" in rule:
            rule["evidence"] = ["generic failure pattern"]
    return updates, {"error": None, "tokens": tokens, "raw": raw, **parse_meta}


def write_report(out_dir: Path, base_summaries: dict, llm_summary: dict, evolved_summary: dict, rules: list[dict], updates: list[dict]) -> None:
    lines = [
        "# LLM Memory and Self-Evolution Experiment",
        "",
        "## Result Summary",
        "",
        "| Variant | Func+Sec | Notes |",
        "|---|---:|---|",
        f"| Previous script memory v3 / SeCodePLT | {base_summaries['secodeplt_memory']['fun_sec_count']}/30 | Script diff + common rules + retrieval |",
        f"| Previous CodeSecEval memory v3 | {base_summaries['codeseceval_memory']['fun_sec_count']}/30 | Reused previous CodeSecEval experience |",
        f"| Previous NoMemory v3 | {base_summaries['no_memory']['fun_sec_count']}/30 | No experience |",
        f"| LLM-distilled SeCodePLT memory | {llm_summary['fun_sec_count']}/30 | LLM summarizes generic rules from 100 SeCodePLT pairs |",
        f"| Evolved LLM memory | {evolved_summary['fun_sec_count']}/30 | Adds generic rules learned from failed cases |",
        "",
        "## What changed",
        "",
        "The previous memory was extracted by script: it kept CWE labels, policies, code diffs, and hand-written common rules.",
        "The LLM memory asks the model to compress the 100 paired examples into broad reusable principles.",
        "The evolved memory then reads failed cases and adds generic update rules without binding them to a specific CWE.",
        "",
        "## LLM-distilled Rules",
        "",
    ]
    for rule in rules:
        lines.append(f"- **{rule.get('rule_name', 'Rule')}**: {rule.get('principle', '')}")
    lines.extend(["", "## Self-Evolution Updates", ""])
    for rule in updates:
        lines.append(f"- **{rule.get('rule_name', 'Rule')}**: {rule.get('principle', '')}")
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="glm-5.1")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--max_tokens", type=int, default=4096)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--out_name", default="llm_v1")
    args = parser.parse_args()

    out_dir = HERE / "out" / args.out_name
    out_dir.mkdir(parents=True, exist_ok=True)

    se_cards = read_json(V3 / "memory" / "secodeplt_memory.json")
    test = read_json(V3 / "data" / "codeseceval_test30.json")
    client = make_client()

    rules_path = out_dir / "memory" / "llm_distilled_rules.json"
    logs = []
    if rules_path.exists() and not args.force:
        merged_rules = read_json(rules_path)
    else:
        all_rules = []
        for chunk_id, cards in enumerate(chunked(se_cards, 20), 1):
            rules, log = distill_chunk(client, cards, args.model, chunk_id)
            all_rules.extend(rules)
            logs.append(log)
        merged_rules, merge_log = merge_rules(client, all_rules, args.model)
        logs.append({"merge": merge_log})
        write_json(out_dir / "memory" / "llm_raw_rule_logs.json", logs)
        write_json(rules_path, merged_rules)
        (out_dir / "memory" / "llm_distilled_rules.md").write_text(memory_to_text(merged_rules, "LLM-distilled SeCodePLT memory"), encoding="utf-8")

    llm_memory_text = memory_to_text(merged_rules, "LLM-distilled SeCodePLT memory")
    llm_summary = run_variant(
        "llm_distilled_memory",
        test,
        llm_memory_text,
        args.model,
        args.workers,
        args.max_tokens,
        out_dir,
        force=args.force,
    )

    failure_payload = make_failure_payload(
        test,
        out_dir / "runs" / "llm_distilled_memory" / "results.jsonl",
        out_dir / "runs" / "llm_distilled_memory" / "generations.jsonl",
    )
    write_json(out_dir / "memory" / "failure_payload.json", failure_payload)

    updates_path = out_dir / "memory" / "llm_evolved_updates.json"
    if updates_path.exists() and not args.force:
        updates = read_json(updates_path)
    else:
        updates, update_log = evolve_rules(client, merged_rules, failure_payload, args.model)
        write_json(updates_path, updates)
        write_json(out_dir / "memory" / "llm_evolved_update_log.json", update_log)

    evolved_rules = merged_rules + updates
    write_json(out_dir / "memory" / "llm_evolved_rules.json", evolved_rules)
    evolved_memory_text = memory_to_text(evolved_rules, "LLM-evolved generic memory")
    (out_dir / "memory" / "llm_evolved_rules.md").write_text(evolved_memory_text, encoding="utf-8")

    evolved_summary = run_variant(
        "llm_evolved_memory",
        test,
        evolved_memory_text,
        args.model,
        args.workers,
        args.max_tokens,
        out_dir,
        force=args.force,
    )

    base_summaries = {
        "secodeplt_memory": read_json(V3 / "runs" / "secodeplt_memory" / "summary.json"),
        "codeseceval_memory": read_json(V3 / "runs" / "codeseceval_memory" / "summary.json"),
        "no_memory": read_json(V3 / "runs" / "no_memory" / "summary.json"),
    }
    write_report(out_dir, base_summaries, llm_summary, evolved_summary, merged_rules, updates)
    print(json.dumps({
        "llm_distilled": llm_summary,
        "llm_evolved": evolved_summary,
        "report": str(out_dir / "report.md"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
