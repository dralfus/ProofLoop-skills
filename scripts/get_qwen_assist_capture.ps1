[CmdletBinding()]
param(
    [Parameter(Mandatory)] [ValidatePattern('^[a-f0-9]{32}$')] [string]$RunId,
    [Parameter(Mandatory)] [int]$ProcessId,
    [string]$CaptureDirectory = (Join-Path $env:LOCALAPPDATA 'ProofLoop Skills\\qwen-captures')
)

$ErrorActionPreference = 'Stop'
$CapturePath = Join-Path $CaptureDirectory $RunId
$stdoutPath = Join-Path $CapturePath 'stdout.json'
$stderrPath = Join-Path $CapturePath 'stderr.txt'

if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
    @{ status = 'RUNNING'; pid = $ProcessId; capture_path = $CapturePath } |
        ConvertTo-Json -Compress
    exit 0
}

$stdout = if (Test-Path -LiteralPath $stdoutPath) {
    Get-Content -LiteralPath $stdoutPath -Raw
} else {
    ''
}
$stderr = if (Test-Path -LiteralPath $stderrPath) {
    Get-Content -LiteralPath $stderrPath -Raw
} else {
    ''
}

try {
    $terminalOutput = $stdout | ConvertFrom-Json -ErrorAction Stop
    @{ status = 'COMPLETE'; pid = $ProcessId; terminal_output = $terminalOutput; stderr = $stderr } |
        ConvertTo-Json -Depth 32 -Compress
}
catch {
    @{ status = 'COMPLETE_INVALID_OUTPUT'; pid = $ProcessId; stderr = $stderr } |
        ConvertTo-Json -Compress
}
