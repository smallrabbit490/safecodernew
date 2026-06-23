# Summary

This PR documents and updates the current Secure-only evaluation flow for the CodeSecEval baseline workspace.

The main changes are:

- update the prompt format used by the language/method matrix runner;
- switch Ours / SCT-Agent to full SLP/SeCodePLT experience-pool usage via `--se_train_size 0`;
- evaluate C++ and Go through the translated task harness instead of a shallow standalone compile/run check;
- add a setup and re-evaluation README for the baseline package workspace.

# What Changed

## 1. Prompt changes

The prompt now avoids unnecessary benchmark-facing wording and removes model-visible CWE leakage.

Updated behavior:

- removes `You are running the ... baseline adapter`;
- removes explicit `Track: secure`;
- redacts `CWE-xxx` labels from the problem text shown to models;
- keeps task IDs only in output records, not in prompts;
- keeps Python mostly unchanged;
- specializes C++ and Go prompt wording for compiled harness execution;
- renames `Method behavior` to `Generation strategy`.

For C++ and Go, prompts now explicitly tell the model to:

- preserve the exact callable entry point;
- not generate `main`;
- not write demo-only code;
- not change parameter or return types;
- not redefine harness-provided custom types;
- use the extracted harness signature and surrounding context.

## 2. Dataset / experience-source changes

The Ours / SCT-Agent flow now defaults to the full usable SLP/SeCodePLT vulnerable-patched experience pool:

```powershell
--se_train_size 0
```

The current fixed local package contains 1411 usable vulnerable-patched pairs. Keep `--se_train_size 0` so the script uses all 1411 pairs.

The large ZIP packages and extracted third-party baseline directories remain ignored by Git. The README explains where teammates should place them locally.

## 3. Evaluation changes

C++ and Go evaluation no longer relies only on a standalone compile/run sanity check.

The current flow is:

```text
generated C++ / Go code
  -> injected into saved translated task harness
  -> compiled and run in the configured validator
  -> Function and Secure are split by Test-FP and Test-SP
```

This makes the following metrics meaningful for C++/Go:

- Function
- Secure
- Function+Secure
- PRCS
- EQS
- Generation Errors

# What Needs to Be Re-run

Because both prompts and C++/Go evaluation semantics changed, the following results should be regenerated:

1. C++ baseline results.
2. Go baseline results.
3. Ours / SCT-Agent results using full SLP/SeCodePLT experience.
4. Any summary table that reports Function, Secure, Function+Secure, PRCS, or EQS.

Python does not urgently need regeneration unless it is included in the final comparative table. If Python is included, rerun it for consistency.

# How to Evaluate

Run the core unit test:

```powershell
cd D:\thecourceofdasi\safecodernew\baseline\experience_transfer_experiment
python -m unittest test_language_method_matrix
```

Run a small Ours-only smoke test:

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

Run the main language/method matrix:

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

# Validation

Fresh local validation:

```text
python -m unittest test_language_method_matrix
Ran 20 tests in 0.452s
OK
```

# Notes for Reviewers

- Do not commit API keys or `.env` files.
- Do not commit the large ZIP archives or unpacked third-party baseline packages.
- Check that generated prompts do not expose CWE labels to the model.
- Report Base and Plus separately.
- Report Python, C++, and Go separately.
