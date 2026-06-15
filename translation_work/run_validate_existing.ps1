param(
    [string]$Dataset = "SecEvaBase",
    [int]$MaxWorkers = 1,
    [int]$RequestTimeout = 180,
    [int]$MaxTokens = 65536,
    [int]$MaxRepairAttempts = 1,
    [switch]$Resume,
    [switch]$SkipSecureValidation,
    [switch]$SkipInsecureValidation
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$SecAwareCoder = Join-Path $Root "DatasetAndMethod\SecAwareCoder"
$Outputs = Join-Path $Root "translation_work\outputs"
$Logs = Join-Path $Root "translation_work\logs"

New-Item -ItemType Directory -Force -Path $Outputs | Out-Null
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$RunLog = Join-Path $Logs "validate_existing_${Dataset}_${Timestamp}.log"
$StatusFile = Join-Path $Logs "validate_existing_${Dataset}_${Timestamp}.status.json"

if ($Dataset -eq "SecEvaBase") {
    $DataPath = "..\..\translation_work\outputs\SecEvaBase.translated.json"
    $OutputPath = "..\..\translation_work\outputs\SecEvaBase.translated.validated.json"
} elseif ($Dataset -eq "SecEvalPlus") {
    $DataPath = "..\..\translation_work\outputs\SecEvalPlus.translated.json"
    $OutputPath = "..\..\translation_work\outputs\SecEvalPlus.translated.validated.json"
} else {
    throw "Unsupported dataset: $Dataset"
}

Set-Location -LiteralPath $SecAwareCoder

$started = Get-Date
@{
    dataset = $Dataset
    status = "running"
    started = $started.ToString("o")
    log = $RunLog
    output = (Join-Path $Root ($OutputPath -replace '^\.\.\\\.\.\\', ''))
    max_workers = $MaxWorkers
    request_timeout = $RequestTimeout
    max_tokens = $MaxTokens
    max_repair_attempts = $MaxRepairAttempts
    resume = [bool]$Resume
    skip_secure_validation = [bool]$SkipSecureValidation
    skip_insecure_validation = [bool]$SkipInsecureValidation
} | ConvertTo-Json | Set-Content -LiteralPath $StatusFile -Encoding UTF8

"[$($started.ToString('s'))] Starting validation/repair for $Dataset" | Tee-Object -FilePath $RunLog -Append

$argsList = @(
    "-m", "translation_pipeline.run_translate_dataset",
    "--data-path", $DataPath,
    "--output-path", $OutputPath,
    "--model", "glm-4.7",
    "--max-workers", "$MaxWorkers",
    "--validate-existing",
    "--request-timeout", "$RequestTimeout",
    "--max-tokens", "$MaxTokens",
    "--max-repair-attempts", "$MaxRepairAttempts"
)

if ($Resume) {
    $argsList += "--resume"
}
if ($SkipSecureValidation) {
    $argsList += "--skip-secure-validation"
}
if ($SkipInsecureValidation) {
    $argsList += "--skip-insecure-validation"
}

try {
    & python @argsList *>&1 | Tee-Object -FilePath $RunLog -Append

    $exitCode = $LASTEXITCODE
    $ended = Get-Date
    @{
        dataset = $Dataset
        status = if ($exitCode -eq 0) { "completed" } else { "failed" }
        exit_code = $exitCode
        started = $started.ToString("o")
        ended = $ended.ToString("o")
        log = $RunLog
        output = (Join-Path $Root ($OutputPath -replace '^\.\.\\\.\.\\', ''))
        max_workers = $MaxWorkers
        request_timeout = $RequestTimeout
        max_tokens = $MaxTokens
        max_repair_attempts = $MaxRepairAttempts
        resume = [bool]$Resume
        skip_secure_validation = [bool]$SkipSecureValidation
        skip_insecure_validation = [bool]$SkipInsecureValidation
    } | ConvertTo-Json | Set-Content -LiteralPath $StatusFile -Encoding UTF8
    exit $exitCode
} catch {
    $ended = Get-Date
    "[$($ended.ToString('s'))] ERROR: $($_.Exception.Message)" | Tee-Object -FilePath $RunLog -Append
    @{
        dataset = $Dataset
        status = "failed"
        error = $_.Exception.Message
        started = $started.ToString("o")
        ended = $ended.ToString("o")
        log = $RunLog
        output = (Join-Path $Root ($OutputPath -replace '^\.\.\\\.\.\\', ''))
        max_workers = $MaxWorkers
        request_timeout = $RequestTimeout
        max_tokens = $MaxTokens
        max_repair_attempts = $MaxRepairAttempts
        resume = [bool]$Resume
        skip_secure_validation = [bool]$SkipSecureValidation
        skip_insecure_validation = [bool]$SkipInsecureValidation
    } | ConvertTo-Json | Set-Content -LiteralPath $StatusFile -Encoding UTF8
    exit 1
}
