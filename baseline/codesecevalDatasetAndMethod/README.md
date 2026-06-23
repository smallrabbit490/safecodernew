# CodeSecEval Baseline Package Setup and Re-evaluation Guide

This directory is the local baseline workspace used for CodeSecEval, CWEval, SeCodePLT/SLP experience data, and baseline method runners.

The large downloaded archives and unpacked third-party folders are intentionally not committed to Git. They should be placed locally under `baseline/` before running experiments.

## 1. Required Local Packages

Place these archives under:

```text
D:\thecourceofdasi\safecodernew\baseline\
```

Expected package layout:

| Package | Purpose | Git status |
|---|---|---|
| `codesecevalDatasetAndMethod.zip` | CodeSecEval dataset and baseline method workspace | ignored |
| `cweval.zip` | CWEval reference dataset/workspace | ignored |
| `SeCodePLT-main.zip` | SLP/SeCodePLT vulnerable-patched experience dataset | ignored |

After extraction, the important paths are:

```text
baseline/codesecevalDatasetAndMethod/
baseline/cweval/
baseline/SeCodePLT-main/
```

Do not commit local API keys, `.env` files, virtual environments, logs, or generated run folders.

## 2. Current Core Changes

### Prompt changes

The current prompt flow has been updated for Secure-only multi-language code generation.

Main prompt runner:

```text
baseline/experience_transfer_experiment/run_language_method_matrix.py
```

Key changes:

- Removed the prompt header `You are running the ... baseline adapter`.
- Removed the explicit `Track: secure` line.
- Redacted CWE labels from model-visible problem text.
- Kept task IDs only in output records for traceability, not in prompts.
- Added target-language-specific generation strategy text.
- Kept Python mostly unchanged because Python does not need a compiled harness contract.
- Specialized C++ and Go prompts for harness execution:
  - exact entry point must be preserved;
  - no `main` function;
  - no demo-only code;
  - no signature/type changes;
  - use the extracted harness signature and context when available.

For Ours / SCT-Agent, the prompt now uses:

- evidence-gated security rules;
- retrieved SLP/SeCodePLT vulnerable-patched experience;
- no model-visible CWE type labels;
- compact self-check guidance before final code.

### Dataset / experience source changes

Previous small experiments used a fixed small SeCodePLT sample size, such as 30, 100, or 200.

The current flow uses the full available SLP/SeCodePLT vulnerable-patched experience pool:

```powershell
--se_train_size 0
```

The current fixed local package contains:

```text
SeCodePLT / SLP usable vulnerable-patched pairs: 1411
```

Keep `--se_train_size 0` so the script uses all 1411 usable pairs.

Relevant dataset path:

```text
baseline/SeCodePLT-main/virtue_code_eval/data/safety/secodeplt/data.json
```

Relevant selection logic:

```text
baseline/experience_transfer_experiment/run_experiment.py
```

### Evaluation changes

The old C++/Go smoke runner only checked whether generated code could compile/run as a standalone program. That was too weak for our final evaluation because generated code could pass a shallow build check without matching the real translated task harness.

The current runner does this instead:

```text
generated C++ / Go code
  -> injected into saved translated task harness
  -> compiled in Docker/local validator
  -> Function and Secure are split by Test-FP and Test-SP
```

This makes Function and Secure separate metrics:

| Metric | Meaning |
|---|---|
| `Function` | whether normal functional tests pass |
| `Secure` | whether security tests pass |
| `Function+Secure` | whether both pass |
| `PRCS` | production-readiness composite score |
| `EQS` | engineering-quality score without Function/Secure points |

## 3. Environment Setup

Run from the repository root:

```powershell
cd D:\thecourceofdasi\safecodernew

$env:PYTHONPATH="D:\thecourceofdasi\safecodernew\DatasetAndMethod\SecAwareCoder"
$env:SAFECODER_PYTHON_DOCKER_IMAGE="safecoder-python-validator:local"
$env:SAFECODER_CPP_DOCKER_IMAGE="safecoder-cpp-validator:local"
$env:SAFECODER_GO_DOCKER_IMAGE="golang:1.22"

$env:ZHIPU_API_KEY="<your key>"
$env:ZHIPU_API_BASE="https://open.bigmodel.cn/api/paas/v4"
```

Build missing Docker images if needed:

```powershell
docker build -t safecoder-python-validator:local DatasetAndMethod/SecAwareCoder/translation_pipeline/docker/python-validator
docker build -t safecoder-cpp-validator:local DatasetAndMethod/SecAwareCoder/translation_pipeline/docker/cpp-validator
docker pull golang:1.22
```

## 4. What Needs to Be Re-run

Because prompts and C++/Go evaluation were changed, regenerate/re-evaluate these:

1. C++ baseline results.
2. Go baseline results.
3. Ours / SCT-Agent results using full SLP/SeCodePLT experience.
4. Any summary table that reports Function, Secure, Function+Secure, PRCS, or EQS.

Python does not need urgent prompt regeneration unless it is used in the same final comparison table. If Python is included in a final table, re-run it for consistency.

## 5. Smoke Checks

Run unit tests:

```powershell
cd D:\thecourceofdasi\safecodernew\baseline\experience_transfer_experiment
python -m unittest test_language_method_matrix
```

Run a small C++ prompt/evaluation check:

```powershell
python run_language_method_matrix.py `
  --dataset-root D:\thecourceofdasi\safecodernew\SecEvoBasePlus `
  --subsets Base `
  --languages cpp `
  --limit 2 `
  --include-ours `
  --only-ours `
  --out-name smoke_cpp_ours_no_cwe `
  --model glm-5.1 `
  --max-tokens 4096 `
  --temperature 0 `
  --retries 3
```

Run a small baseline matrix:

```powershell
python run_language_method_matrix.py `
  --dataset-root D:\thecourceofdasi\safecodernew\SecEvoBasePlus `
  --subsets Base `
  --languages cpp go `
  --limit 2 `
  --out-name smoke_cpp_go_9_baselines `
  --model glm-5.1 `
  --max-tokens 4096 `
  --temperature 0 `
  --retries 3
```

## 6. Full Evaluation Commands

Run Ours / SCT-Agent with full SLP/SeCodePLT experience:

```powershell
cd D:\thecourceofdasi\safecodernew\baseline\experience_transfer_experiment

python run_coset_eagle_experiment.py `
  --model glm-5.1 `
  --workers 3 `
  --max_tokens 4096 `
  --se_train_size 0 `
  --code_train_size 30 `
  --test_size 30 `
  --repair_iters 3 `
  --out_name coset_eagle_final_gated `
  --variants no_memory,script_codeseceval,secodeplt_memory,coset_eagle_final_gated
```

Run language/method matrix on Base and Plus:

```powershell
python run_language_method_matrix.py `
  --dataset-root D:\thecourceofdasi\safecodernew\SecEvoBasePlus `
  --subsets Base Plus `
  --languages python cpp go `
  --out-name full_secure_language_method_matrix `
  --model glm-5.1 `
  --max-tokens 4096 `
  --temperature 0 `
  --retries 3
```

If API errors occur, re-run only failed/API-error rows with the retry helper scripts already in `baseline/experience_transfer_experiment/`.

## 7. How to Read Results

Main outputs are written under:

```text
baseline/experience_transfer_experiment/out/<out_name>/
```

Important files:

| File | Purpose |
|---|---|
| `language_method_matrix_report.md` | human-readable method table |
| `summary.json` | grouped metrics |
| `rows.jsonl` | one row per method/language/task |
| `language_methods/<subset>/<language>/*.jsonl` | per-method detailed results |

For final reporting, split tables by:

- dataset: Base vs Plus;
- language: Python, C++, Go;
- method group: traditional baseline, agent baseline, Ours.

Use these columns:

```text
Function
Secure
Function+Secure
PRCS
EQS
Generation Errors
```

## 8. Pull Request Review Checklist

Before accepting a run as final:

- Confirm prompts do not expose CWE labels to the model.
- Confirm C++/Go outputs are evaluated through the translated harness when available.
- Confirm Python/C++/Go tables are not mixed into one unlabelled aggregate.
- Confirm Base and Plus are reported separately.
- Confirm API errors are counted separately and re-run before final statistics.
- Confirm no API keys or local `.env` files are committed.
