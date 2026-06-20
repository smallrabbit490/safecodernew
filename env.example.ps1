# Copy this file to env.local.ps1 and fill in your own API key.
# Do not commit env.local.ps1.

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

$env:PYTHONPATH = Join-Path $ProjectRoot "DatasetAndMethod\SecAwareCoder"

# GLM 5.1 API settings.
$env:ZHIPU_API_BASE = "https://open.bigmodel.cn/api/paas/v4"
$env:ZHIPU_API_KEY = "<your-zhipu-api-key>"

# Docker validator settings.
$env:SAFECODER_PYTHON_DOCKER_IMAGE = "safecoder-python-validator:local"
$env:SAFECODER_CPP_DOCKER_IMAGE = "safecoder-cpp-validator:local"
$env:SAFECODER_GO_DOCKER_IMAGE = "golang:1.22"
$env:SAFECODER_CPP_BACKEND = "docker"
$env:SAFECODER_GO_BACKEND = "docker"
$env:SAFECODER_CPP_DOCKER_ENTRYPOINT = ""
$env:SAFECODER_GO_DOCKER_ENTRYPOINT = "__default__"

# Keep temp/cache on this project drive, not C:.
$env:TEMP = Join-Path $ProjectRoot "translation_work\temp"
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null

# Optional: set this if Docker Desktop stores the VHDX somewhere else.
# $env:DOCKER_DESKTOP_VHDX = "D:\DockerDesktopLocal\wsl-data\disk\docker_data.vhdx"

# Keep logs compact during large runs.
$env:SAFECODER_MAX_STORED_TEXT_CHARS = "2000"
$env:SAFECODER_MAX_VALIDATOR_OUTPUT_CHARS = "2000"
