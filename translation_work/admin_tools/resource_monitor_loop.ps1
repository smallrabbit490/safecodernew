$ErrorActionPreference = "Continue"

$project = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$runRoot = Join-Path $project "translation_work\monitored_full_run"
$logRoot = Join-Path $runRoot "logs"
$monitorLog = Join-Path $logRoot "resource_monitor.csv"
$pidFile = Join-Path $runRoot "monitor_pid.txt"
$outRoot = Join-Path $project "baseline\experience_transfer_experiment\out"
$vhdxPath = if ($env:DOCKER_DESKTOP_VHDX) { $env:DOCKER_DESKTOP_VHDX } else { "D:\DockerDesktopLocal\wsl-data\disk\docker_data.vhdx" }
$shardNames = @(
  "full_secure_sharded_guarded_base_python",
  "full_secure_sharded_guarded_base_cpp",
  "full_secure_sharded_guarded_base_go",
  "full_secure_sharded_guarded_plus_python",
  "full_secure_sharded_guarded_plus_cpp",
  "full_secure_sharded_guarded_plus_go"
)

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$PID | Set-Content -LiteralPath $pidFile -Encoding ASCII
"timestamp,d_free_gb,d_used_gb,mem_free_gb,mem_used_pct,vhdx_gb,docker_images,docker_containers,docker_volumes,docker_build_cache,base_python_rows,base_cpp_rows,base_go_rows,plus_python_rows,plus_cpp_rows,plus_go_rows,largest_jsonl_mb" | Set-Content -LiteralPath $monitorLog -Encoding UTF8

function CountJsonlRows($dir) {
  if (-not (Test-Path -LiteralPath $dir)) { return 0 }
  $total = 0
  $methodDir = Join-Path $dir "Base\language_methods"
  if (-not (Test-Path -LiteralPath $methodDir)) {
    $methodDir = Join-Path $dir "Plus\language_methods"
  }
  if (-not (Test-Path -LiteralPath $methodDir)) { return 0 }
  Get-ChildItem -LiteralPath $methodDir -Recurse -File -Filter "*.jsonl" -ErrorAction SilentlyContinue | ForEach-Object {
    try { $total += (Get-Content -LiteralPath $_.FullName -ErrorAction Stop | Measure-Object -Line).Lines } catch {}
  }
  return $total
}

function DockerDfValue($typeName) {
  try {
    $line = docker system df --format "{{.Type}},{{.Size}}" 2>$null | Where-Object { $_ -like "$typeName,*" } | Select-Object -First 1
    if ($line) { return (($line -split ',',2)[1]) }
  } catch {}
  return "NA"
}

while ($true) {
  try {
    $drive = Get-PSDrive -Name D
    $os = Get-CimInstance Win32_OperatingSystem
    $memFreeGb = [math]::Round(($os.FreePhysicalMemory * 1KB) / 1GB, 3)
    $memTotalGb = [math]::Round(($os.TotalVisibleMemorySize * 1KB) / 1GB, 3)
    $memUsedPct = if ($memTotalGb -gt 0) { [math]::Round((1 - ($memFreeGb / $memTotalGb)) * 100, 2) } else { 0 }
    $vhdx = Get-Item -LiteralPath $vhdxPath -ErrorAction SilentlyContinue
    $rows = @()
    foreach ($name in $shardNames) { $rows += CountJsonlRows (Join-Path $outRoot $name) }
    $largest = 0
    foreach ($name in $shardNames) {
      $dir = Join-Path $outRoot $name
      $methodDir = Join-Path $dir "Base\language_methods"
      if (-not (Test-Path -LiteralPath $methodDir)) {
        $methodDir = Join-Path $dir "Plus\language_methods"
      }
      if (Test-Path -LiteralPath $methodDir) {
        Get-ChildItem -LiteralPath $methodDir -Recurse -File -Filter "*.jsonl" -ErrorAction SilentlyContinue | ForEach-Object {
          if ($_.Length -gt $largest) { $largest = $_.Length }
        }
      }
    }
    $values = @(
      (Get-Date -Format o),
      [math]::Round($drive.Free / 1GB, 3),
      [math]::Round($drive.Used / 1GB, 3),
      $memFreeGb,
      $memUsedPct,
      $(if ($vhdx) { [math]::Round($vhdx.Length / 1GB, 3) } else { 0 }),
      (DockerDfValue "Images"),
      (DockerDfValue "Containers"),
      (DockerDfValue "Local Volumes"),
      (DockerDfValue "Build Cache"),
      $rows[0],$rows[1],$rows[2],$rows[3],$rows[4],$rows[5],
      [math]::Round($largest / 1MB, 3)
    )
    Add-Content -LiteralPath $monitorLog -Value (($values | ForEach-Object { '"' + ([string]$_).Replace('"','""') + '"' }) -join ',') -Encoding UTF8
  } catch {
    Add-Content -LiteralPath $monitorLog -Value ((Get-Date -Format o) + ',MONITOR_ERROR,"' + $_.Exception.Message.Replace('"','""') + '"') -Encoding UTF8
  }
  Start-Sleep -Seconds 60
}
