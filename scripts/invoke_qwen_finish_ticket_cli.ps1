[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$QwenCommand,

    [ValidateSet('protocol', 'recon')]
    [string]$Mode = 'protocol',

    [string]$QwenArgumentsJson,

    [string]$Ticket,

    [string]$SchemaPath,

    [string]$Worktree,

    [ValidatePattern('^[0-9a-f]{40,64}$')]
    [string]$ReconBaseline,

    [ValidatePattern('^[A-Za-z0-9._/-]+$')]
    [string]$CredentialTarget = 'ProofLoop/Qwen/OpenAI',

    [string]$OpenAIBaseUrl = 'https://llm-dev.gs-labs.ru/api/v1',

    [string]$OpenAIModel = 'qwen38-flash-next'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-QwenFailureProjection {
    param(
        [AllowEmptyString()] [string]$Stdout,
        [AllowEmptyString()] [string]$Stderr
    )

    $stdoutPath = [IO.Path]::GetTempFileName()
    $stderrPath = [IO.Path]::GetTempFileName()
    try {
        [IO.File]::WriteAllText($stdoutPath, $Stdout)
        [IO.File]::WriteAllText($stderrPath, $Stderr)
        $projection = & python (Join-Path $PSScriptRoot 'qwen_terminal_projection.py') `
            --project --stdout-file $stdoutPath --stderr-file $stderrPath | Out-String
        return $projection | ConvertFrom-Json
    }
    catch {
        return [pscustomobject]@{ reason = 'QWEN_COMMAND_FAILED'; diagnostic = [pscustomobject]@{} }
    }
    finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

function Test-QwenNativeAbortExitCode {
    param([int]$ExitCode)

    return $ExitCode -in @(-1073740791, 3221226505)
}

function Test-QwenStructuredSuccessOutput {
    param([AllowEmptyString()] [string]$Output)

    $outputPath = [IO.Path]::GetTempFileName()
    try {
        [IO.File]::WriteAllText($outputPath, $Output)
        $projection = & python (Join-Path $PSScriptRoot 'qwen_terminal_projection.py') `
            --extract-structured-result --input-file $outputPath | Out-String
        return (($projection | ConvertFrom-Json).status -eq 'TERMINAL_STRUCTURED_RESULT')
    }
    catch {
        return $false
    }
    finally {
        Remove-Item -LiteralPath $outputPath -Force -ErrorAction SilentlyContinue
    }
}

function Stop-CommandContract {
    @{ status = 'QWEN_COMMAND_REJECTED'; reason = 'QWEN_ARGUMENT_CONTRACT_INVALID' } | ConvertTo-Json -Compress
    exit 5
}

function Get-QwenRegistryArguments {
    param(
        [Parameter(Mandatory)] [string]$Mode,
        [string]$Ticket,
        [string]$SchemaPath,
        [string]$Baseline
    )

    $registryArguments = @('--mode', $Mode)
    if ($Ticket) { $registryArguments += @('--ticket', $Ticket) }
    if ($SchemaPath) { $registryArguments += @('--schema-path', $SchemaPath) }
    if ($Baseline) { $registryArguments += @('--baseline', $Baseline) }
    try {
        $rendered = & python (Join-Path $PSScriptRoot 'qwen_invocation_contract.py') @registryArguments 2>$null | Out-String
        $exitCode = if (Test-Path Variable:global:LASTEXITCODE) { [int]$global:LASTEXITCODE } else { 0 }
        if ($exitCode -ne 0 -or [string]::IsNullOrWhiteSpace($rendered)) { Stop-CommandContract }
        $argv = @($rendered | ConvertFrom-Json)
        if ($argv.Count -eq 0 -or @($argv | Where-Object { $_ -isnot [string] }).Count -gt 0) { Stop-CommandContract }
        return $argv
    }
    catch {
        Stop-CommandContract
    }
}

if ($Mode -eq 'protocol') {
    try {
        $qwenArguments = @(ConvertFrom-Json -InputObject $QwenArgumentsJson)
    }
    catch {
        Stop-CommandContract
    }

    if ($qwenArguments.Count -ne 10) {
        Stop-CommandContract
    }
    if ($qwenArguments[8] -ne '--prompt' -or $qwenArguments[9] -isnot [string] -or $qwenArguments[9] -notmatch '^/finish-ticket ticket [A-Za-z0-9._/-]+$') {
        Stop-CommandContract
    }
    $ticketFromPrompt = [regex]::Match([string]$qwenArguments[9], '^/finish-ticket ticket ([A-Za-z0-9._/-]+)$')
    if (-not $ticketFromPrompt.Success) {
        Stop-CommandContract
    }
    try {
        $expectedArguments = @(Get-QwenRegistryArguments -Mode 'protocol' -Ticket $ticketFromPrompt.Groups[1].Value)
    }
    catch {
        Stop-CommandContract
    }
    if ($qwenArguments.Count -ne $expectedArguments.Count) {
        Stop-CommandContract
    }
    for ($index = 0; $index -lt $expectedArguments.Count; $index++) {
        if ($qwenArguments[$index] -ne $expectedArguments[$index]) {
            Stop-CommandContract
        }
    }
}
else {
    if (-not $Ticket -or $Ticket -notmatch '^[A-Za-z0-9._/-]+$' -or -not $SchemaPath -or -not $Worktree -or
        -not $ReconBaseline -or
        (Split-Path -Leaf $SchemaPath) -ne 'qwen-assist-recon.schema.json' -or -not (Test-Path -LiteralPath $SchemaPath -PathType Leaf)) {
        Stop-CommandContract
    }
    $qwenArguments = @(Get-QwenRegistryArguments -Mode 'native_recon' -SchemaPath $SchemaPath -Baseline $ReconBaseline)
    $qwenCommandLeaf = Split-Path -Leaf $QwenCommand
    if ($qwenCommandLeaf -in @('qwen', 'qwen.cmd', 'qwen.exe')) {
        $qwenArguments = @(
            '--auth-type', 'openai',
            '--model', $OpenAIModel,
            '--openai-base-url', $OpenAIBaseUrl
        ) + $qwenArguments
    }
}

try {
    $qwenExitCode = 0
    $qwenOutput = ''
    $qwenErrorOutput = ''
    $stderrPath = $null
    $locationPushed = $false
    $credentialInjected = $false
    $credentialSecret = $null
    $previousApiKey = [Environment]::GetEnvironmentVariable('OPENAI_API_KEY', 'Process')
    $previousBaseUrl = [Environment]::GetEnvironmentVariable('OPENAI_BASE_URL', 'Process')
    $previousModel = [Environment]::GetEnvironmentVariable('OPENAI_MODEL', 'Process')
    if ($Mode -eq 'recon') {
        $qwenCommandLeaf = Split-Path -Leaf $QwenCommand
        if ($qwenCommandLeaf -in @('qwen', 'qwen.cmd', 'qwen.exe')) {
            . (Join-Path $PSScriptRoot 'qwen_credential.ps1')
            $credentialSecret = Get-ProofLoopQwenGenericSecret -Target $CredentialTarget
            $env:OPENAI_API_KEY = $credentialSecret
            $env:OPENAI_BASE_URL = $OpenAIBaseUrl
            $env:OPENAI_MODEL = $OpenAIModel
            $credentialInjected = $true
        }
        Push-Location -LiteralPath $Worktree
        $locationPushed = $true
        $stderrPath = [IO.Path]::GetTempFileName()
        $qwenOutput = (& $QwenCommand @qwenArguments 2> $stderrPath | Out-String)
        if (Test-Path -LiteralPath $stderrPath -PathType Leaf) {
            $qwenErrorOutput = Get-Content -LiteralPath $stderrPath -Raw
        }
    }
    else {
        & $QwenCommand @qwenArguments *> $null
    }
    if (Test-Path Variable:global:LASTEXITCODE) {
        $qwenExitCode = $global:LASTEXITCODE
    }
}
catch {
    @{ status = 'QWEN_COMMAND_FAILED'; reason = 'QWEN_COMMAND_UNAVAILABLE' } | ConvertTo-Json -Compress
    exit 4
}
finally {
    if ($stderrPath -and (Test-Path -LiteralPath $stderrPath -PathType Leaf)) {
        Remove-Item -LiteralPath $stderrPath -Force -ErrorAction SilentlyContinue
    }
    if ($locationPushed) {
        Pop-Location
    }
    if ($credentialInjected) {
        if ($null -eq $previousApiKey) { Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue } else { $env:OPENAI_API_KEY = $previousApiKey }
        if ($null -eq $previousBaseUrl) { Remove-Item Env:OPENAI_BASE_URL -ErrorAction SilentlyContinue } else { $env:OPENAI_BASE_URL = $previousBaseUrl }
        if ($null -eq $previousModel) { Remove-Item Env:OPENAI_MODEL -ErrorAction SilentlyContinue } else { $env:OPENAI_MODEL = $previousModel }
        $credentialSecret = $null
    }
}

if ($qwenExitCode -ne 0) {
    if ($Mode -eq 'recon' -and
        (Test-QwenNativeAbortExitCode -ExitCode $qwenExitCode) -and
        (Test-QwenStructuredSuccessOutput -Output $qwenOutput)) {
        $qwenOutput.Trim()
        exit 0
    }
    if ($Mode -eq 'recon') {
        $failureProjection = Get-QwenFailureProjection -Stdout $qwenOutput -Stderr $qwenErrorOutput
        @{ status = 'QWEN_COMMAND_FAILED'; reason = $failureProjection.reason; diagnostic = $failureProjection.diagnostic } | ConvertTo-Json -Compress
    }
    else {
        @{ status = 'QWEN_COMMAND_FAILED'; reason = 'QWEN_COMMAND_FAILED' } | ConvertTo-Json -Compress
    }
    exit $qwenExitCode
}

if ($Mode -eq 'recon') {
    $qwenOutput.Trim()
}
