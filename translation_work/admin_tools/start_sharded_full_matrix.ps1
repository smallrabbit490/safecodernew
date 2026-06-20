$ErrorActionPreference = "Stop"

$project = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$exp = Join-Path $project "baseline\experience_transfer_experiment"
$runRoot = Join-Path $project "translation_work\monitored_full_run"
$logRoot = Join-Path $runRoot "logs\shards"
$pidPath = Join-Path $runRoot "shard_pids.json"
$outPrefix = "full_secure_sharded_guarded"

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

$env:PYTHONPATH = Join-Path $project "DatasetAndMethod\SecAwareCoder"
$env:ZHIPU_API_BASE = if ($env:ZHIPU_API_BASE) { $env:ZHIPU_API_BASE } else { "https://open.bigmodel.cn/api/paas/v4" }
$env:SAFECODER_CPP_BACKEND = "docker"
$env:SAFECODER_GO_BACKEND = "docker"
$env:SAFECODER_CPP_DOCKER_IMAGE = "safecoder-cpp-validator:local"
$env:SAFECODER_GO_DOCKER_IMAGE = "golang:1.22"
$env:SAFECODER_PYTHON_DOCKER_IMAGE = "safecoder-python-validator:local"
$env:SAFECODER_CPP_DOCKER_ENTRYPOINT = ""
$env:SAFECODER_GO_DOCKER_ENTRYPOINT = "__default__"
$env:SAFECODER_MAX_STORED_TEXT_CHARS = "2000"
$env:SAFECODER_MAX_VALIDATOR_OUTPUT_CHARS = "2000"
$env:TEMP = Join-Path $project "translation_work\temp"
$env:TMP = Join-Path $project "translation_work\temp"
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null

$shards = @()
foreach ($subset in @("Base", "Plus")) {
    foreach ($language in @("python", "cpp", "go")) {
        $shards += [pscustomobject]@{Subset=$subset; Language=$language}
    }
}

$started = @()
foreach ($shard in $shards) {
    while ($true) {
        $startedPids = @($started | Select-Object -ExpandProperty pid -ErrorAction SilentlyContinue)
        $aliveCount = if ($startedPids.Count -gt 0) { @(Get-Process -Id $startedPids -ErrorAction SilentlyContinue).Count } else { 0 }
        if ($aliveCount -lt 3) { break }
        Start-Sleep -Seconds 30
    }
    $name = "$outPrefix`_$($shard.Subset.ToLower())_$($shard.Language)"
    $stdout = Join-Path $logRoot "$name.log"
    $stderr = Join-Path $logRoot "$name.err.log"
    $args = @(
        "run_language_method_matrix.py",
        "--dataset-root", (Join-Path $project "SecEvoBasePlus"),
        "--subset", $shard.Subset,
        "--languages", $shard.Language,
        "--limit", "0",
        "--include-ours",
        "--out-name", $name,
        "--model", "glm-5.1",
        "--max-tokens", "2048",
        "--temperature", "0",
        "--retries", "2"
    )
    $proc = Start-Process -FilePath "python" -ArgumentList $args -WorkingDirectory $exp -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -WindowStyle Hidden
    $started += [pscustomobject]@{
        pid = $proc.Id
        subset = $shard.Subset
        language = $shard.Language
        out_name = $name
        stdout = $stdout
        stderr = $stderr
        started_at = (Get-Date -Format o)
    }
    Start-Sleep -Seconds 2
}

$started | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $pidPath -Encoding UTF8
$started | Format-Table -AutoSize
Write-Host "Shard PID file: $pidPath"
