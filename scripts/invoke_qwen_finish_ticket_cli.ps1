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

function Inspect-QwenOutput {
    param([AllowEmptyString()] [string]$Output)

    $present = -not [string]::IsNullOrWhiteSpace($Output)
    $json = $false
    $structuredOutputMarker = $false
    $jsonShape = 'none'
    $terminalResult = $false
    $terminalIsError = $false
    $terminalSubtype = 'none'
    $errorMessagePresent = $false
    $errorMessageCategory = 'none'
    $envelopeIsError = $false
    $envelopeSubtype = 'none'
    $envelopeErrorMessagePresent = $false
    $envelopeErrorMessageCategory = 'none'
    $parsed = $null

    if ($present) {
        try {
            $parsed = $Output | ConvertFrom-Json
            $json = $true
        }
        catch {
            $parsed = $null
        }
    }

    if ($json) {
        $terminal = $null
        $topLevelEnvelope = $false
        if ($parsed -is [array]) {
            $jsonShape = 'array'
            $terminalEvents = @($parsed | Where-Object { $_.type -eq 'result' } | Select-Object -Last 1)
            if ($terminalEvents.Count -eq 1) {
                $terminal = $terminalEvents[0]
            }
        }
        elseif ($parsed -is [pscustomobject]) {
            $jsonShape = 'object'
            if ($null -ne $parsed.PSObject.Properties['type'] -and [string]$parsed.type -eq 'result') {
                $terminal = $parsed
            }
            elseif ($null -ne $parsed.PSObject.Properties['is_error'] -or
                $null -ne $parsed.PSObject.Properties['subtype'] -or
                $null -ne $parsed.PSObject.Properties['error']) {
                $terminal = $parsed
                $topLevelEnvelope = $true
            }
        }
        else {
            $jsonShape = 'other'
        }

        if ($null -ne $terminal) {
            $isErrorProperty = $terminal.PSObject.Properties['is_error']
            $isError = $false
            if ($null -ne $isErrorProperty -and $isErrorProperty.Value -is [bool]) {
                $isError = [bool]$isErrorProperty.Value
            }
            $subtypeProperty = $terminal.PSObject.Properties['subtype']
            $subtype = 'none'
            if ($null -ne $subtypeProperty -and [string]$subtypeProperty.Value -in @('success', 'error_during_execution')) {
                $subtype = [string]$subtypeProperty.Value
            }
            elseif ($null -ne $subtypeProperty -and -not [string]::IsNullOrWhiteSpace([string]$subtypeProperty.Value)) {
                $subtype = 'other'
            }

            $errorMessage = ''
            $errorProperty = $terminal.PSObject.Properties['error']
            if ($null -ne $errorProperty -and $null -ne $errorProperty.Value) {
                $messageProperty = $errorProperty.Value.PSObject.Properties['message']
                if ($null -ne $messageProperty) {
                    $errorMessage = [string]$messageProperty.Value
                }
            }
            $messagePresent = -not [string]::IsNullOrWhiteSpace($errorMessage)
            $messageCategory = 'none'
            if ($errorMessage -match '(?i)model did not produce structured output|plain text instead of calling.*structured_output|structured[ _-]?output.*missing') {
                $messageCategory = 'structured_output_missing'
                $structuredOutputMarker = $true
            }
            elseif ($errorMessage -match '(?i)\b(401|403)\b|unauthori[sz]ed|forbidden|api[\s_-]*key|authentication|bearer|token') {
                $messageCategory = 'auth_or_forbidden'
            }
            elseif ($errorMessage -match '(?i)\b5\d\d\b|websocket|https?://|fetch failed|timed? ?out|network|connection|econn|dns|proxy|gateway') {
                $messageCategory = 'transport'
            }
            elseif ($messagePresent) {
                $messageCategory = 'other'
            }

            $errorTypeProperty = $terminal.PSObject.Properties['errorType']
            $errorType = if ($null -eq $errorTypeProperty) { '' } else { [string]$errorTypeProperty.Value }
            $legacyErrorMessageProperty = $terminal.PSObject.Properties['errorMessage']
            $legacyErrorMessage = if ($null -eq $legacyErrorMessageProperty) { '' } else { [string]$legacyErrorMessageProperty.Value }
            $structuredOutputMarker = $structuredOutputMarker -or
                $errorType -in @('structured_output_missing', 'structured-output-missing') -or
                $legacyErrorMessage -match '(?i)model did not produce structured output|plain text instead of calling.*structured_output|structured[ _-]?output.*missing'

            if ($topLevelEnvelope) {
                $envelopeIsError = $isError
                $envelopeSubtype = $subtype
                $envelopeErrorMessagePresent = $messagePresent
                $envelopeErrorMessageCategory = $messageCategory
            }
            else {
                $terminalResult = $true
                $terminalIsError = $isError
                $terminalSubtype = $subtype
            }
            $errorMessagePresent = $messagePresent
            $errorMessageCategory = $messageCategory
        }
    }

    if (-not $structuredOutputMarker -and $present) {
        $structuredOutputMarker = $Output -match '(?i)model did not produce structured output|plain text instead of calling.*structured_output|structured[ _-]?output.*missing'
        if ($structuredOutputMarker) {
            $errorMessageCategory = 'structured_output_missing'
        }
    }

    return [pscustomobject]@{
        present = $present
        json = $json
        structured_output_marker = $structuredOutputMarker
        json_shape = $jsonShape
        terminal_result = $terminalResult
        terminal_is_error = $terminalIsError
        terminal_subtype = $terminalSubtype
        error_message_present = $errorMessagePresent
        error_message_category = $errorMessageCategory
        envelope_is_error = $envelopeIsError
        envelope_subtype = $envelopeSubtype
        envelope_error_message_present = $envelopeErrorMessagePresent
        envelope_error_message_category = $envelopeErrorMessageCategory
    }
}

function Get-QwenFailureProjection {
    param(
        [AllowEmptyString()] [string]$Stdout,
        [AllowEmptyString()] [string]$Stderr
    )

    $stdoutInspection = Inspect-QwenOutput -Output $Stdout
    $stderrInspection = Inspect-QwenOutput -Output $Stderr
    $stdoutStructured = [bool]$stdoutInspection.structured_output_marker
    $stderrStructured = [bool]$stderrInspection.structured_output_marker
    $jsonErrorResult = [bool]$stdoutInspection.terminal_is_error -or
        [bool]$stderrInspection.terminal_is_error -or
        [bool]$stdoutInspection.envelope_is_error -or
        [bool]$stderrInspection.envelope_is_error
    $reason = if ($stdoutStructured -or $stderrStructured) {
        'STRUCTURED_OUTPUT_MISSING'
    }
    elseif ($jsonErrorResult) {
        'QWEN_JSON_ERROR_RESULT'
    }
    else {
        'QWEN_COMMAND_FAILED'
    }
    $structuredChannel = if ($stdoutStructured -and $stderrStructured) {
        'stdout+stderr'
    }
    elseif ($stdoutStructured) {
        'stdout'
    }
    elseif ($stderrStructured) {
        'stderr'
    }
    else {
        'none'
    }

    return @{
        reason = $reason
        diagnostic = [ordered]@{
            stdout_present = [bool]$stdoutInspection.present
            stderr_present = [bool]$stderrInspection.present
            stdout_json = [bool]$stdoutInspection.json
            stderr_json = [bool]$stderrInspection.json
            structured_output_channel = $structuredChannel
            json_shape = if ($stdoutInspection.json_shape -ne 'none') { $stdoutInspection.json_shape } else { $stderrInspection.json_shape }
            terminal_result = [bool]$stdoutInspection.terminal_result -or [bool]$stderrInspection.terminal_result
            terminal_is_error = $jsonErrorResult
            terminal_subtype = if ($stdoutInspection.terminal_subtype -ne 'none') { $stdoutInspection.terminal_subtype } else { $stderrInspection.terminal_subtype }
            error_message_present = [bool]$stdoutInspection.error_message_present -or [bool]$stderrInspection.error_message_present
            error_message_category = if ($stdoutInspection.error_message_category -ne 'none') { $stdoutInspection.error_message_category } else { $stderrInspection.error_message_category }
            envelope_is_error = [bool]$stdoutInspection.envelope_is_error -or [bool]$stderrInspection.envelope_is_error
            envelope_subtype = if ($stdoutInspection.envelope_subtype -ne 'none') { $stdoutInspection.envelope_subtype } else { $stderrInspection.envelope_subtype }
            envelope_error_message_present = [bool]$stdoutInspection.envelope_error_message_present -or [bool]$stderrInspection.envelope_error_message_present
            envelope_error_message_category = if ($stdoutInspection.envelope_error_message_category -ne 'none') { $stdoutInspection.envelope_error_message_category } else { $stderrInspection.envelope_error_message_category }
        }
    }
}

function Test-QwenNativeAbortExitCode {
    param([int]$ExitCode)

    return $ExitCode -in @(-1073740791, 3221226505)
}

function Test-QwenStructuredSuccessOutput {
    param([AllowEmptyString()] [string]$Output)

    if ([string]::IsNullOrWhiteSpace($Output)) {
        return $false
    }
    try {
        $parsed = $Output | ConvertFrom-Json
    }
    catch {
        return $false
    }
    $terminal = $null
    if ($parsed -is [array]) {
        $terminalEvents = @($parsed | Where-Object { $_.type -eq 'result' } | Select-Object -Last 1)
        if ($terminalEvents.Count -eq 1) {
            $terminal = $terminalEvents[0]
        }
    }
    if ($null -eq $terminal) {
        return $false
    }
    $isErrorProperty = $terminal.PSObject.Properties['is_error']
    $subtypeProperty = $terminal.PSObject.Properties['subtype']
    $structuredResultProperty = $terminal.PSObject.Properties['structured_result']
    return $null -ne $isErrorProperty -and
        $isErrorProperty.Value -is [bool] -and
        -not [bool]$isErrorProperty.Value -and
        $null -ne $subtypeProperty -and
        [string]$subtypeProperty.Value -eq 'success' -and
        $null -ne $structuredResultProperty -and
        $structuredResultProperty.Value -is [pscustomobject]
}

function Stop-CommandContract {
    @{ status = 'QWEN_COMMAND_REJECTED'; reason = 'QWEN_ARGUMENT_CONTRACT_INVALID' } | ConvertTo-Json -Compress
    exit 5
}

if ($Mode -eq 'protocol') {
    try {
        $qwenArguments = @(ConvertFrom-Json -InputObject $QwenArgumentsJson)
    }
    catch {
        Stop-CommandContract
    }

    $expectedArguments = @(
        '--max-session-turns', '20',
        '--max-tool-calls', '20',
        '--max-wall-time', '30m',
        '--max-subagent-depth', '1'
    )
    if ($qwenArguments.Count -ne 10) {
        Stop-CommandContract
    }
    for ($index = 0; $index -lt $expectedArguments.Count; $index++) {
        if ($qwenArguments[$index] -ne $expectedArguments[$index]) {
            Stop-CommandContract
        }
    }
    if ($qwenArguments[8] -ne '--prompt' -or $qwenArguments[9] -isnot [string] -or $qwenArguments[9] -notmatch '^/finish-ticket ticket [A-Za-z0-9._/-]+$') {
        Stop-CommandContract
    }
}
else {
    if (-not $Ticket -or $Ticket -notmatch '^[A-Za-z0-9._/-]+$' -or -not $SchemaPath -or -not $Worktree -or
        -not $ReconBaseline -or
        (Split-Path -Leaf $SchemaPath) -ne 'qwen-assist-recon.schema.json' -or -not (Test-Path -LiteralPath $SchemaPath -PathType Leaf)) {
        Stop-CommandContract
    }
    $reconPrompt = "Inspect only README.md in the current clean worktree using read-only file inspection. The baseline is $ReconBaseline. Then call structured_output exactly once with a schema-valid EVIDENCE_FOUND report containing at least three concrete facts. Set baseline exactly to $ReconBaseline. Do not edit files, run commands, or use network."
    $qwenArguments = @(
        '--bare',
        '--approval-mode', 'plan',
        '--output-format', 'json',
        '--json-schema', "@$SchemaPath",
        '--max-session-turns', '3',
        '--max-wall-time', '5m',
        '--max-tool-calls', '6',
        '--max-subagent-depth', '1',
        '--exclude-tools', 'Agent,edit,notebook_edit,run_shell_command',
        '--disabled-slash-commands', 'review,loop',
        '--prompt', $reconPrompt
    )
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
