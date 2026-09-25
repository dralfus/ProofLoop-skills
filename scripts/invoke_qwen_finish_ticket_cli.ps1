[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$QwenCommand,

    [ValidateSet('protocol', 'recon')]
    [string]$Mode = 'protocol',

    [string]$QwenArgumentsJson,

    [ValidatePattern('^[0-9a-f]{32}$')]
    [string]$LaunchId,

    [string]$ContinuationPacket,

    [ValidateRange(8000, 2147483647)]
    [int]$OutputTokenLimit = 8000,

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
    if ($ContinuationPacket -and (
        [string]::IsNullOrWhiteSpace($ContinuationPacket) -or
        $ContinuationPacket.Length -gt 32768
    )) {
        Stop-CommandContract
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
    $runtimeProjection = $null
    $runtimeProjectionJson = $null
    $failureEnvelopeProjection = $null
    $runtimeProjectionExitCode = $null
    $runtimeProjectionOutputPresent = $false
    $runtimeProjectionParseValid = $false
    $qwenOutput = ''
    $qwenErrorOutput = ''
    $stderrPath = $null
    $locationPushed = $false
    $credentialInjected = $false
    $credentialSecret = $null
    $eventFilePath = $null
    $processObservationPath = $null
    $processObservation = $null
    $hostBoundedComplete = $false
    $protocolLaunchId = $null
    $runtimeClock = [Diagnostics.Stopwatch]::StartNew()
    $previousApiKey = [Environment]::GetEnvironmentVariable('OPENAI_API_KEY', 'Process')
    $previousBaseUrl = [Environment]::GetEnvironmentVariable('OPENAI_BASE_URL', 'Process')
    $previousModel = [Environment]::GetEnvironmentVariable('OPENAI_MODEL', 'Process')
    $previousOutputLimit = [Environment]::GetEnvironmentVariable('QWEN_CODE_MAX_OUTPUT_TOKENS', 'Process')
    if ($Mode -eq 'protocol') {
        $env:QWEN_CODE_MAX_OUTPUT_TOKENS = [string]$OutputTokenLimit
        $eventFilePath = [IO.Path]::GetTempFileName()
        $processObservationPath = [IO.Path]::GetTempFileName()
        $protocolLaunchId = if ($LaunchId) { $LaunchId } else { [guid]::NewGuid().ToString('N').ToLowerInvariant() }
        if ($ContinuationPacket) {
            $qwenArguments[9] = [string]$qwenArguments[9] + "`n`nPROOFLOOP_VERIFIED_CONTINUATION:`n" + $ContinuationPacket
        }
        $qwenArguments += @('--json-file', $eventFilePath)
    }
    $qwenCommandLeaf = Split-Path -Leaf $QwenCommand
    if ($qwenCommandLeaf -in @('qwen', 'qwen.cmd', 'qwen.exe')) {
        . (Join-Path $PSScriptRoot 'qwen_credential.ps1')
        $credentialSecret = Get-ProofLoopQwenGenericSecret -Target $CredentialTarget
        $env:OPENAI_API_KEY = $credentialSecret
        $credentialInjected = $true
        if ($Mode -eq 'recon') {
            $env:OPENAI_BASE_URL = $OpenAIBaseUrl
            $env:OPENAI_MODEL = $OpenAIModel
        }
    }
    if ($Mode -eq 'recon') {
        Push-Location -LiteralPath $Worktree
        $locationPushed = $true
        $stderrPath = [IO.Path]::GetTempFileName()
        $qwenOutput = (& $QwenCommand @qwenArguments 2> $stderrPath | Out-String)
        if (Test-Path -LiteralPath $stderrPath -PathType Leaf) {
            $qwenErrorOutput = Get-Content -LiteralPath $stderrPath -Raw
        }
    }
    else {
        . (Join-Path $PSScriptRoot 'qwen_protocol_supervisor.ps1')
        $supervisorResult = Invoke-QwenProtocolChild `
            -QwenCommand $QwenCommand `
            -QwenArguments $qwenArguments `
            -EventFilePath $eventFilePath `
            -LaunchId $protocolLaunchId `
            -MaxToolCalls 20 `
            -MaxWallTimeSeconds 1800
        $qwenExitCode = [int]$supervisorResult.qwen_exit_code
        $processObservation = $supervisorResult.process_observation
        [IO.File]::WriteAllText(
            $processObservationPath,
            ($processObservation | ConvertTo-Json -Compress -Depth 4),
            [Text.UTF8Encoding]::new($false)
        )
    }
    if ($Mode -eq 'recon' -and (Test-Path Variable:global:LASTEXITCODE)) {
        $qwenExitCode = $global:LASTEXITCODE
    }
    if ($credentialInjected) {
        if ($null -eq $previousApiKey) { Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue } else { $env:OPENAI_API_KEY = $previousApiKey }
        if ($null -eq $previousBaseUrl) { Remove-Item Env:OPENAI_BASE_URL -ErrorAction SilentlyContinue } else { $env:OPENAI_BASE_URL = $previousBaseUrl }
        if ($null -eq $previousModel) { Remove-Item Env:OPENAI_MODEL -ErrorAction SilentlyContinue } else { $env:OPENAI_MODEL = $previousModel }
        $credentialSecret = $null
        $credentialInjected = $false
    }
    if ($Mode -eq 'protocol' -and $eventFilePath -and (Test-Path -LiteralPath $eventFilePath -PathType Leaf) -and
        $processObservationPath -and (Test-Path -LiteralPath $processObservationPath -PathType Leaf)) {
        $runtimeClock.Stop()
        $wallTime = [int][Math]::Ceiling($runtimeClock.Elapsed.TotalSeconds)
        $nativeCommandErrorPreference = Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue
        if ($null -ne $nativeCommandErrorPreference) { $PSNativeCommandUseErrorActionPreference = $false }
        try {
            $projectionJson = & python (Join-Path $PSScriptRoot 'qwen_runtime_adapter.py') `
                '--project-events' $eventFilePath `
                '--process-observation-file' $processObservationPath `
                '--launch-id' $protocolLaunchId 2>$null | Out-String
        }
        finally {
            if ($null -ne $nativeCommandErrorPreference) { $PSNativeCommandUseErrorActionPreference = [bool]$nativeCommandErrorPreference.Value }
        }
        $runtimeProjectionExitCode = if (Test-Path Variable:global:LASTEXITCODE) { [int]$global:LASTEXITCODE } else { 0 }
        $runtimeProjectionOutputPresent = -not [string]::IsNullOrWhiteSpace($projectionJson)
        # The adapter uses exit 3 for a valid fail-closed projection. Preserve
        # that raw-free JSON instead of replacing it with a generic fallback.
        if ($runtimeProjectionExitCode -in @(0, 3) -and $runtimeProjectionOutputPresent) {
            try {
                $runtimeProjection = $projectionJson | ConvertFrom-Json
                $runtimeProjectionParseValid = $null -ne $runtimeProjection
                if ($runtimeProjectionParseValid) {
                    $runtimeProjectionJson = $runtimeProjection | ConvertTo-Json -Compress -Depth 4
                }
            }
            catch {
                $runtimeProjection = [pscustomobject]@{ status = 'BLOCKED_CAPABILITY'; reason = 'QWEN_RUNTIME_EVIDENCE_UNSUPPORTED'; role_dispatch = $false }
                $runtimeProjectionJson = $runtimeProjection | ConvertTo-Json -Compress -Depth 4
            }
        }
        if (-not $runtimeProjectionJson) {
            $runtimeProjection = [pscustomobject]@{ status = 'BLOCKED_CAPABILITY'; reason = 'QWEN_RUNTIME_EVIDENCE_UNSUPPORTED'; role_dispatch = $false }
            $runtimeProjectionJson = $runtimeProjection | ConvertTo-Json -Compress -Depth 4
        }
        if ($qwenExitCode -ne 0) {
            try {
                $failureEnvelopeJson = & python (Join-Path $PSScriptRoot 'qwen_runtime_adapter.py') `
                    '--project-events' $eventFilePath `
                    '--wall-time-seconds' $wallTime 2>$null | Out-String
                $failureEnvelopeExitCode = if (Test-Path Variable:global:LASTEXITCODE) { [int]$global:LASTEXITCODE } else { 0 }
                if ($failureEnvelopeExitCode -in @(0, 3) -and -not [string]::IsNullOrWhiteSpace($failureEnvelopeJson)) {
                    $candidate = $failureEnvelopeJson | ConvertFrom-Json
                    if ($candidate.reason -eq 'QWEN_JSON_ERROR_RESULT' -and $candidate.diagnostic -is [pscustomobject]) {
                        $failureEnvelopeProjection = $candidate
                    }
                }
            }
            catch {
                $failureEnvelopeProjection = $null
            }
        }
    }
}
catch {
    @{ status = 'QWEN_COMMAND_FAILED'; reason = 'QWEN_COMMAND_UNAVAILABLE' } | ConvertTo-Json -Compress
    exit 4
}
finally {
    if ($eventFilePath -and (Test-Path -LiteralPath $eventFilePath -PathType Leaf)) {
        Remove-Item -LiteralPath $eventFilePath -Force -ErrorAction SilentlyContinue
    }
    if ($processObservationPath -and (Test-Path -LiteralPath $processObservationPath -PathType Leaf)) {
        Remove-Item -LiteralPath $processObservationPath -Force -ErrorAction SilentlyContinue
    }
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
    if ($Mode -eq 'protocol') {
        if ($null -eq $previousOutputLimit) { Remove-Item Env:QWEN_CODE_MAX_OUTPUT_TOKENS -ErrorAction SilentlyContinue } else { $env:QWEN_CODE_MAX_OUTPUT_TOKENS = $previousOutputLimit }
    }
}

if ($Mode -eq 'protocol' -and $runtimeProjection -and
    $runtimeProjection.status -eq 'COMPLETE' -and
    $runtimeProjection.terminal_source -eq 'HOST' -and
    $runtimeProjection.budget_stop -eq $true -and
    $runtimeProjection.loop_status -eq 'HOST_CLEAR') {
    $hostBoundedComplete = $true
}

if ($qwenExitCode -ne 0 -and -not $hostBoundedComplete) {
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
    elseif ($runtimeProjectionJson) {
        $failureReason = 'QWEN_COMMAND_FAILED'
        $runtimeReasonProperty = $runtimeProjection.PSObject.Properties['reason']
        if ($null -ne $runtimeReasonProperty -and [string]$runtimeReasonProperty.Value -in @('QWEN_JSON_ERROR_RESULT', 'QWEN_RUNTIME_EVIDENCE_UNSUPPORTED')) {
            $failureReason = [string]$runtimeReasonProperty.Value
        }
        if ($null -ne $failureEnvelopeProjection) { $failureReason = 'QWEN_JSON_ERROR_RESULT' }
        $failureProjection = [ordered]@{
            status = 'QWEN_COMMAND_FAILED'
            reason = $failureReason
            qwen_exit_code = [int]$qwenExitCode
            runtime_evidence_status = [string]$runtimeProjection.status
            runtime_projection_output_present = [bool]$runtimeProjectionOutputPresent
            runtime_projection_parse_valid = [bool]$runtimeProjectionParseValid
        }
        if ($null -ne $runtimeProjectionExitCode) { $failureProjection.runtime_projection_exit_code = [int]$runtimeProjectionExitCode }
        foreach ($field in @('session_id', 'session_id_hash', 'turns', 'tool_calls', 'wall_time_seconds', 'session_ended', 'terminal_reason', 'terminal_source', 'event_coverage', 'budget_stop', 'loop_status', 'loop_detector_version', 'tool_fingerprint')) {
            $property = $runtimeProjection.PSObject.Properties[$field]
            if ($null -ne $property) { $failureProjection[$field] = $property.Value }
        }
        $runtimeDiagnostic = $runtimeProjection.PSObject.Properties['diagnostic']
        if ($null -ne $runtimeDiagnostic -and $runtimeDiagnostic.Value -is [pscustomobject]) {
            $safeDiagnostic = [ordered]@{}
            foreach ($field in @('terminal_result', 'terminal_is_error', 'error_message_present')) {
                $property = $runtimeDiagnostic.Value.PSObject.Properties[$field]
                if ($null -ne $property -and $property.Value -is [bool]) { $safeDiagnostic[$field] = [bool]$property.Value }
            }
            $subtypeProperty = $runtimeDiagnostic.Value.PSObject.Properties['terminal_subtype']
            if ($null -ne $subtypeProperty -and [string]$subtypeProperty.Value -in @('none', 'success', 'error_during_execution', 'other')) {
                $safeDiagnostic.terminal_subtype = [string]$subtypeProperty.Value
            }
            $categoryProperty = $runtimeDiagnostic.Value.PSObject.Properties['error_message_category']
            if ($null -ne $categoryProperty -and [string]$categoryProperty.Value -in @('none', 'structured_output_missing', 'auth_or_forbidden', 'transport', 'other')) {
                $safeDiagnostic.error_message_category = [string]$categoryProperty.Value
            }
            if ($safeDiagnostic.Count -gt 0) { $failureProjection.diagnostic = $safeDiagnostic }
        }
        if ($null -ne $failureEnvelopeProjection) {
            foreach ($field in @('session_id', 'turns', 'tool_calls', 'wall_time_seconds', 'tool_fingerprint')) {
                $property = $failureEnvelopeProjection.PSObject.Properties[$field]
                if ($null -ne $property) { $failureProjection[$field] = $property.Value }
            }
            $sourceDiagnostic = $failureEnvelopeProjection.diagnostic
            $safeDiagnostic = [ordered]@{}
            foreach ($field in @('terminal_result', 'terminal_is_error', 'error_message_present')) {
                $property = $sourceDiagnostic.PSObject.Properties[$field]
                if ($null -ne $property -and $property.Value -is [bool]) { $safeDiagnostic[$field] = [bool]$property.Value }
            }
            $subtypeProperty = $sourceDiagnostic.PSObject.Properties['terminal_subtype']
            if ($null -ne $subtypeProperty -and [string]$subtypeProperty.Value -in @('none', 'success', 'error_during_execution', 'other')) {
                $safeDiagnostic.terminal_subtype = [string]$subtypeProperty.Value
            }
            $categoryProperty = $sourceDiagnostic.PSObject.Properties['error_message_category']
            if ($null -ne $categoryProperty -and [string]$categoryProperty.Value -in @('none', 'structured_output_missing', 'auth_or_forbidden', 'transport', 'other')) {
                $safeDiagnostic.error_message_category = [string]$categoryProperty.Value
            }
            if ($safeDiagnostic.Count -gt 0) { $failureProjection.diagnostic = $safeDiagnostic }
        }
        $failureProjection | ConvertTo-Json -Compress -Depth 4
    }
    else {
        @{ status = 'QWEN_COMMAND_FAILED'; reason = 'QWEN_COMMAND_FAILED' } | ConvertTo-Json -Compress
    }
    exit $qwenExitCode
}

    if ($Mode -eq 'protocol') {
        if (-not $runtimeProjectionJson) {
            $runtimeProjection = [pscustomobject]@{ status = 'BLOCKED_CAPABILITY'; reason = 'QWEN_RUNTIME_EVIDENCE_UNSUPPORTED'; role_dispatch = $false }
            $runtimeProjectionJson = $runtimeProjection | ConvertTo-Json -Compress -Depth 4
        }
        Write-Output $runtimeProjectionJson
        exit 0
    }

if ($Mode -eq 'recon') {
    $qwenOutput.Trim()
}
