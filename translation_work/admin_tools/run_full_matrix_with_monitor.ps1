$ErrorActionPreference = "Stop"

$project = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$exp = Join-Path $project "baseline\experience_transfer_experiment"
$runRoot = Join-Path $project "translation_work\monitored_full_run"
$logRoot = Join-Path $runRoot "logs"
$outName = "full_secure_baselines_base_plus_3lang_guarded"
$monitorLog = Join-Path $logRoot "resource_monitor.csv"
$runLog = Join-Path $logRoot "full_matrix_run.log"
$pidFile = Join-Path $runRoot "pids.json"

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

$env:PYTHONPATH = Join-Path $project "DatasetAndMethod\SecAwareCoder"
$env:ZHIPU_API_BASE = if ($env:ZHIPU_API_BASE) { $env:ZHIPU_API_BASE } else { "https://open.bigmodel.cn/api/paas/v4" }
$env:SAFECODER_CPP_BACKEND = "docker"
$env:SAFECODER_GO_BACKEND = "docker"
$env:SAFECODER_CPP_DOCKER_IMAGE = "safecoder-cpp-validator:local"
$env:SAFECODER_GO_DOCKER_IMAGE = "golang:1.22"
$env:SAFECODER_MAX_STORED_TEXT_CHARS = "2000"
$env:SAFECODER_MAX_VALIDATOR_OUTPUT_CHARS = "2000"

function Get-DirSizeGB($path) {
    if (-not (Test-Path -LiteralPath $path)) { return 0 }
    $sum = (Get-ChildItem -LiteralPath $path -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    return [math]::Round(($sum / 1GB), 3)
}

function Start-Monitor {
    param(
        [string]$Project,
        [string]$RunRoot,
        [string]$MonitorLog
    )
    Start-Job -Name "safecoder_resource_monitor" -ScriptBlock {
        param($Project, $RunRoot, $MonitorLog)
        "timestamp,d_free_gb,d_used_gb,project_gb,translation_work_gb,baseline_out_gb,run_root_gb,vhdx_logical_gb,docker_images_line" |
            Set-Content -LiteralPath $MonitorLog -Encoding UTF8
        while ($true) {
            try {
                $drive = Get-PSDrive -Name D
                $vhdxPath = if ($env:DOCKER_DESKTOP_VHDX) { $env:DOCKER_DESKTOP_VHDX } else { "D:\DockerDesktopLocal\wsl-data\disk\docker_data.vhdx" }
                $vhdx = Get-Item -LiteralPath $vhdxPath -ErrorAction SilentlyContinue
                $dockerLine = ""
                try {
                    $dockerLine = (docker system df --format "{{.Type}} {{.TotalCount}} {{.Size}} {{.Reclaimable}}" 2>$null | Out-String).Trim().Replace("`r"," ").Replace("`n","; ")
                } catch {
                    $dockerLine = "docker_unavailable"
                }
                function SizeGB($path) {
                    if (-not (Test-Path -LiteralPath $path)) { return 0 }
                    $sum = (Get-ChildItem -LiteralPath $path -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
                    return [math]::Round(($sum / 1GB), 3)
                }
                $row = [pscustomobject]@{
                    timestamp = (Get-Date -Format o)
                    d_free_gb = [math]::Round($drive.Free / 1GB, 3)
                    d_used_gb = [math]::Round($drive.Used / 1GB, 3)
                    project_gb = SizeGB $Project
                    translation_work_gb = SizeGB (Join-Path $Project "translation_work")
                    baseline_out_gb = SizeGB (Join-Path $Project "baseline\experience_transfer_experiment\out")
                    run_root_gb = SizeGB $RunRoot
                    vhdx_logical_gb = if ($vhdx) { [math]::Round($vhdx.Length / 1GB, 3) } else { 0 }
                    docker_images_line = $dockerLine
                }
                $line = ($row.timestamp, $row.d_free_gb, $row.d_used_gb, $row.project_gb, $row.translation_work_gb, $row.baseline_out_gb, $row.run_root_gb, $row.vhdx_logical_gb, ('"' + $row.docker_images_line.Replace('"','""') + '"')) -join ","
                Add-Content -LiteralPath $MonitorLog -Value $line -Encoding UTF8
            } catch {
                Add-Content -LiteralPath $MonitorLog -Value "$(Get-Date -Format o),MONITOR_ERROR,$($_.Exception.Message)" -Encoding UTF8
            }
            Start-Sleep -Seconds 60
        }
    } -ArgumentList $Project, $RunRoot, $MonitorLog
}

$monitorJob = Start-Monitor -Project $project -RunRoot $runRoot -MonitorLog $monitorLog

$argList = @(
    "run_language_method_matrix.py",
    "--dataset-root", (Join-Path $project "SecEvoBasePlus"),
    "--subsets", "Base", "Plus",
    "--languages", "python", "cpp", "go",
    "--limit", "0",
    "--include-ours",
    "--out-name", $outName,
    "--model", "glm-5.1",
    "--max-tokens", "2048",
    "--temperature", "0",
    "--retries", "2"
)

$process = Start-Process -FilePath "python" -ArgumentList $argList -WorkingDirectory $exp -RedirectStandardOutput $runLog -RedirectStandardError (Join-Path $logRoot "full_matrix_run.err.log") -PassThru -WindowStyle Hidden

@{
    run_pid = $process.Id
    monitor_job_id = $monitorJob.Id
    out_name = $outName
    run_log = $runLog
    monitor_log = $monitorLog
    started_at = (Get-Date -Format o)
} | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $pidFile -Encoding UTF8

Write-Host "Started full matrix run PID=$($process.Id)"
Write-Host "Run log: $runLog"
Write-Host "Monitor log: $monitorLog"
Write-Host "PID file: $pidFile"
