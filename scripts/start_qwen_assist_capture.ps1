[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$Prompt,
    [Parameter(Mandatory)] [string]$SchemaPath,
    [Parameter(Mandatory)] [string]$Worktree,
    [ValidateSet('openai')] [string]$AuthType = 'openai',
    [ValidatePattern('^[A-Za-z0-9._/-]+$')] [string]$CredentialTarget = 'ProofLoop/Qwen/OpenAI',
    [string]$CaptureDirectory = (Join-Path $env:LOCALAPPDATA 'ProofLoop Skills\\qwen-captures')
)

$ErrorActionPreference = 'Stop'
$runId = [guid]::NewGuid().ToString('N')
$capturePath = Join-Path $CaptureDirectory $runId
New-Item -ItemType Directory -Path $capturePath -Force | Out-Null
$stdoutPath = Join-Path $capturePath 'stdout.json'
$stderrPath = Join-Path $capturePath 'stderr.txt'
$wrapper = Join-Path $PSScriptRoot 'invoke_qwen_assist.ps1'
$command = "& '$wrapper' -Prompt '$($Prompt.Replace("'", "''"))' -SchemaPath '$SchemaPath' -Worktree '$Worktree' -AuthType '$AuthType' -CredentialTarget '$CredentialTarget'"
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
$process = Start-Process -FilePath 'C:\\Program Files\\PowerShell\\7\\pwsh.exe' `
    -ArgumentList @('-NoProfile', '-EncodedCommand', $encoded) `
    -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath `
    -WindowStyle Hidden -PassThru

@{ status = 'STARTED'; run_id = $runId; pid = $process.Id; stdout_path = $stdoutPath; stderr_path = $stderrPath } |
    ConvertTo-Json -Compress
