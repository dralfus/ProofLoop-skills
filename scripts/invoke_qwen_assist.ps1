[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$Prompt,

    [Parameter(Mandatory)]
    [string]$SchemaPath,

    [Parameter(Mandatory)]
    [string]$Worktree,

    [ValidateSet('openai', 'openai-responses', 'anthropic', 'qwen-oauth', 'gemini', 'vertex-ai')]
    [string]$AuthType,

    [ValidateSet('plan', 'yolo', 'seal')]
    [string]$ApprovalMode = 'plan',

    [switch]$SuccessfulRecon,

    [string]$ReconReportPath,

    [string]$PatchSealReceiptPath,

    [string]$TicketId,

    [string]$SealLedgerDirectory = (Join-Path $env:LOCALAPPDATA 'ProofLoop Skills\qwen-seal-ledger'),

    [string]$Baseline,

    [ValidatePattern('^[A-Za-z0-9._/-]+$')]

    [string]$CredentialTarget = 'ProofLoop/Qwen/OpenAI'
)

$ErrorActionPreference = 'Stop'
if ($ApprovalMode -eq 'yolo' -and -not $SuccessfulRecon) {
    throw 'ApprovalMode yolo requires -SuccessfulRecon.'
}
if ($ApprovalMode -eq 'yolo') {
    if ((Split-Path -Leaf $SchemaPath) -ne 'qwen-assist-patch.schema.json') {
        throw 'ApprovalMode yolo requires qwen-assist-patch.schema.json.'
    }
    if ($Worktree -notmatch '^qwen-patch-') {
        throw 'ApprovalMode yolo requires a qwen-patch- worktree.'
    }
    if (-not $ReconReportPath -or -not (Test-Path -LiteralPath $ReconReportPath)) {
        throw 'ApprovalMode yolo requires an existing -ReconReportPath.'
    }
    if (-not $Baseline -or $Baseline -ne ((& git rev-parse HEAD).Trim())) {
        throw 'ApprovalMode yolo requires -Baseline matching current HEAD.'
    }
    $reconValidation = python "$PSScriptRoot\qwen_assist.py" --validate-recon (Get-Content -Raw -LiteralPath $ReconReportPath) | ConvertFrom-Json
    if ($reconValidation.status -ne 'EVIDENCE_FOUND') { throw 'ApprovalMode yolo requires schema-valid recon evidence.' }
}

if ($ApprovalMode -eq 'seal') {
    if (-not $SuccessfulRecon) { throw 'ApprovalMode seal requires -SuccessfulRecon.' }
    if ((Split-Path -Leaf $SchemaPath) -ne 'qwen-assist-patch.schema.json') { throw 'ApprovalMode seal requires qwen-assist-patch.schema.json.' }
    if ($Worktree -notmatch '^qwen-patch-') { throw 'ApprovalMode seal requires a qwen-patch- worktree.' }
    if (-not $ReconReportPath -or -not (Test-Path -LiteralPath $ReconReportPath)) { throw 'ApprovalMode seal requires an existing -ReconReportPath.' }
    if (-not $Baseline -or $Baseline -ne ((& git rev-parse HEAD).Trim())) { throw 'ApprovalMode seal requires -Baseline matching current HEAD.' }
    $reconReport = Get-Content -Raw -LiteralPath $ReconReportPath
    $reconValidation = python "$PSScriptRoot\qwen_assist.py" --validate-recon $reconReport | ConvertFrom-Json
    if ($reconValidation.status -ne 'EVIDENCE_FOUND') { throw 'ApprovalMode seal requires schema-valid recon evidence.' }
    if (($reconReport | ConvertFrom-Json).baseline -ne $Baseline) { throw 'ApprovalMode seal requires recon baseline matching -Baseline.' }
    if (-not $PatchSealReceiptPath -or -not (Test-Path -LiteralPath $PatchSealReceiptPath)) { throw 'ApprovalMode seal requires an existing -PatchSealReceiptPath.' }
    if (-not $TicketId) { throw 'ApprovalMode seal requires -TicketId.' }
    $patchSealReceipt = Get-Content -Raw -LiteralPath $PatchSealReceiptPath
    $sealValidation = python "$PSScriptRoot\qwen_assist.py" --validate-patch-seal-receipt $patchSealReceipt --expected-baseline $Baseline | ConvertFrom-Json
    if ($sealValidation.status -ne 'PATCH_SEAL_RECEIPT_READY') { throw 'ApprovalMode seal requires a schema-valid observed receipt bound to baseline.' }
    $sealReservation = python "$PSScriptRoot\qwen_assist.py" --reserve-patch-seal --patch-seal-receipt $patchSealReceipt --ticket-id $TicketId --seal-store $SealLedgerDirectory | ConvertFrom-Json
    if ($sealReservation.status -ne 'PATCH_SEAL_RESERVED') { throw "ApprovalMode seal refused: $($sealReservation.reason)." }
}

$requiredMarkers = @(
    '--prompt', '--output-format', '--json-schema', '--worktree',
    '--approval-mode', '--max-session-turns', '--max-wall-time',
    '--max-tool-calls', '--exclude-tools',
    '--bare'
)
$help = (& qwen --help | Out-String)
$missing = @($requiredMarkers | Where-Object { $help -notlike "*$_*" })
if ($help -notlike '*plan*') {
    $missing += 'plan'
}
if ($missing.Count -gt 0) {
    @{ status = 'BLOCKED_CAPABILITY'; missing_capabilities = $missing } |
        ConvertTo-Json -Compress
    exit 3
}

# Qwen may be a locally administered PowerShell function rather than an exe.
# This wrapper preserves that supported configuration and adds no model fallback
# or permissive flags. The Qwen plan mode is the technical write and command
# guard; its output is still validated by qwen_assist.py.
$authArgs = @()
if ($AuthType) {
    $authArgs = @('--auth-type', $AuthType)
}
$effectiveApprovalMode = if ($ApprovalMode -eq 'seal') { 'plan' } else { $ApprovalMode }
$effectivePrompt = if ($ApprovalMode -eq 'seal') { "$Prompt`nPATCH_SEAL_RECEIPT:`n$patchSealReceipt`nCall structured_output exactly once with the manifest matching the patch schema. Do not inspect or edit code, use shell/network, or create subagents." } else { $Prompt }
$excludedTools = if ($effectiveApprovalMode -eq 'plan') { 'Agent,edit,notebook_edit,run_shell_command' } else { 'Agent,run_shell_command' }
$maxSessionTurns = if ($ApprovalMode -eq 'seal') { '12' } else { '12' }
$maxWallTime = if ($ApprovalMode -eq 'seal') { '300s' } else { '10m' }
$maxToolCalls = if ($ApprovalMode -eq 'seal') { '1' } else { '20' }

. "$PSScriptRoot\qwen_credential.ps1"
$previousApiKey = [Environment]::GetEnvironmentVariable('OPENAI_API_KEY', 'Process')
$previousBaseUrl = [Environment]::GetEnvironmentVariable('OPENAI_BASE_URL', 'Process')
$previousModel = [Environment]::GetEnvironmentVariable('OPENAI_MODEL', 'Process')
$openAiBaseUrl = 'https://llm-dev.gs-labs.ru/api/v1'
$openAiModel = 'qwen38-flash-next'
$credentialSecret = $null
$exitCode = 1

try {
    $credentialSecret = Get-ProofLoopQwenGenericSecret -Target $CredentialTarget
    $env:OPENAI_API_KEY = $credentialSecret
    $env:OPENAI_BASE_URL = $openAiBaseUrl
    $env:OPENAI_MODEL = $openAiModel

    & qwen @authArgs `
        '--approval-mode' $effectiveApprovalMode `
        '--output-format' 'json' `
        '--json-schema' "@$SchemaPath" `
        '--worktree' $Worktree `
        '--bare' `
        '--max-session-turns' $maxSessionTurns `
        '--max-wall-time' $maxWallTime `
        '--max-tool-calls' $maxToolCalls `
        '--max-subagent-depth' '1' `
        '--exclude-tools' $excludedTools `
        '--disabled-slash-commands' 'review,loop' `
        '--prompt' $effectivePrompt
    $exitCode = $LASTEXITCODE
}
finally {
    if ($null -eq $previousApiKey) {
        Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
    }
    else {
        $env:OPENAI_API_KEY = $previousApiKey
    }
    if ($null -eq $previousBaseUrl) {
        Remove-Item Env:OPENAI_BASE_URL -ErrorAction SilentlyContinue
    }
    else {
        $env:OPENAI_BASE_URL = $previousBaseUrl
    }
    if ($null -eq $previousModel) {
        Remove-Item Env:OPENAI_MODEL -ErrorAction SilentlyContinue
    }
    else {
        $env:OPENAI_MODEL = $previousModel
    }
    $credentialSecret = $null
}
