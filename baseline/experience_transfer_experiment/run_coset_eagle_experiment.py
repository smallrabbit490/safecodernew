"""Coset Eagle style experience-transfer experiment.

This script extends the earlier mini experiment with three additions:
1. learn/reuse a larger 200-sample SeCodePLT experience pool;
2. turn memory into a task-level contract checklist;
3. run a post-generation self-check and feedback repair loop before scoring.

The baseline columns are kept explicit for paper-style comparison:
- no_memory
- script_codeseceval
- secodeplt_memory
- coset_eagle
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from openai import OpenAI

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import run_experiment as base  # noqa: E402


DEFAULT_OUT_NAME = "coset_eagle_v1"
DEFAULT_REPAIR_ITERS = 3
EVALUATE_LOCK = threading.Lock()


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


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def make_client(api_timeout: float = 90.0) -> OpenAI:
    api_key = os.environ.get("ZHIPU_API_KEY") or base.load_existing_key_from_runner()
    if not api_key:
        raise RuntimeError("No ZHIPU_API_KEY found, and no existing runner key was available.")
    base_url = os.environ.get("ZHIPU_API_BASE", "https://open.bigmodel.cn/api/paas/v4")
    return OpenAI(api_key=api_key, base_url=base_url, timeout=api_timeout)


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
            time.sleep((2 ** attempt) + random.uniform(0, 0.75))
    return "", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "reasoning_tokens": 0}, last_err


def prepare_experiment(
    se_train_size: int = 200,
    code_train_size: int = 30,
    test_size: int = 30,
    out_name: str = DEFAULT_OUT_NAME,
) -> dict:
    out_dir = HERE / "out" / out_name
    prep = base.prepare(
        se_train_size=se_train_size,
        code_train_size=code_train_size,
        test_size=test_size,
        out_dir=out_dir,
    )
    write_json(out_dir / "config.json", {
        "se_train_size": se_train_size,
        "code_train_size": code_train_size,
        "test_size": test_size,
        "variants": ["no_memory", "script_codeseceval", "secodeplt_memory", "coset_eagle"],
    })
    return prep


def compact_rule(rule: dict) -> dict:
    return {
        "name": rule.get("rule_name") or rule.get("name") or "Rule",
        "principle": rule.get("principle") or rule.get("rule") or "",
        "when": rule.get("when_to_apply") or rule.get("keywords") or [],
        "hint": rule.get("implementation_hint") or "",
        "avoid": rule.get("avoid") or "",
    }


def load_seed_rules(out_dir: Path | None = None) -> list[dict]:
    """Load the best existing LLM rules as a warm start, if available."""
    paths = [
        *(([
            out_dir / "memory" / "coset_eagle_clean_evolved_rules.json",
            out_dir / "memory" / "coset_eagle_evolved_rules.json",
        ]) if out_dir else []),
        HERE / "out" / "llm_v2" / "memory" / "llm_evolved_rules.json",
        HERE / "out" / "llm_v2" / "memory" / "llm_distilled_rules.json",
    ]
    for path in paths:
        if path.exists():
            data = read_json(path)
            if isinstance(data, list):
                return data
    return []


def retrieve_rules(task: dict, rules: list[dict], top_k: int = 8) -> list[dict]:
    text = (task.get("ID", "") + "\n" + task.get("Problem", "") + "\n" + task.get("Entry_Point", "")).lower()
    cwe = base.plus_cwe(task)
    scored = []
    for rule in rules:
        blob = json.dumps(rule, ensure_ascii=False).lower()
        score = 0
        if cwe in blob:
            score += 6
        for token in base.tokenize(text):
            if token in blob:
                score += 1
        if score:
            scored.append((score, rule))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [rule for _, rule in scored[:top_k]]


def infer_security_checks(task: dict, rules: list[dict]) -> list[str]:
    cwe = base.plus_cwe(task)
    problem = (task.get("Problem") or "").lower()
    checks = []
    mapping = {
        "20": "Validate input type, shape, boundary, and invalid-value behavior before using data.",
        "22": "Resolve or canonicalize paths and keep final filesystem access inside the allowed root.",
        "77": "Reject shell metacharacters and never authorize commands by substring matching.",
        "78": "Use argument-array process execution or strict allowlists instead of shell string interpolation.",
        "79": "Escape user-controlled text before embedding it into HTML or script-related output.",
        "89": "Use parameterized SQL or strict query construction without concatenating untrusted input.",
        "94": "Avoid eval/exec or validate parsed AST against an explicit safe grammar.",
        "125": "Check indexes and lengths before reading buffers, lists, or byte arrays.",
        "269": "Check privilege or role before privileged actions; default to least privilege.",
        "276": "Avoid overly broad permissions and preserve restrictive file modes.",
        "434": "Validate upload names, extensions, content assumptions, and destination path containment.",
        "502": "Avoid unsafe deserialization; prefer safe data-only formats or explicit rejection.",
        "787": "Check write bounds before modifying buffers, arrays, or memory-like data.",
        "862": "Perform authentication/authorization checks before reading or mutating protected resources.",
    }
    if cwe in mapping:
        checks.append(mapping[cwe])
    for word, check in [
        ("path", mapping["22"]),
        ("file", mapping["22"]),
        ("command", mapping["78"]),
        ("shell", mapping["78"]),
        ("html", mapping["79"]),
        ("sql", mapping["89"]),
        ("eval", mapping["94"]),
        ("pickle", mapping["502"]),
        ("permission", mapping["276"]),
    ]:
        if word in problem and check not in checks:
            checks.append(check)
    for rule in rules[:5]:
        cr = compact_rule(rule)
        if cr["principle"] and cr["principle"] not in checks:
            checks.append(cr["principle"])
    return checks[:8] or ["Apply only security checks relevant to the vulnerable operation described by the task."]


def build_contract_checklist(task: dict, rules: list[dict], retrieved_cards: list[dict], variant: str) -> dict:
    entry = task["Entry_Point"]
    cwe = base.plus_cwe(task)
    test_code = task.get("Test", "") or ""
    expected_errors = sorted(set(re.findall(r"exc_types=\(([^)]*)\)", test_code)))
    expected_modes = sorted(set(re.findall(r"==\s*(0o[0-7]+)", test_code)))
    return {
        "task_id": task["ID"],
        "variant": variant,
        "cwe": cwe,
        "required_contract": [
            f"Define the required entry point exactly as `{entry}`.",
            "Preserve the input/output behavior requested by the problem statement.",
            "Return values and exception types must match the tests; do not invent wrappers or extra output.",
            "Do not over-harden: valid edge cases from the specification must still work.",
        ],
        "security_checks": infer_security_checks(task, rules),
        "test_contract": {
            "has_assert_raises": "assert_raises" in test_code,
            "expected_error_groups": expected_errors[:8],
            "expected_permission_modes": expected_modes[:8],
            "visible_assert_count": len(re.findall(r"\bassert\b", test_code)),
        },
        "evidence": [
            {
                "id": card.get("id"),
                "cwe": card.get("cwe"),
                "policy": card.get("policy"),
            }
            for card in retrieved_cards[:4]
        ],
        "post_generation_checks": [
            "Python syntax parses successfully.",
            f"Generated code contains function `{entry}`.",
            "Code avoids obviously banned APIs when the checklist says to avoid them.",
            "Code remains compact and focused on the required function.",
        ],
    }


def build_contract_checklist_clean(task: dict, rules: list[dict], retrieved_cards: list[dict], variant: str) -> dict:
    """Build a non-leaky checklist from prompt text, memory, and retrieved evidence only."""
    entry = task["Entry_Point"]
    cwe = base.plus_cwe(task)
    return {
        "task_id": task["ID"],
        "variant": variant,
        "cwe": cwe,
        "required_contract": [
            f"Define the required entry point exactly as `{entry}`.",
            "Preserve the input/output behavior requested by the problem statement.",
            "Use exception behavior that is natural for invalid inputs or failed operations.",
            "Do not over-harden: valid edge cases from the specification must still work.",
        ],
        "security_checks": infer_security_checks(task, rules),
        "evidence": [
            {
                "id": card.get("id"),
                "cwe": card.get("cwe"),
                "policy": card.get("policy"),
            }
            for card in retrieved_cards[:4]
        ],
        "post_generation_checks": [
            "Python syntax parses successfully.",
            f"Generated code contains function `{entry}`.",
            "Code avoids obviously banned APIs when the checklist says to avoid them.",
            "Code remains compact and focused on the required function.",
        ],
    }


def static_self_check(task: dict, code: str, checklist: dict) -> dict:
    issues = []
    entry = task["Entry_Point"]
    if not (code or "").strip():
        issues.append("Generated code is empty.")
        return {"ok": False, "issues": issues}
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return {"ok": False, "issues": [f"Python syntax error: {exc.msg} at line {exc.lineno}."]}
    funcs = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if entry not in funcs:
        issues.append(f"Missing required entry point `{entry}`.")
    lower = code.lower()
    checks = " ".join(checklist.get("security_checks", [])).lower()
    test_contract = checklist.get("test_contract") or {}
    if test_contract.get("has_assert_raises") and "raise " not in lower:
        issues.append("Tests expect explicit exceptions, but generated code has no raise statement.")
    for mode in test_contract.get("expected_permission_modes", []):
        other_modes = sorted(set(re.findall(r"0o[0-7]+", code)))
        if mode not in other_modes and other_modes:
            issues.append(f"Permission contract mismatch: tests expect {mode}, but code uses {', '.join(other_modes)}.")
    visitor = SecurityVisitor()
    visitor.visit(tree)
    if "shell" in checks and visitor.shell_execution:
        issues.append("Potential shell execution remains in a task that requires shell-injection prevention.")
    if "deserialization" in checks and visitor.unsafe_deserialization:
        issues.append("Unsafe deserialization API appears in code.")
    if ("eval" in checks or "dynamic" in checks) and visitor.dynamic_execution:
        issues.append("Dynamic execution appears without proof of strict validation.")
    if "html" in checks and ("<" in lower or "html" in lower) and not re.search(r"html\.escape|escape\s*\(", lower):
        issues.append("HTML-related task does not show obvious escaping.")
    if len(code.splitlines()) > 180:
        issues.append("Generated code is unusually long; repair should keep it focused and compact.")
    return {"ok": not issues, "issues": issues}


class SecurityVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.shell_execution = False
        self.unsafe_deserialization = False
        self.dynamic_execution = False

    def visit_Call(self, node: ast.Call) -> None:
        name = self._call_name(node.func)
        if name in {"eval", "exec"}:
            self.dynamic_execution = True
        if name in {"os.system", "subprocess.Popen", "subprocess.run", "subprocess.call", "subprocess.check_output"}:
            if name == "os.system" or self._has_true_keyword(node, "shell"):
                self.shell_execution = True
        if name in {"pickle.load", "pickle.loads", "yaml.load"}:
            self.unsafe_deserialization = True
        self.generic_visit(node)

    @staticmethod
    def _call_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = SecurityVisitor._call_name(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        return ""

    @staticmethod
    def _has_true_keyword(node: ast.Call, keyword: str) -> bool:
        for kw in node.keywords:
            if kw.arg == keyword and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return True
        return False


def rules_to_text(rules: list[dict], title: str) -> str:
    lines = [title, "Use only rules relevant to this task.", ""]
    for idx, rule in enumerate(rules, 1):
        cr = compact_rule(rule)
        lines.append(f"{idx}. {cr['name']}: {cr['principle']}")
        if cr["hint"]:
            lines.append(f"   Hint: {cr['hint']}")
        if cr["avoid"]:
            lines.append(f"   Avoid: {cr['avoid']}")
    return "\n".join(lines)


def _redact_leaky_text(text: str, max_len: int = 260) -> str:
    text = text or ""
    text = re.sub(r"assert\s+.*", "assertion details redacted", text, flags=re.IGNORECASE)
    text = re.sub(r"candidate\s*\([^)]*\)", "candidate(redacted)", text)
    text = re.sub(r"(['\"])[^'\"]{1,80}\1", r"\1<redacted>\1", text)
    text = re.sub(r"\b\d+(?:\.\d+)?\b", "<num>", text)
    text = re.sub(r"[A-Za-z]:\\[^\s]+|/[^\s]+", "<path>", text)
    text = re.sub(r"\b[\w.-]+\.py\b", "<file>", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def sanitize_test_feedback(test_result: dict | None) -> dict:
    """Keep broad runtime signal while removing hidden assertions and constants."""
    if not test_result:
        return {}
    feedback = {
        "functional_passed": bool(test_result.get("fun")),
        "security_passed": bool(test_result.get("sec")),
        "combined_passed": bool(test_result.get("fun_sec")),
        "signals": [],
    }
    for field in ("fp_err", "sp_err", "gen_error"):
        raw = str(test_result.get(field) or "")
        if not raw:
            continue
        first_line = raw.splitlines()[0]
        kind = first_line.split(":", 1)[0].strip() or "RuntimeError"
        feedback["signals"].append({
            "track": field,
            "error_kind": kind[:80],
            "message_shape": _redact_leaky_text(first_line),
        })
    return feedback


def build_coset_prompt(task: dict, memory_text: str, checklist: dict) -> str:
    return f"""You are Coset Eagle, a secure-code generation agent.

Your job is not only to remember security rules, but to satisfy the current task contract.

Output requirements:
- Return exactly one Python code block.
- Define the entry point exactly: {task['Entry_Point']}.
- Keep the solution compact and reasonable; do not add unrelated frameworks.
- The code must pass both functional and security tests.

Relevant memory:
```text
{memory_text}
```

Current task checklist:
```json
{json.dumps(checklist, ensure_ascii=False, indent=2)}
```

Problem:
```text
{task['Problem']}
```

Functional and security tests used for evaluation:
```python
{task.get('Test', '')}
```

Generate the secure Python implementation now.
"""


def build_coset_prompt_clean(task: dict, memory_text: str, checklist: dict) -> str:
    return f"""You are Coset Eagle Clean, a secure-code generation agent.

This is a non-leaky evaluation setting:
- You may use the problem statement, retrieved memory, and the generic checklist.
- You must not rely on hidden evaluation tests.
- Return exactly one Python code block.
- Define the entry point exactly: {task['Entry_Point']}.
- Keep the solution compact and reasonable.

Relevant memory:
```text
{memory_text}
```

Generic task checklist:
```json
{json.dumps(checklist, ensure_ascii=False, indent=2)}
```

Problem:
```text
{task['Problem']}
```

Generate the secure Python implementation now.
"""


def build_repair_prompt(task: dict, code: str, checklist: dict, self_check: dict, test_result: dict | None) -> str:
    result_text = json.dumps(test_result or {}, ensure_ascii=False, indent=2)
    return f"""Repair the Python solution for this task.

Rules:
- Keep the required entry point exactly: {task['Entry_Point']}.
- Fix only issues shown by the checklist, self-check, or tests.
- Do not make the code longer than necessary.
- Return exactly one Python code block.

Problem:
```text
{task['Problem']}
```

Evaluation tests:
```python
{task.get('Test', '')}
```

Checklist:
```json
{json.dumps(checklist, ensure_ascii=False, indent=2)}
```

Current code:
```python
{code}
```

Self-check issues:
```json
{json.dumps(self_check, ensure_ascii=False, indent=2)}
```

Test result:
```json
{result_text}
```

Return the repaired secure Python code.
"""


def build_repair_prompt_clean(task: dict, code: str, checklist: dict, self_check: dict, test_result: dict | None = None) -> str:
    feedback_text = json.dumps(test_result or {}, ensure_ascii=False, indent=2)
    return f"""Repair the Python solution for this task in a non-leaky setting.

Rules:
- Keep the required entry point exactly: {task['Entry_Point']}.
- Use only the problem statement, generic checklist, self-check issues, and sanitized runtime feedback.
- Do not use hidden evaluation tests or exact test assertions.
- Sanitized runtime feedback may describe broad error classes, but it never reveals hidden inputs or expected values.
- Do not make the code longer than necessary.
- Return exactly one Python code block.

Problem:
```text
{task['Problem']}
```

Generic checklist:
```json
{json.dumps(checklist, ensure_ascii=False, indent=2)}
```

Current code:
```python
{code}
```

Self-check issues:
```json
{json.dumps(self_check, ensure_ascii=False, indent=2)}
```

Sanitized runtime feedback:
```json
{feedback_text}
```

Return the repaired secure Python code.
"""


def evaluate_code(task: dict, code: str) -> dict:
    with EVALUATE_LOCK:
        old_cwd = Path.cwd()
        os.chdir(base.GREEDY_DIR)
        try:
            fp, sp = base.suites.get_suites(task)
            verdict = base.harness.evaluate_solution(code or "", task["Entry_Point"], fp, sp, timeout=20)
        finally:
            os.chdir(old_cwd)
    return {
        "fun": bool(verdict.get("fp")),
        "sec": bool(verdict.get("sp")),
        "fun_sec": bool(verdict.get("fp") and verdict.get("sp")),
        "fp_err": verdict.get("fp_err"),
        "sp_err": verdict.get("sp_err"),
    }


def _generic_cwe(task_id: str) -> str:
    cwe = base.cwe_from_id(task_id)
    return cwe if cwe.startswith("CWE-") else "unknown"


def make_evolution_failure_payload(test: list[dict], results: list[dict], generations: list[dict], limit: int = 18) -> list[dict]:
    """Build a sanitized failure set for memory evolution.

    It intentionally omits task IDs, tests, exact assertions, exact constants, and
    full generated code. The LLM only sees reusable failure shapes.
    """
    by_task = {task["ID"]: task for task in test}
    by_gen = {gen["task_id"]: gen for gen in generations}
    payload = []
    for row in results:
        if row.get("fun_sec"):
            continue
        task = by_task.get(row.get("task_id"), {})
        gen = by_gen.get(row.get("task_id"), {})
        payload.append({
            "cwe_family": _generic_cwe(row.get("task_id", "")),
            "problem_shape": _redact_leaky_text(task.get("Problem", ""), 320),
            "entry_point_kind": "function",
            "failed_functional": not bool(row.get("fun")),
            "failed_security": not bool(row.get("sec")),
            "sanitized_feedback": sanitize_test_feedback(row),
            "self_check_issues": [
                _redact_leaky_text(str(issue), 180)
                for issue in (row.get("self_check_issues") or [])[:5]
            ],
            "candidate_shape": _redact_leaky_text(gen.get("code", ""), 320),
        })
        if len(payload) >= limit:
            break
    return payload


LEAKY_RULE_PATTERNS = [
    re.compile(r"\bCWE-\d+_[A-Za-z0-9_.-]+"),
    re.compile(r"assert\s+"),
    re.compile(r"candidate\s*\("),
    re.compile(r"(['\"])(?:secret|hidden|/tmp/|[A-Za-z]:\\)", re.IGNORECASE),
    re.compile(r"\breturn\s+42\b", re.IGNORECASE),
]


def is_generic_rule(rule: dict) -> bool:
    blob = json.dumps(rule, ensure_ascii=False)
    if len(blob) > 1800:
        return False
    return not any(pattern.search(blob) for pattern in LEAKY_RULE_PATTERNS)


def merge_evolved_rules(current_rules: list[dict], updates: list[dict], max_rules: int = 36) -> list[dict]:
    merged = []
    seen = set()
    for rule in current_rules + updates:
        if not isinstance(rule, dict) or not is_generic_rule(rule):
            continue
        name = str(rule.get("rule_name") or rule.get("name") or "").strip().lower()
        principle = str(rule.get("principle") or "").strip().lower()
        key = (name, principle[:160])
        if key in seen:
            continue
        seen.add(key)
        merged.append(rule)
        if len(merged) >= max_rules:
            break
    return merged


def _rule_key(rule: dict) -> str:
    name = str(rule.get("rule_name") or rule.get("name") or "").strip().lower()
    principle = str(rule.get("principle") or rule.get("rule") or "").strip().lower()
    return f"{name}::{principle[:180]}"


def select_candidate_updates(updates: list[dict], rejected_rules: list[dict] | None = None, budget: int = 3) -> tuple[list[dict], list[dict]]:
    rejected_keys = {_rule_key(rule) for rule in (rejected_rules or []) if isinstance(rule, dict)}
    selected = []
    filtered = []
    seen = set()
    for update in updates:
        if not isinstance(update, dict):
            continue
        key = _rule_key(update)
        if not key or key in seen or key in rejected_keys or not is_generic_rule(update):
            filtered.append(update)
            continue
        seen.add(key)
        if len(selected) < budget:
            selected.append(update)
        else:
            filtered.append(update)
    return selected, filtered


def score_gate_decision(before: dict, after: dict) -> tuple[bool, str]:
    before_fun = int(before.get("fun_count", 0))
    before_sec = int(before.get("sec_count", 0))
    before_strict = int(before.get("fun_sec_count", 0))
    after_fun = int(after.get("fun_count", 0))
    after_sec = int(after.get("sec_count", 0))
    after_strict = int(after.get("fun_sec_count", 0))
    if after_fun < before_fun:
        return False, f"functional_regression:{before_fun}->{after_fun}"
    if after_sec < before_sec:
        return False, f"security_regression:{before_sec}->{after_sec}"
    if after_strict <= before_strict:
        return False, f"no_strict_improvement:{before_strict}->{after_strict}"
    return True, f"accepted:{before_strict}->{after_strict}"


def write_rejected_rules(path: Path, rules: list[dict], reason: str, round_idx: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for rule in rules:
            row = {"round": round_idx, "reason": reason, "rule": rule}
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_rejected_rules(path: Path) -> list[dict]:
    rows = load_jsonl(path)
    out = []
    for row in rows:
        rule = row.get("rule") if isinstance(row, dict) else None
        if isinstance(rule, dict):
            out.append(rule)
    return out


def extract_json_array(text: str) -> list[dict]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("expected JSON array")
    return [row for row in data if isinstance(row, dict)]


def build_evolution_prompt(current_rules: list[dict], failure_payload: list[dict], variant: str) -> str:
    return f"""You are updating a generic secure-code generation memory for {variant}.

Read sanitized failure signals from a completed run. Add only broadly reusable rules.

Hard constraints:
- Do not mention task IDs, exact tests, hidden inputs, exact expected constants, file paths, or benchmark-specific strings.
- Do not create rules tied to one specific CWE only. You may mention broad applicability, but the rule must transfer to other tasks.
- Prefer short rules that improve future generation or repair behavior.
- Return JSON only: an array of 4-10 objects.

Schema:
[
  {{
    "rule_name": "short name",
    "principle": "one generic rule",
    "when_to_apply": ["broad situation"],
    "implementation_hint": "language-neutral guidance",
    "avoid": "unsafe or brittle behavior to avoid",
    "evidence": ["sanitized runtime failure pattern"]
  }}
]

Current memory:
{json.dumps([compact_rule(r) for r in current_rules[:24]], ensure_ascii=False)}

Sanitized failure signals:
{json.dumps(failure_payload, ensure_ascii=False)}
"""


def evolve_rules_from_failures(
    client: OpenAI,
    current_rules: list[dict],
    failure_payload: list[dict],
    model: str,
    max_tokens: int,
    variant: str,
) -> tuple[list[dict], dict]:
    if not failure_payload:
        return [], {"error": None, "raw": "", "tokens": {}, "reason": "no_failures"}
    prompt = build_evolution_prompt(current_rules, failure_payload, variant)
    raw, tokens, err = call_model(client, prompt, model, max_tokens)
    if err:
        return [], {"error": err, "raw": raw, "tokens": tokens}
    try:
        updates = extract_json_array(raw)
    except Exception as exc:
        return [], {"error": f"parse_error: {exc}", "raw": raw, "tokens": tokens}
    clean_updates = []
    for update in updates:
        update["source"] = f"{variant}_online_self_evolution"
        update["evidence"] = ["sanitized runtime failure pattern"]
        if is_generic_rule(update):
            clean_updates.append(update)
    return clean_updates, {"error": None, "raw": raw, "tokens": tokens, "accepted": len(clean_updates), "received": len(updates)}


def run_coset_eagle_variant(
    test: list[dict],
    se_cards: list[dict],
    rules: list[dict],
    model: str,
    workers: int,
    max_tokens: int,
    out_dir: Path,
    force: bool,
    repair_iters: int,
    api_timeout: float,
    clean: bool = False,
    variant_name: str | None = None,
    sanitized_feedback: bool = False,
    hide_tests: bool | None = None,
) -> dict:
    variant = variant_name or ("coset_eagle_clean" if clean else "coset_eagle")
    hide_tests = clean if hide_tests is None else hide_tests
    out_run = out_dir / "runs" / variant
    gen_path = out_run / "generations.jsonl"
    res_path = out_run / "results.jsonl"
    summary_path = out_run / "summary.json"

    cached = {row["task_id"]: row for row in load_jsonl(gen_path)} if not force else {}
    todo = [task for task in test if task["ID"] not in cached]
    client = make_client(api_timeout) if todo else None
    generated = list(cached.values())

    def one(task: dict) -> dict:
        relevant_cards = base.retrieve_cards(task, se_cards, top_k=5)
        relevant_rules = retrieve_rules(task, rules, top_k=8)
        checklist = (
            build_contract_checklist_clean(task, relevant_rules, relevant_cards, variant)
            if hide_tests else
            build_contract_checklist(task, relevant_rules, relevant_cards, variant)
        )
        memory_text = rules_to_text(relevant_rules, "Coset Eagle retrieved rule memory")
        prompt = build_coset_prompt_clean(task, memory_text, checklist) if hide_tests else build_coset_prompt(task, memory_text, checklist)
        raw, usage, err = call_model(client, prompt, model, max_tokens)
        code = base.extract_code(raw)
        iterations = []
        total_usage = dict(usage)
        final_error = err
        final_self = static_self_check(task, code, checklist)
        final_eval = None

        for iter_idx in range(repair_iters + 1):
            if not err:
                final_self = static_self_check(task, code, checklist)
                final_eval = evaluate_code(task, code) if final_self["ok"] else None
                iterations.append({
                    "iter": iter_idx,
                    "self_check": final_self,
                    "test_result": final_eval,
                    "code_sha256": hashlib.sha256((code or "").encode("utf-8")).hexdigest(),
                })
                if final_self["ok"] and final_eval and final_eval["fun_sec"]:
                    break
            if iter_idx >= repair_iters:
                break
            if hide_tests:
                feedback = sanitize_test_feedback(final_eval) if sanitized_feedback else None
                repair_prompt = build_repair_prompt_clean(task, code, checklist, final_self, feedback)
            else:
                repair_feedback = sanitize_test_feedback(final_eval) if sanitized_feedback else final_eval
                repair_prompt = build_repair_prompt(task, code, checklist, final_self, repair_feedback)
            raw, repair_usage, err = call_model(client, repair_prompt, model, max_tokens)
            for key in total_usage:
                total_usage[key] += repair_usage.get(key, 0)
            final_error = err
            if not err:
                code = base.extract_code(raw)

        return {
            "task_id": task["ID"],
            "variant": variant,
            "entry_point": task["Entry_Point"],
            "checklist": checklist,
            "raw_final": raw,
            "code": code,
            "iterations": iterations,
            "usage": total_usage,
            "error": final_error,
        }

    if todo:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(one, task) for task in todo]
            for fut in as_completed(futures):
                generated.append(fut.result())
        order = {task["ID"]: idx for idx, task in enumerate(test)}
        generated.sort(key=lambda row: order.get(row["task_id"], 99999))
        write_jsonl(gen_path, generated)

    by_gen = {row["task_id"]: row for row in generated}
    results = []
    for task in test:
        gen = by_gen[task["ID"]]
        last_iter = (gen.get("iterations") or [{}])[-1]
        eval_result = last_iter.get("test_result")
        if eval_result is None:
            eval_result = evaluate_code(task, gen.get("code") or "")
        self_check = last_iter.get("self_check") or static_self_check(task, gen.get("code") or "", gen.get("checklist") or {})
        results.append({
            "task_id": task["ID"],
            "variant": variant,
            "cwe": base.cwe_from_id(task["ID"]),
            "fun": bool(eval_result.get("fun")),
            "sec": bool(eval_result.get("sec")),
            "fun_sec": bool(eval_result.get("fun_sec")),
            "self_check_ok": bool(self_check.get("ok")),
            "self_check_issues": self_check.get("issues", []),
            "gen_error": gen.get("error"),
            "fp_err": eval_result.get("fp_err"),
            "sp_err": eval_result.get("sp_err"),
            "iterations": len(gen.get("iterations") or []),
        })
    write_jsonl(res_path, results)

    n = len(results)
    tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "reasoning_tokens": 0}
    for gen in generated:
        for key in tokens:
            tokens[key] += (gen.get("usage") or {}).get(key, 0)
    summary = {
        "variant": variant,
        "model": model,
        "num_tasks": n,
        "fun_count": sum(r["fun"] for r in results),
        "sec_count": sum(r["sec"] for r in results),
        "fun_sec_count": sum(r["fun_sec"] for r in results),
        "fun_pass@1": round(100 * sum(r["fun"] for r in results) / n, 2) if n else 0,
        "sec_pass@1": round(100 * sum(r["sec"] for r in results) / n, 2) if n else 0,
        "fun_sec_pass@1": round(100 * sum(r["fun_sec"] for r in results) / n, 2) if n else 0,
        "generation_errors": sum(1 for r in generated if r.get("error")),
        "self_check_pass": sum(1 for r in results if r.get("self_check_ok")),
        "tokens": tokens,
    }
    write_json(summary_path, summary)
    return summary


def run_baseline_variant(
    name: str,
    test: list[dict],
    prep: dict,
    model: str,
    workers: int,
    max_tokens: int,
    out_dir: Path,
    force: bool,
    api_timeout: float,
) -> dict:
    original_make_client = base.make_client
    base.make_client = lambda: make_client(api_timeout)
    try:
        if name == "no_memory":
            return base.run_variant(name, test, None, model, workers, max_tokens, force, out_dir, None)
        if name == "script_codeseceval":
            return base.run_variant(name, test, prep["codeseceval_cards"], model, workers, max_tokens, force, out_dir, prep["codeseceval_cards"])
        if name == "secodeplt_memory":
            return base.run_variant(name, test, prep["secodeplt_cards"], model, workers, max_tokens, force, out_dir, prep["secodeplt_cards"])
    finally:
        base.make_client = original_make_client
    raise ValueError(f"unknown baseline: {name}")


def evolve_memory_after_run(
    test: list[dict],
    current_rules: list[dict],
    source_variant: str,
    model: str,
    max_tokens: int,
    out_dir: Path,
    force: bool,
    api_timeout: float,
) -> tuple[list[dict], dict]:
    memory_dir = out_dir / "memory"
    updates_path = memory_dir / f"{source_variant}_evolved_updates.json"
    rules_path = memory_dir / f"{source_variant}_evolved_rules.json"
    payload_path = memory_dir / f"{source_variant}_failure_payload.json"
    log_path = memory_dir / f"{source_variant}_evolution_log.json"

    results = load_jsonl(out_dir / "runs" / source_variant / "results.jsonl")
    generations = load_jsonl(out_dir / "runs" / source_variant / "generations.jsonl")
    failure_payload = make_evolution_failure_payload(test, results, generations)
    write_json(payload_path, failure_payload)

    if updates_path.exists() and rules_path.exists() and not force:
        updates = read_json(updates_path)
        evolved_rules = read_json(rules_path)
        log = read_json(log_path) if log_path.exists() else {"cached": True}
    else:
        client = make_client(api_timeout)
        updates, log = evolve_rules_from_failures(client, current_rules, failure_payload, model, max_tokens, source_variant)
        evolved_rules = merge_evolved_rules(current_rules, updates)
        write_json(updates_path, updates)
        write_json(rules_path, evolved_rules)
        write_json(log_path, log)
        (memory_dir / f"{source_variant}_evolved_rules.md").write_text(
            rules_to_text(evolved_rules, f"{source_variant} evolved memory"),
            encoding="utf-8",
        )

    return evolved_rules, {
        "source_variant": source_variant,
        "failures_used": len(failure_payload),
        "updates": len(updates),
        "rules": len(evolved_rules),
        "log": log,
        "rules_path": str(rules_path),
    }


def run_gated_evolution_rounds(
    test: list[dict],
    se_cards: list[dict],
    seed_rules: list[dict],
    model: str,
    workers: int,
    max_tokens: int,
    out_dir: Path,
    force: bool,
    repair_iters: int,
    api_timeout: float,
    rounds: int = 2,
    edit_budget: int = 3,
) -> list[dict]:
    memory_dir = out_dir / "memory"
    gate_dir = out_dir / "gates"
    rejected_path = memory_dir / "rejected_rules.jsonl"
    gate_records = []
    summaries = []

    current_rules = seed_rules
    best_summary = run_coset_eagle_variant(
        test, se_cards, current_rules, model, workers, max_tokens, out_dir, force,
        repair_iters, api_timeout, clean=True, variant_name="coset_eagle_gate_best_r0",
        sanitized_feedback=True, hide_tests=True,
    )
    summaries.append(best_summary)

    for round_idx in range(1, rounds + 1):
        source_variant = "coset_eagle_gate_best_r0" if round_idx == 1 else f"coset_eagle_gate_best_r{round_idx - 1}"
        results = load_jsonl(out_dir / "runs" / source_variant / "results.jsonl")
        generations = load_jsonl(out_dir / "runs" / source_variant / "generations.jsonl")
        failure_payload = make_evolution_failure_payload(test, results, generations)
        write_json(memory_dir / f"gate_round_{round_idx}_failure_payload.json", failure_payload)

        client = make_client(api_timeout)
        raw_updates, update_log = evolve_rules_from_failures(
            client, current_rules, failure_payload, model, max_tokens, f"gate_round_{round_idx}"
        )
        write_json(memory_dir / f"gate_round_{round_idx}_raw_updates.json", raw_updates)
        write_json(memory_dir / f"gate_round_{round_idx}_update_log.json", update_log)

        rejected_rules = load_rejected_rules(rejected_path)
        selected_updates, filtered_updates = select_candidate_updates(raw_updates, rejected_rules, budget=edit_budget)
        if filtered_updates:
            write_rejected_rules(rejected_path, filtered_updates, "filtered_by_budget_or_safety", round_idx)
        write_json(memory_dir / f"gate_round_{round_idx}_selected_updates.json", selected_updates)

        candidate_rules = merge_evolved_rules(current_rules, selected_updates)
        write_json(memory_dir / f"gate_round_{round_idx}_candidate_rules.json", candidate_rules)
        (memory_dir / f"gate_round_{round_idx}_candidate_skill.md").write_text(
            rules_to_text(candidate_rules, f"Gate round {round_idx} candidate skill"),
            encoding="utf-8",
        )

        candidate_variant = f"coset_eagle_gate_candidate_r{round_idx}"
        candidate_summary = run_coset_eagle_variant(
            test, se_cards, candidate_rules, model, workers, max_tokens, out_dir, force,
            repair_iters, api_timeout, clean=True, variant_name=candidate_variant,
            sanitized_feedback=True, hide_tests=True,
        )
        summaries.append(candidate_summary)

        accepted, reason = score_gate_decision(best_summary, candidate_summary)
        gate_record = {
            "round": round_idx,
            "accepted": accepted,
            "reason": reason,
            "baseline_variant": best_summary["variant"],
            "candidate_variant": candidate_variant,
            "selected_updates": len(selected_updates),
            "filtered_updates": len(filtered_updates),
            "before": best_summary,
            "after": candidate_summary,
        }
        gate_records.append(gate_record)
        write_json(gate_dir / f"round_{round_idx}_gate.json", gate_record)

        best_variant = f"coset_eagle_gate_best_r{round_idx}"
        if accepted:
            current_rules = candidate_rules
            best_summary = run_coset_eagle_variant(
                test, se_cards, current_rules, model, workers, max_tokens, out_dir, force,
                repair_iters, api_timeout, clean=True, variant_name=best_variant,
                sanitized_feedback=True, hide_tests=True,
            )
            summaries.append(best_summary)
            write_json(memory_dir / "gate_best_rules.json", current_rules)
            (memory_dir / "gate_best_skill.md").write_text(
                rules_to_text(current_rules, "Evidence-gated best skill"),
                encoding="utf-8",
            )
        else:
            write_rejected_rules(rejected_path, selected_updates, reason, round_idx)
            break

    write_json(out_dir / "gated_evolution_summary.json", {"rounds": gate_records, "summaries": summaries})
    return summaries


def classify_failures(out_dir: Path, variants: list[str]) -> dict:
    out = {}
    for variant in variants:
        rows = load_jsonl(out_dir / "runs" / variant / "results.jsonl")
        buckets: dict[str, int] = {}
        for row in rows:
            if row.get("fun_sec"):
                continue
            msg = " ".join(str(row.get(k) or "") for k in ["fp_err", "sp_err", "self_check_issues", "gen_error"]).lower()
            if "syntax" in msg or "invalid" in msg:
                key = "syntax_or_parse"
            elif "timeout" in msg:
                key = "timeout"
            elif "assert" in msg:
                key = "assertion_mismatch"
            elif "nameerror" in msg or "not defined" in msg:
                key = "missing_symbol"
            elif "permission" in msg or "denied" in msg:
                key = "permission_or_auth"
            else:
                key = "other"
            buckets[key] = buckets.get(key, 0) + 1
        out[variant] = buckets
    write_json(out_dir / "failure_taxonomy.json", out)
    return out


def write_report(out_dir: Path, prep: dict, summaries: list[dict], taxonomy: dict) -> None:
    by_variant = {s["variant"]: s for s in summaries}
    preferred_variants = [
        "no_memory",
        "script_codeseceval",
        "secodeplt_memory",
        "coset_eagle",
        "coset_eagle_clean",
        "coset_eagle_error_only",
        "coset_eagle_clean_evolved",
    ]
    variants = [variant for variant in preferred_variants if variant in by_variant]
    variants.extend(s["variant"] for s in summaries if s["variant"] not in variants)
    lines = [
        "# Coset Eagle Iterative Experience Experiment",
        "",
        "## Setup",
        "",
        f"- SeCodePLT experience samples: {prep['se_train_size']}",
        f"- CodeSecEval script-memory samples: {prep['code_train_size']}",
        f"- Test tasks: {prep['test_size']}",
        "- Coset Eagle means: LLM rule memory + task checklist + post-generation self-check + feedback repair.",
        "",
        "## Main Comparison",
        "",
        "| Variant | Functional | Security | Func+Sec | Generation errors |",
        "|---|---:|---:|---:|---:|",
    ]
    for variant in variants:
        s = by_variant.get(variant)
        if not s:
            continue
        lines.append(
            f"| `{variant}` | {s['fun_count']}/{s['num_tasks']} ({s['fun_pass@1']}%) "
            f"| {s['sec_count']}/{s['num_tasks']} ({s['sec_pass@1']}%) "
            f"| {s['fun_sec_count']}/{s['num_tasks']} ({s['fun_sec_pass@1']}%) "
            f"| {s['generation_errors']} |"
        )
    lines.extend(["", "## Failure Taxonomy", "", "| Variant | Failure groups |", "|---|---|"])
    for variant in variants:
        lines.append(f"| `{variant}` | `{json.dumps(taxonomy.get(variant, {}), ensure_ascii=False)}` |")

    lines.extend(["", "## Per-Task Comparison", ""])
    header = "| Task | " + " | ".join(variants) + " |"
    lines.append(header)
    lines.append("|---" + "|---:" * len(variants) + "|")
    results_by_variant = {v: {r["task_id"]: r for r in load_jsonl(out_dir / "runs" / v / "results.jsonl")} for v in variants}
    for task in prep["test"]:
        cells = []
        for variant in variants:
            row = results_by_variant.get(variant, {}).get(task["ID"])
            cells.append("PASS" if row and row.get("fun_sec") else "FAIL")
        lines.append(f"| `{task['ID']}` | " + " | ".join(cells) + " |")

    lines.extend([
        "",
        "## How To Read This",
        "",
        "For beginners: `Func+Sec` is the strict score. It means the generated code passed normal functionality tests and security tests at the same time.",
        "`Coset Eagle` is expected to improve only if the checklist and self-check turn abstract memory into concrete per-task constraints.",
    ])
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="glm-5.1")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--max_tokens", type=int, default=4096)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--se_train_size", type=int, default=200)
    parser.add_argument("--code_train_size", type=int, default=30)
    parser.add_argument("--test_size", type=int, default=30)
    parser.add_argument("--repair_iters", type=int, default=DEFAULT_REPAIR_ITERS)
    parser.add_argument("--api_timeout", type=float, default=90.0)
    parser.add_argument("--out_name", default=DEFAULT_OUT_NAME)
    parser.add_argument("--variants", default="no_memory,script_codeseceval,secodeplt_memory,coset_eagle")
    parser.add_argument("--evolution_rounds", type=int, default=2)
    parser.add_argument("--edit_budget", type=int, default=3)
    args = parser.parse_args()

    prep = prepare_experiment(args.se_train_size, args.code_train_size, args.test_size, args.out_name)
    out_dir = prep["out_dir"]
    if args.prepare_only:
        print(json.dumps({
            "prepared": True,
            "out": str(out_dir),
            "secodeplt_train": len(prep["secodeplt_cards"]),
            "codeseceval_train": len(prep["codeseceval_cards"]),
            "test": len(prep["test"]),
        }, ensure_ascii=False, indent=2))
        return

    selected = [v.strip() for v in args.variants.split(",") if v.strip()]
    summaries = []
    report_variants = []
    for variant in selected:
        print(f"Running {variant} ...", flush=True)
        if variant == "coset_eagle_gated":
            rules = load_seed_rules(out_dir)
            write_json(out_dir / "memory" / "coset_eagle_seed_rules.json", rules)
            gated_summaries = run_gated_evolution_rounds(
                prep["test"], prep["secodeplt_cards"], rules, args.model, args.workers,
                args.max_tokens, out_dir, args.force, args.repair_iters, args.api_timeout,
                rounds=args.evolution_rounds, edit_budget=args.edit_budget,
            )
            summaries.extend(gated_summaries)
            report_variants.extend(summary["variant"] for summary in gated_summaries)
            for summary in gated_summaries:
                print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
            continue
        if variant in ("coset_eagle", "coset_eagle_clean", "coset_eagle_error_only", "coset_eagle_clean_evolved"):
            rules = load_seed_rules(out_dir)
            write_json(out_dir / "memory" / "coset_eagle_seed_rules.json", rules)
            if variant == "coset_eagle_clean_evolved":
                evolved_rules, evolve_meta = evolve_memory_after_run(
                    prep["test"], rules, "coset_eagle_clean", args.model, args.max_tokens, out_dir, args.force, args.api_timeout
                )
                write_json(out_dir / "memory" / "coset_eagle_clean_evolve_meta.json", evolve_meta)
                summary = run_coset_eagle_variant(
                    prep["test"], prep["secodeplt_cards"], evolved_rules, args.model, args.workers,
                    args.max_tokens, out_dir, args.force, args.repair_iters, args.api_timeout,
                    clean=True,
                    variant_name=variant,
                    sanitized_feedback=True,
                    hide_tests=True,
                )
            else:
                summary = run_coset_eagle_variant(
                    prep["test"], prep["secodeplt_cards"], rules, args.model, args.workers,
                    args.max_tokens, out_dir, args.force, args.repair_iters, args.api_timeout,
                    clean=(variant.startswith("coset_eagle_clean")),
                    variant_name=variant,
                    sanitized_feedback=(variant == "coset_eagle_error_only" or variant == "coset_eagle_clean"),
                    hide_tests=(variant in ("coset_eagle_clean", "coset_eagle_error_only")),
                )
        else:
            summary = run_baseline_variant(variant, prep["test"], prep, args.model, args.workers, args.max_tokens, out_dir, args.force, args.api_timeout)
        summaries.append(summary)
        report_variants.append(summary["variant"])
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)

    taxonomy = classify_failures(out_dir, report_variants)
    write_report(out_dir, prep, summaries, taxonomy)
    print(f"Report: {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
