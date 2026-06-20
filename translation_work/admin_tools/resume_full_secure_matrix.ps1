$ErrorActionPreference = "Continue"

$project = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$exp = Join-Path $project "baseline\experience_transfer_experiment"
$outRoot = Join-Path $exp "out"
$runRoot = Join-Path $project "translation_work\monitored_full_run"
$logRoot = Join-Path $runRoot "logs"
$shardLogRoot = Join-Path $logRoot "shards"
$schedulerLog = Join-Path $logRoot "resume_scheduler.log"
$schedulerPidFile = Join-Path $runRoot "resume_scheduler_pid.txt"
$maxConcurrent = 3

New-Item -ItemType Directory -Force -Path $shardLogRoot | Out-Null
$PID | Set-Content -LiteralPath $schedulerPidFile -Encoding ASCII

$env:PYTHONPATH = Join-Path $project "DatasetAndMethod\SecAwareCoder"
$env:ZHIPU_API_BASE = "https://open.bigmodel.cn/api/paas/v4"
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
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null

$shards = @(
  @{ Name = "full_secure_sharded_guarded_base_python"; Subset = "Base"; Language = "python"; Expected = 1150 },
  @{ Name = "full_secure_sharded_guarded_base_cpp";    Subset = "Base"; Language = "cpp";    Expected = 1150 },
  @{ Name = "full_secure_sharded_guarded_base_go";     Subset = "Base"; Language = "go";     Expected = 1150 },
  @{ Name = "full_secure_sharded_guarded_plus_python"; Subset = "Plus"; Language = "python"; Expected = 1400 },
  @{ Name = "full_secure_sharded_guarded_plus_cpp";    Subset = "Plus"; Language = "cpp";    Expected = 1400 },
  @{ Name = "full_secure_sharded_guarded_plus_go";     Subset = "Plus"; Language = "go";     Expected = 1400 }
)

function Write-SchedulerLog($message) {
  $line = "$(Get-Date -Format o) $message"
  Add-Content -LiteralPath $schedulerLog -Value $line -Encoding UTF8
}

function Count-ShardRows($name) {
  $dir = Join-Path $outRoot $name
  if (-not (Test-Path -LiteralPath $dir)) { return 0 }
  $methodDir = Join-Path $dir "Base\language_methods"
  if (-not (Test-Path -LiteralPath $methodDir)) {
    $methodDir = Join-Path $dir "Plus\language_methods"
  }
  if (-not (Test-Path -LiteralPath $methodDir)) { return 0 }
  $total = 0
  Get-ChildItem -LiteralPath $methodDir -Recurse -File -Filter "*.jsonl" -ErrorAction SilentlyContinue | ForEach-Object {
    try { $total += (Get-Content -LiteralPath $_.FullName -ErrorAction Stop | Measure-Object -Line).Lines } catch {}
  }
  return $total
}

function Get-RunningShardProcesses() {
  Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object { $_.CommandLine -like "*run_language_method_matrix.py*full_secure_sharded_guarded*" }
}

function Is-ShardRunning($name) {
  $running = Get-RunningShardProcesses
  foreach ($proc in $running) {
    if ($proc.CommandLine -like "*--out-name $name*") { return $true }
  }
  return $false
}

function Start-Shard($shard) {
  if (-not $env:ZHIPU_API_KEY) {
    Write-SchedulerLog "SKIP start $($shard.Name): ZHIPU_API_KEY is missing"
    return
  }
  $args = @(
    "run_language_method_matrix.py",
    "--dataset-root", (Join-Path $project "SecEvoBasePlus"),
    "--subset", $shard.Subset,
    "--languages", $shard.Language,
    "--limit", "0",
    "--include-ours",
    "--out-name", $shard.Name,
    "--model", "glm-5.1",
    "--max-tokens", "2048",
    "--temperature", "0",
    "--retries", "2"
  )
  $stdout = Join-Path $shardLogRoot "$($shard.Name).log"
  $stderr = Join-Path $shardLogRoot "$($shard.Name).err.log"
  $proc = Start-Process -FilePath "python" -ArgumentList $args -WorkingDirectory $exp `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr `
    -PassThru -WindowStyle Hidden
  Write-SchedulerLog "START $($shard.Name) pid=$($proc.Id)"
}

Write-SchedulerLog "scheduler started pid=$PID maxConcurrent=$maxConcurrent"

while ($true) {
  try {
    $running = @(Get-RunningShardProcesses)
    $runningCount = $running.Count
    $totalDone = 0
    $totalExpected = 0
    foreach ($shard in $shards) {
      $rows = Count-ShardRows $shard.Name
      $totalDone += [math]::Min($rows, [int]$shard.Expected)
      $totalExpected += [int]$shard.Expected
      Write-SchedulerLog "STATUS $($shard.Name) rows=$rows/$($shard.Expected) running=$(Is-ShardRunning $shard.Name)"
    }

    if ($totalDone -ge $totalExpected) {
      Write-SchedulerLog "COMPLETE total=$totalDone/$totalExpected"
      break
    }

    if ($runningCount -lt $maxConcurrent) {
      foreach ($shard in $shards) {
        if ($runningCount -ge $maxConcurrent) { break }
        $rows = Count-ShardRows $shard.Name
        if ($rows -ge [int]$shard.Expected) { continue }
        if (Is-ShardRunning $shard.Name) { continue }
        Start-Shard $shard
        $runningCount += 1
      }
    }
  } catch {
    Write-SchedulerLog "ERROR $($_.Exception.Message)"
  }
  Start-Sleep -Seconds 60
}
