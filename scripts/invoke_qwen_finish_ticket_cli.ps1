[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$QwenCommand,

    [ValidateSet('protocol', 'recon')]
    [string]$Mode = 'protocol',

    [ValidateSet('standard', 'pilot-expanded')]
    [string]$ProtocolBudgetProfile = 'standard',

    [string]$QwenArgumentsJson,

    [ValidatePattern('^[0-9a-f]{32}$')]
    [string]$LaunchId,

    [string]$ContinuationPacket,

    [string]$ContinuationPacketPath,

    [switch]$ShowOutput,

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
$script:CliFailureStage = 'ARGUMENT_VALIDATION'

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
    param([string]$Reason = 'QWEN_ARGUMENT_CONTRACT_INVALID')

    @{ status = 'QWEN_COMMAND_REJECTED'; reason = $Reason; cli_failure_stage = 'ARGUMENT_CONTRACT' } | ConvertTo-Json -Compress
    exit 5
}

function Test-PilotExpandedBudgetScope {
    param([Parameter(Mandatory)] [string]$TicketPath)

    if ($ProtocolBudgetProfile -ne 'pilot-expanded') { return $true }
    if ($Mode -ne 'protocol' -or (Split-Path -Leaf $TicketPath) -cne 'qwen-protocol-pilot-ticket.md') { return $false }
    $currentDirectory = [IO.Path]::GetFullPath((Get-Location).Path)
    if ($currentDirectory -notmatch '[\\/]\.scratch[\\/]' -or
        -not (Test-Path -LiteralPath (Join-Path $currentDirectory '.git'))) { return $false }
    try {
        $resolvedTicket = [IO.Path]::GetFullPath((Join-Path $currentDirectory ($TicketPath.Replace('/', [IO.Path]::DirectorySeparatorChar))))
        $ticketPrefix = $currentDirectory.TrimEnd([char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)) + [IO.Path]::DirectorySeparatorChar
        if (-not $resolvedTicket.StartsWith($ticketPrefix, [StringComparison]::OrdinalIgnoreCase)) { return $false }
        $ticketText = Get-Content -LiteralPath $resolvedTicket -Raw -ErrorAction Stop
    }
    catch { return $false }
    foreach ($requiredMarker in @(
        'This is a fresh owner-authorized experiment',
        'It is a test-only slice related to Ticket 314',
        'test_patch_candidate_rejects_changed_lines_over_200',
        'Do not commit, transfer, broaden scope'
    )) {
        if ($ticketText -notlike "*$requiredMarker*") { return $false }
    }
    return $true
}

if ($ContinuationPacketPath -and $ContinuationPacket) {
    Stop-CommandContract
}
if ($ContinuationPacketPath) {
    try {
        $packetInfo = Get-Item -LiteralPath $ContinuationPacketPath -ErrorAction Stop
        if ($packetInfo -isnot [IO.FileInfo] -or $packetInfo.Length -gt 14000) {
            Stop-CommandContract
        }
        $packetBytes = [IO.File]::ReadAllBytes($ContinuationPacketPath)
        if ($packetBytes.LongLength -gt 14000) {
            Stop-CommandContract
        }
        $ContinuationPacket = [Text.UTF8Encoding]::new($false, $true).GetString($packetBytes)
        [Array]::Clear($packetBytes, 0, $packetBytes.Length)
    }
    catch {
        Stop-CommandContract
    }
}

function Get-QwenRegistryArguments {
    param(
        [Parameter(Mandatory)] [string]$Mode,
        [string]$Ticket,
        [string]$SchemaPath,
        [string]$Baseline,
        [string]$BudgetProfile = 'standard'
    )

    $registryArguments = @('--mode', $Mode)
    if ($Ticket) { $registryArguments += @('--ticket', $Ticket) }
    if ($Mode -eq 'protocol') { $registryArguments += @('--protocol-budget-profile', $BudgetProfile) }
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

function New-QwenLaunchDiagnostic {
    param(
        [object]$Observation,
        [switch]$ShowOutput
    )

    $diagnostic = [ordered]@{
        schema_version = 1
        supervisor_stage = 'NOT_REACHED'
        process_state = 'NOT_STARTED'
        process_exit_code = $null
        event_file_state = 'NOT_OBSERVED'
        event_file_bytes = $null
        console_output_mode = if ($ShowOutput) { 'VISIBLE' } else { 'SUPPRESSED' }
    }
    if ($null -eq $Observation) { return [pscustomobject]$diagnostic }

    $stageProperty = $Observation.PSObject.Properties['supervisor_stage']
    if ($null -ne $stageProperty -and [string]$stageProperty.Value -in @(
        'COMMAND_RESOLUTION', 'PROCESS_CREATION', 'CHILD_STARTED', 'PROCESS_EXITED',
        'PROCESS_EXIT_UNCONFIRMED', 'COMMAND_RESOLUTION_FAILED', 'PROCESS_CREATION_FAILED',
        'CHILD_MONITOR_FAILED'
    )) {
        $diagnostic.supervisor_stage = [string]$stageProperty.Value
    }
    $stateProperty = $Observation.PSObject.Properties['process_state']
    if ($null -ne $stateProperty -and [string]$stateProperty.Value -in @('NOT_STARTED', 'RUNNING', 'EXITED', 'UNKNOWN')) {
        $diagnostic.process_state = [string]$stateProperty.Value
    }
    $exitProperty = $Observation.PSObject.Properties['process_exit_code']
    if ($null -ne $exitProperty -and $exitProperty.Value -is [ValueType] -and
        $exitProperty.Value -isnot [bool] -and [int64]$exitProperty.Value -ge -2147483648 -and
        [int64]$exitProperty.Value -le 2147483647) {
        $diagnostic.process_exit_code = [int]$exitProperty.Value
    }
    $eventStateProperty = $Observation.PSObject.Properties['event_file_state']
    if ($null -ne $eventStateProperty -and [string]$eventStateProperty.Value -in @(
        'NOT_OBSERVED', 'MISSING', 'EMPTY', 'PRESENT', 'UNAVAILABLE'
    )) {
        $diagnostic.event_file_state = [string]$eventStateProperty.Value
    }
    $eventBytesProperty = $Observation.PSObject.Properties['event_file_bytes']
    if ($null -ne $eventBytesProperty -and $eventBytesProperty.Value -is [ValueType] -and
        $eventBytesProperty.Value -isnot [bool] -and [int64]$eventBytesProperty.Value -ge 0 -and
        [int64]$eventBytesProperty.Value -le 2147483647) {
        $diagnostic.event_file_bytes = [int]$eventBytesProperty.Value
    }
    $consoleProperty = $Observation.PSObject.Properties['console_output_mode']
    if ($null -ne $consoleProperty -and [string]$consoleProperty.Value -in @('SUPPRESSED', 'VISIBLE')) {
        $diagnostic.console_output_mode = [string]$consoleProperty.Value
    }
    return [pscustomobject]$diagnostic
}

if ($Mode -eq 'protocol') {
    try {
        $qwenArguments = @(ConvertFrom-Json -InputObject $QwenArgumentsJson)
    }
    catch {
        Stop-CommandContract
    }

    if ($qwenArguments.Count -ne 12) {
        Stop-CommandContract
    }
    if ($qwenArguments[8] -ne '--output-format' -or $qwenArguments[9] -ne 'stream-json' -or
        $qwenArguments[10] -ne '--prompt' -or $qwenArguments[11] -isnot [string] -or
        $qwenArguments[11] -notmatch '^/finish-ticket ticket [A-Za-z0-9._/-]+$') {
        Stop-CommandContract
    }
    $ticketFromPrompt = [regex]::Match([string]$qwenArguments[11], '^/finish-ticket ticket ([A-Za-z0-9._/-]+)$')
    if (-not $ticketFromPrompt.Success) {
        Stop-CommandContract
    }
    try {
        $expectedArguments = @(Get-QwenRegistryArguments -Mode 'protocol' -Ticket $ticketFromPrompt.Groups[1].Value -BudgetProfile $ProtocolBudgetProfile)
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
    if (-not (Test-PilotExpandedBudgetScope -TicketPath $ticketFromPrompt.Groups[1].Value)) {
        Stop-CommandContract -Reason 'PILOT_BUDGET_SCOPE_REQUIRED'
    }
    if ($ContinuationPacket -and (
        [string]::IsNullOrWhiteSpace($ContinuationPacket) -or
        [Text.Encoding]::UTF8.GetByteCount($ContinuationPacket) -gt 14000
    )) {
        Stop-CommandContract
    }
    $maxToolCallsIndex = [Array]::IndexOf([string[]]$qwenArguments, '--max-tool-calls')
    if ($maxToolCallsIndex -lt 0 -or $maxToolCallsIndex + 1 -ge $qwenArguments.Count -or
        $qwenArguments[$maxToolCallsIndex + 1] -notin @('20', '40')) {
        Stop-CommandContract
    }
    $maxToolCalls = [int]$qwenArguments[$maxToolCallsIndex + 1]
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

$script:CliFailureStage = 'ARGUMENTS_VALIDATED'

try {
    $script:CliFailureStage = 'CAPTURE_SETUP'
    $qwenExitCode = 0
    $launchDiagnostic = New-QwenLaunchDiagnostic -ShowOutput:$ShowOutput
    $runtimeProjection = $null
    $runtimeProjectionJson = $null
    $failureEnvelopeProjection = $null
    $runtimeProjectionExitCode = $null
    $runtimeProjectionOutputPresent = $false
    $runtimeProjectionParseValid = $false
    $qwenOutput = ''
    $qwenErrorOutput = ''
    $stderrPath = $null
    $stdoutCapturePath = $null
    $stderrCapturePath = $null
    $processOutputCaptureStatus = 'NOT_REQUESTED'
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
    if ($Mode -eq 'protocol') {
        $stdoutCapturePath = [IO.Path]::GetTempFileName()
        # Headless stream-json is the event channel; --prompt-interactive requires a TTY.
        $eventFilePath = $stdoutCapturePath
        $processObservationPath = [IO.Path]::GetTempFileName()
        $stderrCapturePath = [IO.Path]::GetTempFileName()
        $processOutputCaptureStatus = 'AVAILABLE'
        $protocolLaunchId = if ($LaunchId) { $LaunchId } else { [guid]::NewGuid().ToString('N').ToLowerInvariant() }
        if ($ContinuationPacket) {
            $qwenArguments[11] = [string]$qwenArguments[11] + "`n`nPROOFLOOP_VERIFIED_CONTINUATION:`n" + $ContinuationPacket
        }
    }
    $script:CliFailureStage = 'CAPTURE_READY'
    $qwenCommandLeaf = Split-Path -Leaf $QwenCommand
    if ($qwenCommandLeaf -in @('qwen', 'qwen.cmd', 'qwen.exe')) {
        $script:CliFailureStage = 'CREDENTIAL_HELPER_LOAD'
        . (Join-Path $PSScriptRoot 'qwen_credential.ps1')
        $script:CliFailureStage = 'CREDENTIAL_LOOKUP'
        $credentialSecret = Get-ProofLoopQwenGenericSecret -Target $CredentialTarget
        $script:CliFailureStage = 'CREDENTIAL_READY'
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
        $script:CliFailureStage = 'SUPERVISOR_LOAD'
        . (Join-Path $PSScriptRoot 'qwen_protocol_supervisor.ps1')
        $script:CliFailureStage = 'SUPERVISOR_READY'
        $script:CliFailureStage = 'SUPERVISOR_DISPATCH'
        $supervisorResult = Invoke-QwenProtocolChild `
            -QwenCommand $QwenCommand `
            -QwenArguments $qwenArguments `
            -EventFilePath $eventFilePath `
            -StdoutFilePath $stdoutCapturePath `
            -StderrFilePath $stderrCapturePath `
            -LaunchId $protocolLaunchId `
            -MaxToolCalls $maxToolCalls `
            -MaxWallTimeSeconds 1800 `
            -ShowOutput:$ShowOutput
        $script:CliFailureStage = 'SUPERVISOR_RETURNED'
        $processObservation = $supervisorResult.process_observation
        $launchDiagnostic = New-QwenLaunchDiagnostic -Observation $supervisorResult.launch_diagnostic -ShowOutput:$ShowOutput
        $qwenExitCode = if ($processObservation.child_started -and $processObservation.process_exited -and
            $processObservation.process_exit_code -is [ValueType]) {
            [int]$processObservation.process_exit_code
        }
        else { $null }
        [IO.File]::WriteAllText(
            $processObservationPath,
            ($processObservation | ConvertTo-Json -Compress -Depth 4),
            [Text.UTF8Encoding]::new($false)
        )
        if (-not $ShowOutput -and $qwenExitCode -is [ValueType] -and $qwenExitCode -ne 0) {
            $maxCapturedOutputBytes = 2 * 1024 * 1024
            try {
                $stdoutCaptureLength = (Get-Item -LiteralPath $stdoutCapturePath -ErrorAction Stop).Length
                $stderrCaptureLength = (Get-Item -LiteralPath $stderrCapturePath -ErrorAction Stop).Length
                if ($stdoutCaptureLength -le $maxCapturedOutputBytes -and $stderrCaptureLength -le $maxCapturedOutputBytes) {
                    $qwenOutput = [IO.File]::ReadAllText($stdoutCapturePath, [Text.Encoding]::UTF8)
                    $qwenErrorOutput = [IO.File]::ReadAllText($stderrCapturePath, [Text.Encoding]::UTF8)
                }
                else {
                    $processOutputCaptureStatus = 'LIMIT_EXCEEDED'
                }
            }
            catch {
                $processOutputCaptureStatus = 'UNAVAILABLE'
            }
        }
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
        $script:CliFailureStage = 'RUNTIME_PROJECTION'
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
        }
        $roleLifecycleEvidence = [pscustomobject]@{
            schema_version = 'proofloop.qwen-role-lifecycle.v1'
            status = 'BLOCKED'
            reason = 'ROLE_EVIDENCE_UNAVAILABLE'
            launch_id = $protocolLaunchId
            session_id_hash = $null
            role_calls = @()
            unclassified_agent_calls = 0
        }
        try {
            $roleProjectionJson = & python (Join-Path $PSScriptRoot 'qwen_runtime_adapter.py') '--project-role-lifecycle' $eventFilePath '--launch-id' $protocolLaunchId 2>$null | Out-String
            $roleProjectionExitCode = if (Test-Path Variable:global:LASTEXITCODE) { [int]$global:LASTEXITCODE } else { 0 }
            if ($roleProjectionExitCode -in @(0, 3) -and -not [string]::IsNullOrWhiteSpace($roleProjectionJson)) {
                $candidateRoleEvidence = $roleProjectionJson | ConvertFrom-Json
                $expectedSessionHash = if (
                    $null -ne $runtimeProjection.PSObject.Properties['session_id_hash'] -and
                    [string]$runtimeProjection.session_id_hash -match '^[0-9a-f]{64}$'
                ) { [string]$runtimeProjection.session_id_hash } else { $null }
                if (
                    $candidateRoleEvidence.schema_version -eq 'proofloop.qwen-role-lifecycle.v1' -and
                    $candidateRoleEvidence.launch_id -eq $protocolLaunchId -and
                    $null -ne $expectedSessionHash -and
                    $candidateRoleEvidence.session_id_hash -eq $expectedSessionHash -and
                    $candidateRoleEvidence.status -in @('COMPLETE', 'BLOCKED')
                ) {
                    $roleLifecycleEvidence = $candidateRoleEvidence
                }
            }
        }
        catch {
            # Keep only the fixed unavailable marker; never surface adapter diagnostics.
        }
        if ($qwenExitCode -is [ValueType] -and $qwenExitCode -ne 0 -and -not $ShowOutput) {
            if ($processOutputCaptureStatus -eq 'AVAILABLE') {
                $outputFailureProjection = Get-QwenFailureProjection -Stdout $qwenOutput -Stderr $qwenErrorOutput
                $processOutputDiagnostic = [pscustomobject]@{
                    capture_status = 'PROJECTED'
                    reason = [string]$outputFailureProjection.reason
                    diagnostic = $outputFailureProjection.diagnostic
                }
            }
            else {
                $processOutputDiagnostic = [pscustomobject]@{
                    capture_status = $processOutputCaptureStatus
                    reason = 'QWEN_COMMAND_FAILED'
                    diagnostic = $null
                }
            }
            $runtimeProjection | Add-Member -NotePropertyName process_output_diagnostic -NotePropertyValue $processOutputDiagnostic -Force
        }
        $runtimeProjection | Add-Member -NotePropertyName role_lifecycle_evidence -NotePropertyValue $roleLifecycleEvidence -Force
        $runtimeProjection | Add-Member -NotePropertyName launch_diagnostic -NotePropertyValue $launchDiagnostic -Force
        $script:CliFailureStage = 'RUNTIME_PROJECTED'
        $runtimeProjection | Add-Member -NotePropertyName cli_stage -NotePropertyValue $script:CliFailureStage -Force
        $runtimeProjectionJson = $runtimeProjection | ConvertTo-Json -Compress -Depth 5
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
    $allowedCliFailureStages = @(
        'ARGUMENTS_VALIDATED', 'CAPTURE_SETUP', 'CAPTURE_READY', 'CREDENTIAL_LOOKUP',
        'CREDENTIAL_HELPER_LOAD', 'CREDENTIAL_READY', 'SUPERVISOR_LOAD', 'SUPERVISOR_READY', 'SUPERVISOR_DISPATCH',
        'SUPERVISOR_RETURNED', 'RUNTIME_PROJECTION', 'RUNTIME_PROJECTED'
    )
    $safeCliFailureStage = if ($script:CliFailureStage -in $allowedCliFailureStages) { $script:CliFailureStage } else { 'UNKNOWN' }
    @{ status = 'QWEN_COMMAND_FAILED'; reason = 'QWEN_COMMAND_UNAVAILABLE'; cli_failure_stage = $safeCliFailureStage; launch_diagnostic = $launchDiagnostic } | ConvertTo-Json -Compress -Depth 5
    exit 4
}
finally {
    if ($eventFilePath -and (Test-Path -LiteralPath $eventFilePath -PathType Leaf)) {
        Remove-Item -LiteralPath $eventFilePath -Force -ErrorAction SilentlyContinue
    }
    if ($processObservationPath -and (Test-Path -LiteralPath $processObservationPath -PathType Leaf)) {
        Remove-Item -LiteralPath $processObservationPath -Force -ErrorAction SilentlyContinue
    }
    if ($stdoutCapturePath -and (Test-Path -LiteralPath $stdoutCapturePath -PathType Leaf)) {
        Remove-Item -LiteralPath $stdoutCapturePath -Force -ErrorAction SilentlyContinue
    }
    if ($stderrCapturePath -and (Test-Path -LiteralPath $stderrCapturePath -PathType Leaf)) {
        Remove-Item -LiteralPath $stderrCapturePath -Force -ErrorAction SilentlyContinue
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
            runtime_evidence_status = [string]$runtimeProjection.status
            runtime_projection_output_present = [bool]$runtimeProjectionOutputPresent
            runtime_projection_parse_valid = [bool]$runtimeProjectionParseValid
            launch_diagnostic = $launchDiagnostic
        }
        if ([string]$runtimeProjection.cli_stage -in @(
            'ARGUMENTS_VALIDATED', 'CAPTURE_SETUP', 'CAPTURE_READY', 'CREDENTIAL_HELPER_LOAD', 'CREDENTIAL_LOOKUP',
            'CREDENTIAL_READY', 'SUPERVISOR_LOAD', 'SUPERVISOR_READY', 'SUPERVISOR_DISPATCH',
            'SUPERVISOR_RETURNED', 'RUNTIME_PROJECTION', 'RUNTIME_PROJECTED'
        )) { $failureProjection.cli_stage = [string]$runtimeProjection.cli_stage }
        if ($qwenExitCode -is [ValueType] -and $qwenExitCode -isnot [bool] -and
            [int64]$qwenExitCode -ge -2147483648 -and [int64]$qwenExitCode -le 2147483647) {
            $failureProjection.qwen_exit_code = [int]$qwenExitCode
        }
        if ($null -ne $runtimeProjectionExitCode) { $failureProjection.runtime_projection_exit_code = [int]$runtimeProjectionExitCode }
        foreach ($field in @('session_id', 'session_id_hash', 'turns', 'tool_calls', 'wall_time_seconds', 'session_ended', 'terminal_reason', 'terminal_source', 'event_coverage', 'budget_stop', 'loop_status', 'loop_detector_version', 'tool_fingerprint')) {
            $property = $runtimeProjection.PSObject.Properties[$field]
            if ($null -ne $property) { $failureProjection[$field] = $property.Value }
        }
        $partialObservationProperty = $runtimeProjection.PSObject.Properties['partial_observation']
        if ($null -ne $partialObservationProperty -and $partialObservationProperty.Value -is [pscustomobject]) {
            $partialObservation = [ordered]@{}
            foreach ($field in @(
                'event_lines_observed', 'assistant_turns_observed', 'tool_dispatches_observed',
                'tool_results_observed', 'tool_errors_observed', 'agent_dispatches_observed'
            )) {
                $property = $partialObservationProperty.Value.PSObject.Properties[$field]
                if ($null -ne $property -and $property.Value -is [ValueType] -and
                    $property.Value -isnot [bool] -and [int64]$property.Value -ge 0 -and
                    [int64]$property.Value -le 2147483647) {
                    $partialObservation[$field] = [int]$property.Value
                }
            }
            $terminalResultSeen = $partialObservationProperty.Value.PSObject.Properties['terminal_result_seen']
            if ($null -ne $terminalResultSeen -and $terminalResultSeen.Value -is [bool]) {
                $partialObservation.terminal_result_seen = [bool]$terminalResultSeen.Value
            }
            if ($partialObservation.Count -eq 7) {
                $failureProjection.partial_observation = [pscustomobject]$partialObservation
            }
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
        $processOutputDiagnosticProperty = $runtimeProjection.PSObject.Properties['process_output_diagnostic']
        if ($null -ne $processOutputDiagnosticProperty -and
            $processOutputDiagnosticProperty.Value -is [pscustomobject] -and
            [string]$processOutputDiagnosticProperty.Value.capture_status -in @('PROJECTED', 'LIMIT_EXCEEDED', 'UNAVAILABLE')) {
            $failureProjection.process_output_diagnostic = $processOutputDiagnosticProperty.Value
        }
        $failureProjection | ConvertTo-Json -Compress -Depth 4
    }
    else {
        @{ status = 'QWEN_COMMAND_FAILED'; reason = 'QWEN_COMMAND_FAILED' } | ConvertTo-Json -Compress
    }
    if ($qwenExitCode -is [ValueType] -and $qwenExitCode -isnot [bool]) { exit ([int]$qwenExitCode) }
    exit 4
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
