# SafeCoderNew: First Migration Snapshot

This repository records the first migration snapshot of a research project on
security-aware code generation and cross-language secure/insecure code
migration.

The project starts from Python secure/insecure paired samples and studies how
security-relevant differences can be transferred to target languages such as
C++, Go, Java, and JavaScript. The current snapshot includes datasets, baseline
analysis notes, translation workflow artifacts, and the first implementation of
an experience-transfer/self-evolution experiment.

## What This Repository Contains

```text
safecodernew/
├─ DatasetAndMethod/
│  ├─ CodeSecEval/
│  │  ├─ SecEvaBase.json
│  │  └─ SecEvalPlus.json
│  └─ SecAwareCoder/
│     ├─ main_streamsave.py
│     ├─ security_aware_code_generation_graph.py
│     ├─ prompts.py
│     ├─ tools_and_schemas.py
│     └─ execution_engine/
│
├─ baseline/
│  ├─ experience_transfer_experiment/
│  │  ├─ run_coset_eagle_experiment.py
│  │  ├─ test_coset_eagle_experiment.py
│  │  └─ out/
│  │     ├─ coset_eagle_self_evolve_30/
│  │     └─ coset_eagle_gated_30_r2/
│  ├─ baseline_分析与轻量测试报告.md
│  └─ 跨语言安全代码生成_baseline与整体实验设计.md
│
├─ translation_work/
│  ├─ outputs/
│  ├─ reports/
│  └─ manual_fix/
│
├─ docs/
├─ meeting_notes/
├─ ai建议/
└─ AGENTS.md
```

## Research Goal

The core question is not simply whether Python code can be translated into other
programming languages. Instead, the project focuses on whether the security
semantic difference between a secure Python implementation and an insecure
Python implementation can be preserved after migration.

Each original task has two tracks:

- **Secure track**: generate target-language code that is functionally correct
  and avoids the corresponding vulnerability.
- **Insecure track**: generate target-language code that preserves the expected
  vulnerable behavior or failure mode, instead of accidentally repairing it.

This dual-track setting is useful because it checks whether the model really
understands the security delta between the secure and insecure versions.

## Main Dataset

The main dataset used in this snapshot is CodeSecEval:

- `DatasetAndMethod/CodeSecEval/SecEvaBase.json`: base split, about 115 tasks.
- `DatasetAndMethod/CodeSecEval/SecEvalPlus.json`: plus split, about 140 tasks.

Important fields include:

- `ID`
- `Problem`
- `Entry_Point`
- `Insecure Code`
- `Secure Code`
- `Test`
- `Test-FP`
- `Test-SP`

## First Migration Work

The local project contains translation and validation work for secure and
insecure code migration. The target languages considered in the broader project
are:

- C++
- Go
- Java
- JavaScript

The migration workflow follows this high-level loop:

```text
Python Secure/Insecure paired sample
  -> extract security-delta experience
  -> generate target-language Secure/Insecure code
  -> compile and run in the target-language environment
  -> validate Secure and Insecure separately
  -> repair failed cases
  -> record validated results and failure types
```

Large local runtime folders, downloaded toolchains, sandboxes, caches, and API
logs are intentionally excluded from this public repository.

## Experience Transfer and Self-Evolution

The folder `baseline/experience_transfer_experiment/` contains the first compact
implementation of the experience-transfer experiment.

The experiment compares several memory and experience-use strategies on a
30-task test set. The strict metric is `Func+Sec`, which means the generated
code passes both functionality checks and security checks.

Previous 30-task results are stored in:

```text
baseline/experience_transfer_experiment/out/coset_eagle_self_evolve_30/report.md
```

Key previous results:

| Variant | Func+Sec |
|---|---:|
| `no_memory` | 13 / 30 |
| `script_codeseceval` | 15 / 30 |
| `secodeplt_memory` | 16 / 30 |
| `coset_eagle_clean_evolved` | 17 / 30 |

The newer gated evolution run is stored in:

```text
baseline/experience_transfer_experiment/out/coset_eagle_gated_30_r2/
```

It adds a Claude-inspired evidence gate:

1. Run the current best experience on 30 tasks.
2. Read failed cases.
3. Ask the model to summarize candidate general rules.
4. Select only a small number of candidate updates.
5. Re-run the 30 tasks with the candidate rules.
6. Promote the candidate rules only if the strict score improves without
   functional or security regression.
7. Put rejected rules into a rejected buffer.

Gated evolution result:

| Stage | Func+Sec |
|---|---:|
| `coset_eagle_gate_best_r0` | 14 / 30 |
| `coset_eagle_gate_candidate_r1` | 17 / 30 |
| `coset_eagle_gate_best_r1` | 17 / 30 |
| `coset_eagle_gate_candidate_r2` | 16 / 30 |
| Final best | 17 / 30 |

Round 1 was accepted because it improved the strict score from `14/30` to
`17/30`. Round 2 was rejected because functionality regressed from 28 passing
tasks to 27 passing tasks.

## How to Run the Compact Experiment

From the repository root:

```powershell
python -m unittest baseline.experience_transfer_experiment.test_coset_eagle_experiment
```

The main experiment script is:

```powershell
python baseline/experience_transfer_experiment/run_coset_eagle_experiment.py `
  --out_name coset_eagle_gated_30_r2 `
  --se_train_size 200 `
  --code_train_size 30 `
  --test_size 30 `
  --workers 3 `
  --repair_iters 3 `
  --max_tokens 4096 `
  --api_timeout 180 `
  --variants coset_eagle_gated `
  --evolution_rounds 2 `
  --edit_budget 3
```

Running the full experiment requires a compatible model API key. Do not commit
API keys or `.env` files.

## Security and Privacy Notes

This public snapshot intentionally excludes:

- API keys and `.env` files.
- Local downloaded compilers/runtimes.
- Virtual environments.
- Large sandbox folders.
- Temporary logs and cache directories.
- Archive files used only for local unpacking.

Generated code should be treated as untrusted. Run it only inside an expected
isolated environment.

## Current Status

This is the first public migration snapshot. It records:

- CodeSecEval data and related method code.
- Cross-language migration work artifacts.
- Baseline analysis documents.
- A compact experience-transfer/self-evolution experiment.
- A gated two-round evolution run on 30 tasks.

Future work may add cleaner release packages, more target-language validation
summaries, and paper-ready experiment tables.
