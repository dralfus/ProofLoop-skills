[CmdletBinding()]
param(
    [Parameter(Mandatory)] [ValidatePattern('^[a-f0-9]{32}$')] [string]$RunId,
    [Parameter(Mandatory)] [int]$ProcessId,
    [string]$PatchSealReceiptPath,
    [string]$CaptureDirectory = (Join-Path $env:LOCALAPPDATA 'ProofLoop Skills\qwen-captures')
)

$ErrorActionPreference = 'Stop'

function Get-TerminalResultEvent {
    param([Parameter(Mandatory)] [object]$ParsedOutput)

    [object[]]$events = @($ParsedOutput)
    if ($events.Count -eq 0) {
        return $null
    }

    $terminalEvent = $events[$events.Count - 1]
    if ($terminalEvent -isnot [pscustomobject]) {
        return $null
    }
    $typeProperty = $terminalEvent.PSObject.Properties['type']
    if ($null -eq $typeProperty -or [string]$typeProperty.Value -ne 'result') {
        return $null
    }
    $isErrorProperty = $terminalEvent.PSObject.Properties['is_error']
    $subtypeProperty = $terminalEvent.PSObject.Properties['subtype']
    if ($null -eq $isErrorProperty -or $isErrorProperty.Value -isnot [bool] -or
        [bool]$isErrorProperty.Value -or $null -eq $subtypeProperty -or
        [string]$subtypeProperty.Value -ne 'success') {
        return $null
    }
    return $terminalEvent
}

$CapturePath = Join-Path $CaptureDirectory $RunId
$stdoutPath = Join-Path $CapturePath 'stdout.json'
$stderrPath = Join-Path $CapturePath 'stderr.txt'
if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
    @{ status = 'RUNNING'; pid = $ProcessId; capture_path = $CapturePath } | ConvertTo-Json -Compress
    exit 0
}
$stdout = if (Test-Path -LiteralPath $stdoutPath) { Get-Content -LiteralPath $stdoutPath -Raw } else { '' }
$stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw } else { '' }
if ($PatchSealReceiptPath -and [string]::IsNullOrWhiteSpace($stdout)) {
    @{ status = 'QWEN_UNUSABLE'; reason = 'MISSING_TERMINAL_PATCH_MANIFEST'; pid = $ProcessId } | ConvertTo-Json -Compress
    exit 0
}
try {
    $terminalOutput = $stdout | ConvertFrom-Json -ErrorAction Stop
    if ($PatchSealReceiptPath) {
        if (-not (Test-Path -LiteralPath $PatchSealReceiptPath)) { throw 'Patch seal receipt is unavailable.' }
        $terminalEvent = Get-TerminalResultEvent -ParsedOutput $terminalOutput
        $structuredResultProperty = if ($null -eq $terminalEvent) { $null } else { $terminalEvent.PSObject.Properties['structured_result'] }
        $manifest = if ($null -eq $structuredResultProperty) { $null } else { $structuredResultProperty.Value }
        if ($manifest -isnot [pscustomobject]) {
            @{ status = 'QWEN_UNUSABLE'; reason = 'MISSING_TERMINAL_PATCH_MANIFEST'; pid = $ProcessId } | ConvertTo-Json -Compress
            exit 0
        }
        $sealResult = python "$PSScriptRoot\qwen_assist.py" --validate-patch-seal-manifest ($manifest | ConvertTo-Json -Depth 32 -Compress) --patch-seal-receipt (Get-Content -Raw -LiteralPath $PatchSealReceiptPath) | ConvertFrom-Json
        if ($sealResult.status -eq 'SEALED_CANDIDATE') {
            @{ status = 'SEALED_CANDIDATE'; pid = $ProcessId } | ConvertTo-Json -Compress
        }
        else {
            @{ status = 'QWEN_UNUSABLE'; reason = $sealResult.reason; pid = $ProcessId } | ConvertTo-Json -Compress
        }
        exit 0
    }
    @{ status = 'COMPLETE'; pid = $ProcessId; terminal_output = $terminalOutput; stderr = $stderr } | ConvertTo-Json -Depth 32 -Compress
}
catch {
    if ($PatchSealReceiptPath) {
        @{ status = 'QWEN_UNUSABLE'; reason = 'INVALID_TERMINAL_PATCH_MANIFEST'; pid = $ProcessId } | ConvertTo-Json -Compress
    }
    else {
        @{ status = 'COMPLETE_INVALID_OUTPUT'; pid = $ProcessId; stderr = $stderr } | ConvertTo-Json -Compress
    }
}
