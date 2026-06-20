# SafeCoderNew

This repository contains the reproducible workflow for the current project:

```text
Self-evolving experience driven multilingual secure code generation
```

In simple terms, the project learns reusable security-generation experience
from security-related code data, then uses that experience to generate secure
Python, C++, and Go code. The generated code is validated in Docker instead of
being trusted directly.

## What Is Included

The repository includes:

- The fixed `SecEvoBasePlus` dataset.
- The Python/C++/Go secure-code validation pipeline.
- Dockerfiles for the Python and C++ validators.
- The Go validator configuration based on `golang:1.22`.
- Baseline and Ours/SCT-Agent runner scripts.
- Monitoring and resume scripts for long full-matrix runs.

The repository does not include:

- API keys.
- Local Docker image binary exports.
- Large generated logs, caches, temporary files, or local result dumps.
- Your Docker Desktop VHDX file.

## Dataset

The fixed dataset is stored here:

```text
SecEvoBasePlus/
  Base/
    Python_Base.json
    Cpp_Base.json
    Go_Base.json
    Java_Base.json
    JS_Base.json
  Plus/
    Python_Plus.json
    Cpp_Plus.json
    Go_Plus.json
    Java_Plus.json
    JS_Plus.json
```

Current scale:

| Split | Python | C++ | Go | Java | JS |
|---|---:|---:|---:|---:|---:|
| Base | 115 | 115 | 115 | 116 | 116 |
| Plus | 140 | 140 | 140 | 140 | 140 |

The public experiment currently fixes Docker validation for Python, C++, and
Go. Java and JS data are included, but their Docker validation images are not
yet fixed in this repository.

## Environment Setup

Use PowerShell on Windows.

1. Clone the repository.

```powershell
git clone https://github.com/smallrabbit490/safecodernew.git
cd safecodernew
```

2. Create a local environment file.

```powershell
Copy-Item env.example.ps1 env.local.ps1
notepad env.local.ps1
```

Fill in your own key:

```powershell
$env:ZHIPU_API_KEY = "<your-zhipu-api-key>"
```

Do not commit `env.local.ps1`.

3. Load the environment.

```powershell
. .\env.local.ps1
```

Beginner note: this only sets temporary environment variables for the current
PowerShell window. It does not write your API key into the repository.

## Docker Setup

Docker Desktop must be running.

Build the local validator images:

```powershell
docker build -t safecoder-python-validator:local `
  DatasetAndMethod/SecAwareCoder/translation_pipeline/docker/python-validator

docker build -t safecoder-cpp-validator:local `
  DatasetAndMethod/SecAwareCoder/translation_pipeline/docker/cpp-validator

docker pull golang:1.22
```

Important: the Python and C++ Dockerfiles extend these base images:

```text
porta-bench-runtime-python3:latest
porta-bench-runtime-cpp:latest
```

So a teammate must have those base images locally before building
`safecoder-python-validator:local` and `safecoder-cpp-validator:local`. If they
do not have them, share the original Porta benchmark runtime images separately
or rebuild those base images from the original benchmark environment first.

The validator images are intentionally not uploaded as image binaries. The
Dockerfiles are uploaded instead, so every teammate can rebuild the same
environment locally.

Current validator images:

| Language | Image |
|---|---|
| Python | `safecoder-python-validator:local` |
| C++ | `safecoder-cpp-validator:local` |
| Go | `golang:1.22` |

## Light Verification

After loading `env.local.ps1`, run the unit tests:

```powershell
python -m unittest `
  DatasetAndMethod.SecAwareCoder.tests.test_translation_pipeline_unit `
  baseline.experience_transfer_experiment.test_language_method_matrix
```

These tests check the core runner/validator wiring without launching the full
expensive experiment.

## Full Secure Matrix Run

The full current run is:

```text
Base + Plus
Python + C++ + Go
9 baselines + Ours/SCT-Agent
Secure-only generation and validation
```

Expected total rows:

```text
7650 = (115 + 115 + 115 + 140 + 140 + 140) * 10 methods
```

Start or resume the guarded sharded run:

```powershell
. .\env.local.ps1
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\translation_work\admin_tools\resume_full_secure_matrix.ps1
```

This script:

- Keeps at most 3 shard processes running at once.
- Skips rows that already exist.
- Starts the next unfinished shard when one shard finishes.
- Writes progress logs under `translation_work/monitored_full_run/`.

Beginner note: a shard means one smaller part of the whole experiment, for
example `Base + C++` or `Plus + Go`.

## Monitoring

Start the resource monitor:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\translation_work\admin_tools\resource_monitor_loop.ps1
```

Important logs:

```text
translation_work/monitored_full_run/logs/resource_monitor.csv
translation_work/monitored_full_run/logs/resume_scheduler.log
translation_work/monitored_full_run/logs/shards/
```

The monitor records:

- D drive free/used space.
- Memory usage.
- Docker VHDX size.
- Docker resource summary.
- Per-shard row counts.

## Docker VHDX Space Control

Docker Desktop on Windows stores Linux images, container layers, volumes, and
temporary writes in a dynamic VHDX file. In this project the common path is:

```text
D:\DockerDesktopLocal\wsl-data\disk\docker_data.vhdx
```

If your Docker Desktop uses a different path, set:

```powershell
$env:DOCKER_DESKTOP_VHDX = "D:\your\path\docker_data.vhdx"
```

Why this matters: Docker containers may delete their internal files, but the
Windows-side VHDX file does not always shrink automatically. That is why the
runner uses short-lived containers, explicit timeout cleanup, mounted temp/cache
directories, and output length limits.

Check current Docker size:

```powershell
Get-Item $env:DOCKER_DESKTOP_VHDX |
  Select-Object FullName,@{n='SizeGB';e={[math]::Round($_.Length/1GB,3)}},LastWriteTime

docker system df -v
docker ps
```

If Docker resources are small but the VHDX is still huge, compact it only after
stopping Docker work:

```powershell
wsl -d docker-desktop -- sh -lc "fstrim -av 2>&1 || true"

Start-Process powershell -Verb RunAs -ArgumentList `
  "-NoProfile","-ExecutionPolicy","Bypass","-File",`
  ".\translation_work\admin_tools\compact_docker_vhdx_admin.ps1"
```

Do not directly delete `docker_data.vhdx` unless you intentionally want to reset
Docker Desktop images, containers, volumes, and internal state.

## Output Locations

Full-matrix outputs are written under:

```text
baseline/experience_transfer_experiment/out/
```

Runtime logs and monitor files are written under:

```text
translation_work/monitored_full_run/
```

Large generated outputs are ignored by Git by default. If a result should be
shared, move a compact report or summary JSON into a stable documentation folder
instead of committing raw large logs.

## Main Commands Summary

```powershell
# 1. Load local API/Docker environment.
. .\env.local.ps1

# 2. Build validator images.
docker build -t safecoder-python-validator:local `
  DatasetAndMethod/SecAwareCoder/translation_pipeline/docker/python-validator
docker build -t safecoder-cpp-validator:local `
  DatasetAndMethod/SecAwareCoder/translation_pipeline/docker/cpp-validator
docker pull golang:1.22

# 3. Run lightweight tests.
python -m unittest `
  DatasetAndMethod.SecAwareCoder.tests.test_translation_pipeline_unit `
  baseline.experience_transfer_experiment.test_language_method_matrix

# 4. Start monitor.
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\translation_work\admin_tools\resource_monitor_loop.ps1

# 5. Start or resume full run.
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\translation_work\admin_tools\resume_full_secure_matrix.ps1
```

## Safety Rules

- Do not commit API keys, `.env` files, or `env.local.ps1`.
- Treat generated code as untrusted; run it only in Docker or a sandbox.
- Keep temporary files under `translation_work/`.
- Do not use `docker image prune -a` if you need to preserve old experiment
  images.
- Do not delete the Docker VHDX directly during normal cleanup.
