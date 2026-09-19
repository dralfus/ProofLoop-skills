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
    [string]$TicketId,
    [string]$SealLedgerDirectory = (Join-Path $env:LOCALAPPDATA 'ProofLoop Skills\qwen-seal-ledger'),
    [string]$Baseline,
    [string]$CaptureDirectory = (Join-Path $env:LOCALAPPDATA 'ProofLoop Skills\qwen-captures')
)

$ErrorActionPreference = 'Stop'
if ($ApprovalMode -in @('yolo', 'seal') -and (-not $ReconReportPath -or -not $Baseline)) { throw 'Candidate modes require -ReconReportPath and -Baseline.' }
if ($ApprovalMode -in @('yolo', 'seal') -and $Worktree -notmatch '^qwen-patch-') { throw 'Candidate modes require a qwen-patch- worktree.' }
if ($ApprovalMode -in @('yolo', 'seal') -and -not $SuccessfulRecon) { throw 'Candidate modes require -SuccessfulRecon.' }
if ($ApprovalMode -eq 'seal' -and (-not $PatchSealReceiptPath -or -not $TicketId)) { throw 'ApprovalMode seal requires -PatchSealReceiptPath and -TicketId.' }

function Quote-PowerShellLiteral([string]$Value) { return "'" + $Value.Replace("'", "''") + "'" }

$runId = [guid]::NewGuid().ToString('N')
$capturePath = Join-Path $CaptureDirectory $runId
New-Item -ItemType Directory -Path $capturePath -Force | Out-Null
$stdoutPath = Join-Path $capturePath 'stdout.json'
$stderrPath = Join-Path $capturePath 'stderr.txt'
$wrapper = Join-Path $PSScriptRoot 'invoke_qwen_assist.ps1'
$arguments = @(
    "& $(Quote-PowerShellLiteral $wrapper)",
    "-Prompt $(Quote-PowerShellLiteral $Prompt)",
    "-SchemaPath $(Quote-PowerShellLiteral $SchemaPath)",
    "-Worktree $(Quote-PowerShellLiteral $Worktree)",
    "-AuthType $(Quote-PowerShellLiteral $AuthType)",
    "-ApprovalMode $(Quote-PowerShellLiteral $ApprovalMode)",
    "-CredentialTarget $(Quote-PowerShellLiteral $CredentialTarget)"
)
if ($SuccessfulRecon) { $arguments += '-SuccessfulRecon' }
if ($ReconReportPath) { $arguments += "-ReconReportPath $(Quote-PowerShellLiteral $ReconReportPath)"; $arguments += "-Baseline $(Quote-PowerShellLiteral $Baseline)" }
if ($PatchSealReceiptPath) { $arguments += "-PatchSealReceiptPath $(Quote-PowerShellLiteral $PatchSealReceiptPath)" }
if ($TicketId) { $arguments += "-TicketId $(Quote-PowerShellLiteral $TicketId)"; $arguments += "-SealLedgerDirectory $(Quote-PowerShellLiteral $SealLedgerDirectory)" }
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes(($arguments -join ' ')))
$process = Start-Process -FilePath 'C:\Program Files\PowerShell\7\pwsh.exe' -ArgumentList @('-NoProfile', '-EncodedCommand', $encoded) -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -WindowStyle Hidden -PassThru
@{ status = 'STARTED'; run_id = $runId; pid = $process.Id; stdout_path = $stdoutPath; stderr_path = $stderrPath } | ConvertTo-Json -Compress