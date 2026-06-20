# Docker Validators

This folder contains Docker build files for the current Python/C++/Go secure
code validation workflow.

## Images

| Language | Image used by scripts | Source |
|---|---|---|
| Python | `safecoder-python-validator:local` | Built from `python-validator/Dockerfile` |
| C++ | `safecoder-cpp-validator:local` | Built from `cpp-validator/Dockerfile` |
| Go | `golang:1.22` | Pulled from Docker Hub |

## Build

```powershell
docker build -t safecoder-python-validator:local `
  DatasetAndMethod/SecAwareCoder/translation_pipeline/docker/python-validator

docker build -t safecoder-cpp-validator:local `
  DatasetAndMethod/SecAwareCoder/translation_pipeline/docker/cpp-validator

docker pull golang:1.22
```

## Base Image Note

The Python and C++ validator Dockerfiles currently extend local Porta benchmark
runtime images:

```text
porta-bench-runtime-python3:latest
porta-bench-runtime-cpp:latest
```

That means a teammate must already have those base images locally, or must load
or rebuild them from the original benchmark environment before building the two
`safecoder-*` images.

We intentionally do not commit Docker image binary exports to GitHub, because
they are very large. GitHub should store the build files and scripts; large
image archives should be shared separately if needed.

