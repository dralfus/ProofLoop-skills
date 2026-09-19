[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$Prompt,
    [Parameter(Mandatory)] [string]$SchemaPath,
    [Parameter(Mandatory)] [string]$Worktree,
    [ValidateSet('openai')] [string]$AuthType = 'openai',
    [ValidateSet('plan', 'yolo', 'seal')] [string]$ApprovalMode = 'plan',
    [ValidatePattern('^[A-Za-z0-9._/-]+$')] [string]$CredentialTarget = 'ProofLoop/Qwen/OpenAI',
    [switch]$SuccessfulRecon,

    [string]$ReconReportPath,
    [string]$PatchSealReceiptPath,
    [string]$Baseline,

    [string]$CaptureDirectory = (Join-Path $env:LOCALAPPDATA 'ProofLoop Skills\\qwen-captures')
)

$ErrorActionPreference = 'Stop'
if ($ApprovalMode -in @('yolo', 'seal') -and (-not $ReconReportPath -or -not $Baseline)) {
    throw 'Candidate modes require -ReconReportPath and -Baseline.'
}
if ($ApprovalMode -in @('yolo', 'seal') -and $Worktree -notmatch '^qwen-patch-') {
    throw 'Candidate modes require a qwen-patch- worktree.'
}
if ($ApprovalMode -in @('yolo', 'seal') -and -not $SuccessfulRecon) {
    throw 'Candidate modes require -SuccessfulRecon.'
}
if ($ApprovalMode -eq 'seal' -and -not $PatchSealReceiptPath) {
    throw 'ApprovalMode seal requires -PatchSealReceiptPath.'
}

$runId = [guid]::NewGuid().ToString('N')
$capturePath = Join-Path $CaptureDirectory $runId
New-Item -ItemType Directory -Path $capturePath -Force | Out-Null
$stdoutPath = Join-Path $capturePath 'stdout.json'
$stderrPath = Join-Path $capturePath 'stderr.txt'
$wrapper = Join-Path $PSScriptRoot 'invoke_qwen_assist.ps1'
$successfulReconArgument = if ($SuccessfulRecon) { ' -SuccessfulRecon' } else { '' }
$reconArgument = if ($ReconReportPath) { " -ReconReportPath '$ReconReportPath' -Baseline '$Baseline'" } else { '' }
$sealReceiptArgument = if ($PatchSealReceiptPath) { " -PatchSealReceiptPath '$PatchSealReceiptPath'" } else { '' }
$command = "& '$wrapper' -Prompt '$($Prompt.Replace("'", "''"))' -SchemaPath '$SchemaPath' -Worktree '$Worktree' -AuthType '$AuthType' -ApprovalMode '$ApprovalMode'$successfulReconArgument$reconArgument$sealReceiptArgument -CredentialTarget '$CredentialTarget'"
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
$process = Start-Process -FilePath 'C:\\Program Files\\PowerShell\\7\\pwsh.exe' `
    -ArgumentList @('-NoProfile', '-EncodedCommand', $encoded) `
    -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath `
    -WindowStyle Hidden -PassThru

@{ status = 'STARTED'; run_id = $runId; pid = $process.Id; stdout_path = $stdoutPath; stderr_path = $stderrPath } |
    ConvertTo-Json -Compress
