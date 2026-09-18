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

    [ValidatePattern('^[A-Za-z0-9._/-]+$')]
    [string]$CredentialTarget = 'ProofLoop/Qwen/OpenAI'
)

$ErrorActionPreference = 'Stop'
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
        '--approval-mode' 'plan' `
        '--output-format' 'json' `
        '--json-schema' "@$SchemaPath" `
        '--worktree' $Worktree `
        '--bare' `
        '--max-session-turns' '12' `
        '--max-wall-time' '10m' `
        '--max-tool-calls' '20' `
        '--max-subagent-depth' '1' `
        '--exclude-tools' 'Agent' `
        '--disabled-slash-commands' 'review,loop' `
        '--prompt' $Prompt
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
