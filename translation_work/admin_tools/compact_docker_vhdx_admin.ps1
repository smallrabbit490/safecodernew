$ErrorActionPreference = "Stop"

$vhdxPath = if ($env:DOCKER_DESKTOP_VHDX) { $env:DOCKER_DESKTOP_VHDX } else { "D:\DockerDesktopLocal\wsl-data\disk\docker_data.vhdx" }
$workDir = $PSScriptRoot
$diskpartScript = Join-Path $workDir "compact_docker_vhdx.diskpart.txt"
$logPath = Join-Path $workDir "compact_docker_vhdx.log"

New-Item -ItemType Directory -Force -Path $workDir | Out-Null

function Write-Log($message) {
    "[$(Get-Date -Format o)] $message" | Tee-Object -FilePath $logPath -Append
}

function Disk-Snapshot($label) {
    Write-Log "=== $label ==="
    $item = Get-Item -LiteralPath $vhdxPath
    Write-Log ("VHDX logical size GB: {0}" -f ([math]::Round($item.Length / 1GB, 3)))
    Get-PSDrive -PSProvider FileSystem |
        Select-Object Name, @{Name='FreeGB';Expression={[math]::Round($_.Free/1GB,2)}}, @{Name='UsedGB';Expression={[math]::Round($_.Used/1GB,2)}}, Root |
        Format-Table -AutoSize |
        Out-String |
        Tee-Object -FilePath $logPath -Append
}

Write-Log "Starting Docker VHDX compact."
Disk-Snapshot "before"

Write-Log "Stopping Docker Desktop and WSL."
Get-Process |
    Where-Object { $_.ProcessName -match 'Docker|com\.docker|docker-sandbox' } |
    Stop-Process -Force -ErrorAction SilentlyContinue
wsl --shutdown
Start-Sleep -Seconds 8

$optimizeVhd = Get-Command Optimize-VHD -ErrorAction SilentlyContinue
if ($optimizeVhd) {
    Write-Log "Running Optimize-VHD -Mode Full."
    try {
        Optimize-VHD -Path $vhdxPath -Mode Full
        Write-Log "Optimize-VHD completed."
    } catch {
        Write-Log "Optimize-VHD failed: $($_.Exception.Message)"
    }
} else {
    Write-Log "Optimize-VHD is not available; falling back to diskpart compact vdisk."
}

@"
select vdisk file="$vhdxPath"
attach vdisk readonly
compact vdisk
detach vdisk
exit
"@ | Set-Content -LiteralPath $diskpartScript -Encoding ASCII

Write-Log "Running diskpart compact vdisk."
diskpart /s $diskpartScript | Tee-Object -FilePath $logPath -Append
Remove-Item -LiteralPath $diskpartScript -Force -ErrorAction SilentlyContinue

Disk-Snapshot "after"
Write-Log "Finished Docker VHDX compact."
