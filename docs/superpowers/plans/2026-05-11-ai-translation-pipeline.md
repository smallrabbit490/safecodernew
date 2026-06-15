# AI Translation Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local pipeline that translates both `Secure Code` and `Insecure Code` from the Python CodeSecEval JSON datasets into C++ and Go, validates secure translations with functional tests, and validates insecure translations by matching the original Python insecure behavior.

**Architecture:** Keep the original JSON files untouched. Add a focused translation tool under `DatasetAndMethod/SecAwareCoder/translation_pipeline/`, and write all generated files, caches, logs, downloads, and temporary compile/run files under `D:\thecourceofdasi\safecodernew\translation_work\`. Use the local Zhipu API credentials from `质朴api使用\质朴.env`, cache API responses by task/code/language, and produce new translated JSON files in `translation_work\outputs\`.

**Tech Stack:** Python 3.10+, standard library first, optional `zhipuai` SDK if installed, fallback OpenAI-compatible HTTP if needed, local `g++` and `go` command-line tools for lightweight smoke tests, existing dataset JSON fields.

---

## File Structure

- Create: `DatasetAndMethod/SecAwareCoder/translation_pipeline/__init__.py`
  - Package marker only.
- Create: `DatasetAndMethod/SecAwareCoder/translation_pipeline/models.py`
  - Dataclasses for translation requests, translation results, and validation results.
- Create: `DatasetAndMethod/SecAwareCoder/translation_pipeline/paths.py`
  - Centralizes all project-relative and `translation_work` paths.
- Create: `DatasetAndMethod/SecAwareCoder/translation_pipeline/zhipu_client.py`
  - Loads local Zhipu keys and calls the translation model without printing secrets.
- Create: `DatasetAndMethod/SecAwareCoder/translation_pipeline/prompts.py`
  - Prompt builders for secure translation, insecure behavior-preserving translation, and repair.
- Create: `DatasetAndMethod/SecAwareCoder/translation_pipeline/code_extract.py`
  - Extracts C++/Go code blocks from model responses.
- Create: `DatasetAndMethod/SecAwareCoder/translation_pipeline/validators.py`
  - Runs Python baseline behavior checks, C++ compile/run checks, and Go compile/run checks in `translation_work\temp\`.
- Create: `DatasetAndMethod/SecAwareCoder/translation_pipeline/run_translate_dataset.py`
  - CLI entry point for batch translation, resume, caching, testing, repair, and JSON output.
- Create: `DatasetAndMethod/SecAwareCoder/translation_pipeline/README.md`
  - New-user friendly instructions.
- Create: `DatasetAndMethod/SecAwareCoder/tests/test_translation_pipeline_unit.py`
  - Unit tests that do not call the API.

The first implementation should avoid modifying existing workflow files. It should be an additive tool so the original research workflow remains stable.

---

### Task 1: Create Path And Data Models

**Files:**
- Create: `DatasetAndMethod/SecAwareCoder/translation_pipeline/__init__.py`
- Create: `DatasetAndMethod/SecAwareCoder/translation_pipeline/paths.py`
- Create: `DatasetAndMethod/SecAwareCoder/translation_pipeline/models.py`
- Test: `DatasetAndMethod/SecAwareCoder/tests/test_translation_pipeline_unit.py`

- [ ] **Step 1: Create a failing test for workspace paths**

Add this test:

```python
from pathlib import Path

from translation_pipeline.paths import get_project_root, get_work_dir, ensure_work_dirs


def test_translation_work_dir_is_inside_current_project():
    root = get_project_root()
    work_dir = get_work_dir()
    assert work_dir == root / "translation_work"
    dirs = ensure_work_dirs()
    assert dirs["cache"] == work_dir / "cache"
    assert dirs["temp"] == work_dir / "temp"
    assert dirs["logs"] == work_dir / "logs"
    assert dirs["outputs"] == work_dir / "outputs"
    assert dirs["downloads"] == work_dir / "downloads"
    for path in dirs.values():
        assert isinstance(path, Path)
        assert path.exists()
```

- [ ] **Step 2: Run the failing test**

Run from `DatasetAndMethod/SecAwareCoder`:

```bash
python -m pytest tests/test_translation_pipeline_unit.py -q
```

Expected: FAIL because `translation_pipeline.paths` does not exist yet.

- [ ] **Step 3: Implement `paths.py`**

Create these functions:

```python
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def get_work_dir() -> Path:
    return get_project_root() / "translation_work"


def ensure_work_dirs() -> dict[str, Path]:
    work_dir = get_work_dir()
    dirs = {
        "work": work_dir,
        "cache": work_dir / "cache",
        "temp": work_dir / "temp",
        "logs": work_dir / "logs",
        "outputs": work_dir / "outputs",
        "downloads": work_dir / "downloads",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs
```

- [ ] **Step 4: Implement `models.py`**

Add simple dataclasses:

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TranslationResult:
    code: str
    language: str
    source_field: str
    model: str
    attempts: int = 1
    error: str | None = None


@dataclass
class ValidationResult:
    ok: bool
    language: str
    mode: str
    stdout: str = ""
    stderr: str = ""
    details: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 5: Run the unit test again**

Run:

```bash
python -m pytest tests/test_translation_pipeline_unit.py -q
```

Expected: PASS.

---

### Task 2: Add Zhipu API Client With Cache

**Files:**
- Create: `DatasetAndMethod/SecAwareCoder/translation_pipeline/zhipu_client.py`
- Modify: `DatasetAndMethod/SecAwareCoder/tests/test_translation_pipeline_unit.py`

- [ ] **Step 1: Add a test for local key loading without printing secrets**

Add:

```python
from pathlib import Path

from translation_pipeline.zhipu_client import load_zhipu_keys


def test_load_zhipu_keys_from_env_file(tmp_path):
    env_file = tmp_path / "zhipu.env"
    env_file.write_text("xyykey=abc\nlzhkey=def\n", encoding="utf-8")
    keys = load_zhipu_keys(env_file)
    assert keys == {"xyykey": "abc", "lzhkey": "def"}
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
python -m pytest tests/test_translation_pipeline_unit.py -q
```

Expected: FAIL because `zhipu_client.py` does not exist.

- [ ] **Step 3: Implement key loading and cache keys**

Create `load_zhipu_keys(env_path: Path) -> dict[str, str]`, `make_cache_key(payload: dict) -> str`, and `ZhipuTranslationClient.translate(prompt: str) -> str`.

Required behavior:

- Read `质朴api使用\质朴.env`.
- Prefer `lzhkey` if present, otherwise use the first available key.
- Never log or print the key.
- Store response cache files in `translation_work\cache\`.
- Default model should be `glm-4.7`.
- Default concurrency should start conservatively at `4`, even though the screenshot shows `GLM-4.7` supports higher concurrency.

- [ ] **Step 4: Run unit tests**

Run:

```bash
python -m pytest tests/test_translation_pipeline_unit.py -q
```

Expected: PASS. No real API call should happen in unit tests.

---

### Task 3: Add Prompt Builders And Code Extraction

**Files:**
- Create: `DatasetAndMethod/SecAwareCoder/translation_pipeline/prompts.py`
- Create: `DatasetAndMethod/SecAwareCoder/translation_pipeline/code_extract.py`
- Modify: `DatasetAndMethod/SecAwareCoder/tests/test_translation_pipeline_unit.py`

- [ ] **Step 1: Test code block extraction**

Add:

```python
from translation_pipeline.code_extract import extract_code_block


def test_extract_code_block_prefers_requested_language():
    response = "text\n```cpp\nint main(){return 0;}\n```\n```go\npackage main\n```"
    assert extract_code_block(response, "cpp") == "int main(){return 0;}"
```

- [ ] **Step 2: Test insecure prompt preserves bad behavior**

Add:

```python
from translation_pipeline.prompts import build_translation_prompt


def test_insecure_prompt_says_not_to_fix_vulnerability():
    prompt = build_translation_prompt(
        problem="demo problem",
        entry_point="foo",
        source_code="def foo(x): return eval(x)",
        source_field="Insecure Code",
        target_language="Go",
    )
    assert "do not fix" in prompt.lower()
    assert "preserve the insecure behavior" in prompt.lower()
```

- [ ] **Step 3: Implement `extract_code_block`**

Rules:

- Prefer fenced blocks matching `cpp`, `c++`, `go`, or `golang`.
- If no matching fence exists, return the first fenced block.
- If there is no fence, return stripped response text.

- [ ] **Step 4: Implement prompt builders**

Create:

- `build_translation_prompt(problem, entry_point, source_code, source_field, target_language)`
- `build_repair_prompt(problem, entry_point, source_code, translated_code, target_language, failure_text, mode)`

Secure prompt must say:

- Translate the Python function into target language.
- Keep the same function behavior.
- Use a predictable callable entry point.
- Return only code.

Insecure prompt must say:

- Translate the Python function into target language.
- Preserve the insecure or incorrect behavior.
- Do not repair validation, sanitization, exception handling, or security bugs.
- Return only code.

- [ ] **Step 5: Run unit tests**

Run:

```bash
python -m pytest tests/test_translation_pipeline_unit.py -q
```

Expected: PASS.

---

### Task 4: Build Lightweight Validators

**Files:**
- Create: `DatasetAndMethod/SecAwareCoder/translation_pipeline/validators.py`
- Modify: `DatasetAndMethod/SecAwareCoder/tests/test_translation_pipeline_unit.py`

- [ ] **Step 1: Add tests for command availability checks**

Add:

```python
from translation_pipeline.validators import command_exists


def test_command_exists_returns_boolean():
    assert isinstance(command_exists("python"), bool)
```

- [ ] **Step 2: Implement validator helpers**

Create helpers:

- `command_exists(command: str) -> bool`
- `run_command(args: list[str], cwd: Path, timeout: int) -> ValidationResult`
- `validate_cpp_program(code: str, task_id: str, mode: str) -> ValidationResult`
- `validate_go_program(code: str, task_id: str, mode: str) -> ValidationResult`

Rules:

- Write temporary files only under `translation_work\temp\`.
- C++ uses `g++ -std=c++17`.
- Go uses `go run`.
- If `g++` or `go` is missing, return `ok=False` with a clear error message instead of crashing.

- [ ] **Step 3: Define validation meaning**

For `Secure Code`:

- `ok=True` means compile succeeded and generated target-language test program passed.

For `Insecure Code`:

- `ok=True` means target-language output or failure mode matches the Python insecure baseline for the generated comparison cases.
- Do not repair insecure code into secure behavior.

- [ ] **Step 4: Run unit tests**

Run:

```bash
python -m pytest tests/test_translation_pipeline_unit.py -q
```

Expected: PASS.

---

### Task 5: Implement Dataset Runner

**Files:**
- Create: `DatasetAndMethod/SecAwareCoder/translation_pipeline/run_translate_dataset.py`
- Modify: `DatasetAndMethod/SecAwareCoder/tests/test_translation_pipeline_unit.py`

- [ ] **Step 1: Add test for output field naming**

Add:

```python
from translation_pipeline.run_translate_dataset import add_translation_fields


def test_add_translation_fields_keeps_original_fields():
    record = {"ID": "x", "Secure Code": "secure", "Insecure Code": "bad"}
    out = add_translation_fields(
        record,
        secure_cpp="cpp secure",
        secure_go="go secure",
        insecure_cpp="cpp bad",
        insecure_go="go bad",
        secure_cpp_result={"ok": True},
        secure_go_result={"ok": True},
        insecure_cpp_result={"ok": True},
        insecure_go_result={"ok": True},
    )
    assert out["Secure Code"] == "secure"
    assert out["Insecure Code"] == "bad"
    assert out["Secure Code C++"] == "cpp secure"
    assert out["Secure Code Go"] == "go secure"
    assert out["Insecure Code C++"] == "cpp bad"
    assert out["Insecure Code Go"] == "go bad"
```

- [ ] **Step 2: Implement CLI arguments**

`run_translate_dataset.py` should support:

```bash
python -m translation_pipeline.run_translate_dataset ^
  --data-path ..\CodeSecEval\SecEvaBase.json ^
  --output-path ..\..\translation_work\outputs\SecEvaBase.translated.json ^
  --model glm-4.7 ^
  --max-workers 4 ^
  --limit 5 ^
  --max-repair-attempts 2
```

Arguments:

- `--data-path`
- `--output-path`
- `--model`
- `--max-workers`
- `--limit`
- `--resume`
- `--max-repair-attempts`
- `--skip-api`

- [ ] **Step 3: Implement record processing**

For each record:

1. Translate `Secure Code` to C++.
2. Translate `Secure Code` to Go.
3. Translate `Insecure Code` to C++ with behavior-preserving insecure prompt.
4. Translate `Insecure Code` to Go with behavior-preserving insecure prompt.
5. Validate secure C++ and secure Go with functional tests.
6. Validate insecure C++ and insecure Go against Python insecure behavior where possible.
7. If secure validation fails, repair only the secure target code.
8. If insecure behavior validation fails, repair only for behavior preservation, not security.
9. Add result fields to the copied record.

- [ ] **Step 4: Write output safely**

Output rules:

- Never overwrite `SecEvaBase.json` or `SecEvalPlus.json`.
- Write to a temporary output file first, then replace the translated output.
- Preserve original field names and order as much as practical.
- Save per-record status in the output JSON so a failed item is visible instead of silently missing.

- [ ] **Step 5: Run unit tests**

Run:

```bash
python -m pytest tests/test_translation_pipeline_unit.py -q
```

Expected: PASS.

---

### Task 6: Add New-User README

**Files:**
- Create: `DatasetAndMethod/SecAwareCoder/translation_pipeline/README.md`

- [ ] **Step 1: Write README**

Include:

- What the tool does in plain language.
- Difference between `Secure Code` validation and `Insecure Code` behavior matching.
- Where generated files go: `D:\thecourceofdasi\safecodernew\translation_work\`.
- How to run a 5-item smoke test.
- How to run full translation after smoke test passes.
- How to clean temporary files while preserving outputs.

- [ ] **Step 2: Verify README paths**

Run:

```bash
Get-Content DatasetAndMethod\SecAwareCoder\translation_pipeline\README.md
```

Expected: readable Chinese or English text, no secret keys.

---

### Task 7: Smoke Test With Small Dataset Slice

**Files:**
- Generated output: `translation_work\outputs\SecEvaBase.translated.json`
- Generated logs: `translation_work\logs\`
- Generated cache: `translation_work\cache\`
- Generated temp files: `translation_work\temp\`

- [ ] **Step 1: Install missing dependencies under project work area if needed**

If `zhipuai` is missing, install with cache on D/project path:

```bash
python -m pip install zhipuai --cache-dir D:\thecourceofdasi\safecodernew\translation_work\downloads\pip-cache
```

- [ ] **Step 2: Run a five-item smoke test**

From `DatasetAndMethod/SecAwareCoder`:

```bash
python -m translation_pipeline.run_translate_dataset ^
  --data-path ..\CodeSecEval\SecEvaBase.json ^
  --output-path ..\..\translation_work\outputs\SecEvaBase.translated.json ^
  --model glm-4.7 ^
  --max-workers 4 ^
  --limit 5 ^
  --max-repair-attempts 2
```

Expected:

- Output JSON exists.
- Original dataset remains unchanged.
- Each processed item has C++ and Go fields for secure and insecure code.
- Secure code result fields show pass/fail details.
- Insecure code result fields show baseline-match pass/fail details.

- [ ] **Step 3: Inspect failure summaries**

Run:

```bash
python -c "import json; p=r'translation_work\outputs\SecEvaBase.translated.json'; d=json.load(open(p, encoding='utf-8')); print(len(d)); print(d[0].keys())"
```

Expected: command prints record count and includes translated fields.

- [ ] **Step 4: Clean temporary compile files**

Remove only disposable files under:

```text
D:\thecourceofdasi\safecodernew\translation_work\temp\
```

Keep:

- `translation_work\outputs\`
- `translation_work\cache\`
- `translation_work\logs\`

---

### Task 8: Full Dataset Run

**Files:**
- Output: `translation_work\outputs\SecEvaBase.translated.json`
- Output: `translation_work\outputs\SecEvalPlus.translated.json`

- [ ] **Step 1: Run full `SecEvaBase` translation**

```bash
python -m translation_pipeline.run_translate_dataset ^
  --data-path ..\CodeSecEval\SecEvaBase.json ^
  --output-path ..\..\translation_work\outputs\SecEvaBase.translated.json ^
  --model glm-4.7 ^
  --max-workers 4 ^
  --resume ^
  --max-repair-attempts 2
```

- [ ] **Step 2: Run full `SecEvalPlus` translation**

```bash
python -m translation_pipeline.run_translate_dataset ^
  --data-path ..\CodeSecEval\SecEvalPlus.json ^
  --output-path ..\..\translation_work\outputs\SecEvalPlus.translated.json ^
  --model glm-4.7 ^
  --max-workers 4 ^
  --resume ^
  --max-repair-attempts 2
```

- [ ] **Step 3: Produce a beginner-friendly summary**

Report:

- How many records were processed.
- How many secure C++ translations passed.
- How many secure Go translations passed.
- How many insecure C++ translations matched Python insecure behavior.
- How many insecure Go translations matched Python insecure behavior.
- Where outputs are saved.
- Which failures need manual review.

- [ ] **Step 4: Final cleanup**

Delete disposable temporary scripts and compile/run files created by the implementation. Keep reusable source files, JSON outputs, logs, and API cache unless the user explicitly asks to remove them.

---

## Self-Review

- Spec coverage: The plan covers both datasets, both secure and insecure source fields, C++ and Go targets, project-local `translation_work`, API usage through local Zhipu credentials, secure functional validation, insecure behavior matching, resume/cache behavior, and beginner-friendly reporting.
- Placeholder scan: The plan avoids placeholder tasks and gives exact paths, commands, and expected results.
- Type consistency: Field names are consistent across tasks: `Secure Code C++`, `Secure Code Go`, `Insecure Code C++`, `Insecure Code Go`, plus result dictionaries for each target/mode.
