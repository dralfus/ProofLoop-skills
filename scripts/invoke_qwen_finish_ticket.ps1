[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[A-Za-z0-9._/-]+$')]
    [string]$Ticket,

    [ValidateSet('protocol', 'recon')]
    [string]$Mode = 'protocol',

    [switch]$SafeMode,

    [string]$SettingsPath = (Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)) '.qwen\settings.json'),

    [string]$ExtensionRoot,

    [string]$ReconWorktree,

    [string]$ReconSchemaPath = (Join-Path $PSScriptRoot '..\plugins\agentic-development-workflow\skills\finish-ticket\references\qwen-assist-recon.schema.json'),

    [string]$ReceiptDirectory = (Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)) 'ProofLoop Skills\qwen-session-guards'),

    [string]$QwenCommand = 'qwen.cmd',

    [ValidatePattern('^[A-Za-z0-9._/-]+$')]
    [string]$CredentialTarget = 'ProofLoop/Qwen/OpenAI'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:LauncherClock = [Diagnostics.Stopwatch]::StartNew()
$script:ModelRequestStarted = $false

function Write-GuardStatus {
    param(
        [Parameter(Mandatory)] [string]$Status,
        [string]$Reason,
        [string]$LaunchId,
        [object]$Diagnostic
    )

    $result = @{ status = $Status }
    $result.mode = $Mode
    $result.duration_ms = [long]$script:LauncherClock.ElapsedMilliseconds
    $result.terminal_reason = if ($Reason) { $Reason } else { $Status }
    $result.turn_count = if ($script:ModelRequestStarted) { 'NOT_AVAILABLE' } else { 0 }
    $result.tool_call_count = if ($script:ModelRequestStarted) { 'NOT_AVAILABLE' } else { 0 }
    if ($Reason) {
        $result.reason = $Reason
    }
    if ($LaunchId) {
        $result.launch_id = $LaunchId
    }
    if ($null -ne $Diagnostic) {
        $result.diagnostic = $Diagnostic
    }
    if ($Mode -eq 'recon') {
        $result.role_dispatch = $false
        $result.subagent_dispatch = $false
        $result.acceptance = $false
    }
    $result | ConvertTo-Json -Compress
}

function Stop-Guard {
    param([Parameter(Mandatory)] [string]$Reason)

    Write-GuardStatus -Status 'BLOCKED_CAPABILITY' -Reason $Reason
    exit 3
}

function Get-ReconFixedPoint {
    param([Parameter(Mandatory)] [string]$Worktree)

    if (-not (Test-Path -LiteralPath $Worktree -PathType Container)) {
        Stop-Guard -Reason 'WORKTREE_UNAVAILABLE'
    }

    try {
        $isWorktree = (& git -C $Worktree rev-parse --is-inside-work-tree 2>$null | Out-String).Trim()
        $status = (& git -C $Worktree status --porcelain --untracked-files=all 2>$null | Out-String).Trim()
        $fixedPoint = (& git -C $Worktree rev-parse HEAD 2>$null | Out-String).Trim()
    }
    catch {
        Stop-Guard -Reason 'WORKTREE_UNAVAILABLE'
    }

    if ($isWorktree -ne 'true') {
        Stop-Guard -Reason 'WORKTREE_UNAVAILABLE'
    }
    if ($status) {
        Stop-Guard -Reason 'WORKTREE_NOT_CLEAN'
    }
    if ($fixedPoint -notmatch '^[0-9a-f]{40,64}$') {
        Stop-Guard -Reason 'FIXED_POINT_UNAVAILABLE'
    }
    return $fixedPoint
}

function Test-ReconReport {
    param(
        [Parameter(Mandatory)] [object]$Report,
        [AllowEmptyString()] [string]$ExpectedBaseline
    )

    $reportPath = [IO.Path]::GetTempFileName()
    try {
        $Report | ConvertTo-Json -Depth 16 -Compress | Set-Content -LiteralPath $reportPath -Encoding utf8
        $arguments = @(
            (Join-Path $PSScriptRoot 'recon_report_contract.py'),
            '--input-file', $reportPath
        )
        if ($PSBoundParameters.ContainsKey('ExpectedBaseline')) {
            $arguments += @('--expected-baseline', $ExpectedBaseline)
        }
        $verdictJson = & python @arguments 2>$null | Out-String
        $pythonExitCode = if (Test-Path Variable:global:LASTEXITCODE) { [int]$global:LASTEXITCODE } else { 0 }
        if ($pythonExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($verdictJson)) {
            return @{ valid = $false; reason = 'MALFORMED_REPORT' }
        }
        try {
            $verdict = $verdictJson | ConvertFrom-Json
        }
        catch {
            return @{ valid = $false; reason = 'MALFORMED_REPORT' }
        }
        if ($verdict.valid -eq $true) {
            return @{ valid = $true; report = $Report }
        }
        if ($verdict.reason -is [string] -and $verdict.reason.Trim()) {
            return @{ valid = $false; reason = [string]$verdict.reason }
        }
        return @{ valid = $false; reason = 'MALFORMED_REPORT' }
    }
    finally {
        Remove-Item -LiteralPath $reportPath -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-QwenGuardPolicy {
    param([Parameter(Mandatory)] [object]$PolicyInput)

    $inputPath = [IO.Path]::GetTempFileName()
    try {
        $PolicyInput | ConvertTo-Json -Depth 16 -Compress | Set-Content -LiteralPath $inputPath -Encoding utf8
        $policyJson = & python (Join-Path $PSScriptRoot 'qwen_guard_policy.py') '--input-file' $inputPath 2>$null | Out-String
        $pythonExitCode = if (Test-Path Variable:global:LASTEXITCODE) { [int]$global:LASTEXITCODE } else { 0 }
        if ($pythonExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($policyJson)) {
            return [pscustomobject]@{ status = 'BLOCKED_CAPABILITY'; reason = 'GUARD_POLICY_UNAVAILABLE' }
        }
        try {
            return $policyJson | ConvertFrom-Json
        }
        catch {
            return [pscustomobject]@{ status = 'BLOCKED_CAPABILITY'; reason = 'GUARD_POLICY_MALFORMED' }
        }
    }
    finally {
        Remove-Item -LiteralPath $inputPath -Force -ErrorAction SilentlyContinue
    }
}

function Get-QwenRegistryArguments {
    param([Parameter(Mandatory)] [string]$Mode, [Parameter(Mandatory)] [string]$Ticket)

    try {
        $rendered = & python (Join-Path $PSScriptRoot 'qwen_invocation_contract.py') `
            '--mode' $Mode '--ticket' $Ticket 2>$null | Out-String
        $exitCode = if (Test-Path Variable:global:LASTEXITCODE) { [int]$global:LASTEXITCODE } else { 0 }
        if ($exitCode -ne 0 -or [string]::IsNullOrWhiteSpace($rendered)) { Stop-Guard -Reason 'INVOCATION_CONTRACT_UNAVAILABLE' }
        $argv = @($rendered | ConvertFrom-Json)
        if ($argv.Count -eq 0 -or @($argv | Where-Object { $_ -isnot [string] }).Count -gt 0) { Stop-Guard -Reason 'INVOCATION_CONTRACT_MALFORMED' }
        return $argv
    }
    catch {
        Stop-Guard -Reason 'INVOCATION_CONTRACT_UNAVAILABLE'
    }
}

function New-ReconFreshEvidenceId {
    param([Parameter(Mandatory)] [string]$Directory)

    $used = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    try {
        if (Test-Path -LiteralPath $Directory -PathType Container) {
            foreach ($path in @(Get-ChildItem -LiteralPath $Directory -Filter 'QWEN_RECON_GUARD-*.json' -File)) {
                $metadata = Get-Content -LiteralPath $path.FullName -Raw | ConvertFrom-Json
                $value = $metadata.PSObject.Properties['fresh_evidence_id']
                if ($null -ne $value -and $value.Value -is [string] -and $value.Value -match '^[0-9a-f]{32}$') {
                    [void]$used.Add($value.Value)
                }
            }
        }
    }
    catch {
        Stop-Guard -Reason 'RECEIPT_REGISTRY_UNAVAILABLE'
    }

    do {
        $candidate = [guid]::NewGuid().ToString('N')
    } while ($used.Contains($candidate))
    return $candidate
}

function Convert-ReconOutput {
    param(
        [Parameter(Mandatory)] [string]$Output,
        [AllowEmptyString()] [string]$ExpectedBaseline
    )

    if (-not $Output.Trim()) {
        return @{ valid = $false; reason = 'INVALID_JSON_OUTPUT' }
    }
    try {
        $parsed = $Output | ConvertFrom-Json
    }
    catch {
        return @{ valid = $false; reason = 'INVALID_JSON_OUTPUT' }
    }
    if ($parsed -is [array]) {
        if ($parsed.Count -eq 0 -or $parsed[-1].type -ne 'result' -or $parsed[-1].structured_result -isnot [pscustomobject]) {
            return @{ valid = $false; reason = 'INVALID_JSON_OUTPUT' }
        }
        $parsed = $parsed[-1].structured_result
    }
    return Test-ReconReport -Report $parsed -ExpectedBaseline $ExpectedBaseline
}

function Get-QwenFailureProjection {
    param([AllowEmptyString()] [string]$Output)

    $allowedReasons = @('STRUCTURED_OUTPUT_MISSING', 'QWEN_JSON_ERROR_RESULT', 'QWEN_COMMAND_FAILED', 'QWEN_COMMAND_UNAVAILABLE')
    $diagnostic = [ordered]@{
        stdout_present = $false
        stderr_present = $false
        stdout_json = $false
        stderr_json = $false
        structured_output_channel = 'none'
        json_shape = 'none'
        terminal_result = $false
        terminal_is_error = $false
        terminal_subtype = 'none'
        error_message_present = $false
        error_message_category = 'none'
        envelope_is_error = $false
        envelope_subtype = 'none'
        envelope_error_message_present = $false
        envelope_error_message_category = 'none'
    }
    if ([string]::IsNullOrWhiteSpace($Output)) {
        return @{ reason = 'QWEN_COMMAND_FAILED'; diagnostic = $diagnostic }
    }
    try {
        $projection = $Output | ConvertFrom-Json
    }
    catch {
        return @{ reason = 'QWEN_COMMAND_FAILED'; diagnostic = $diagnostic }
    }
    $diagnosticProperty = $projection.PSObject.Properties['diagnostic']
    if ($null -ne $diagnosticProperty -and $diagnosticProperty.Value -is [pscustomobject]) {
        foreach ($field in @('stdout_present', 'stderr_present', 'stdout_json', 'stderr_json')) {
            $fieldProperty = $diagnosticProperty.Value.PSObject.Properties[$field]
            if ($null -ne $fieldProperty -and $fieldProperty.Value -is [bool]) {
                $diagnostic[$field] = [bool]$fieldProperty.Value
            }
        }
        $channelProperty = $diagnosticProperty.Value.PSObject.Properties['structured_output_channel']
        if ($null -ne $channelProperty -and [string]$channelProperty.Value -in @('none', 'stdout', 'stderr', 'stdout+stderr')) {
            $diagnostic.structured_output_channel = [string]$channelProperty.Value
        }
        $shapeProperty = $diagnosticProperty.Value.PSObject.Properties['json_shape']
        if ($null -ne $shapeProperty -and [string]$shapeProperty.Value -in @('none', 'array', 'object', 'other')) {
            $diagnostic.json_shape = [string]$shapeProperty.Value
        }
        foreach ($field in @('terminal_result', 'terminal_is_error', 'error_message_present')) {
            $fieldProperty = $diagnosticProperty.Value.PSObject.Properties[$field]
            if ($null -ne $fieldProperty -and $fieldProperty.Value -is [bool]) {
                $diagnostic[$field] = [bool]$fieldProperty.Value
            }
        }
        $subtypeProperty = $diagnosticProperty.Value.PSObject.Properties['terminal_subtype']
        if ($null -ne $subtypeProperty -and [string]$subtypeProperty.Value -in @('none', 'success', 'error_during_execution', 'other')) {
            $diagnostic.terminal_subtype = [string]$subtypeProperty.Value
        }
        $categoryProperty = $diagnosticProperty.Value.PSObject.Properties['error_message_category']
        if ($null -ne $categoryProperty -and [string]$categoryProperty.Value -in @('none', 'structured_output_missing', 'auth_or_forbidden', 'transport', 'other')) {
            $diagnostic.error_message_category = [string]$categoryProperty.Value
        }
        $envelopeIsErrorProperty = $diagnosticProperty.Value.PSObject.Properties['envelope_is_error']
        if ($null -ne $envelopeIsErrorProperty -and $envelopeIsErrorProperty.Value -is [bool]) {
            $diagnostic.envelope_is_error = [bool]$envelopeIsErrorProperty.Value
        }
        $envelopeSubtypeProperty = $diagnosticProperty.Value.PSObject.Properties['envelope_subtype']
        if ($null -ne $envelopeSubtypeProperty -and [string]$envelopeSubtypeProperty.Value -in @('none', 'success', 'error_during_execution', 'other')) {
            $diagnostic.envelope_subtype = [string]$envelopeSubtypeProperty.Value
        }
        $envelopeMessagePresentProperty = $diagnosticProperty.Value.PSObject.Properties['envelope_error_message_present']
        if ($null -ne $envelopeMessagePresentProperty -and $envelopeMessagePresentProperty.Value -is [bool]) {
            $diagnostic.envelope_error_message_present = [bool]$envelopeMessagePresentProperty.Value
        }
        $envelopeCategoryProperty = $diagnosticProperty.Value.PSObject.Properties['envelope_error_message_category']
        if ($null -ne $envelopeCategoryProperty -and [string]$envelopeCategoryProperty.Value -in @('none', 'structured_output_missing', 'auth_or_forbidden', 'transport', 'other')) {
            $diagnostic.envelope_error_message_category = [string]$envelopeCategoryProperty.Value
        }
    }
    $reasonProperty = $projection.PSObject.Properties['reason']
    if ($null -ne $reasonProperty -and $allowedReasons -contains [string]$reasonProperty.Value) {
        return @{ reason = [string]$reasonProperty.Value; diagnostic = $diagnostic }
    }
    return @{ reason = 'QWEN_COMMAND_FAILED'; diagnostic = $diagnostic }
}

if ($SafeMode) {
    Stop-Guard -Reason 'SAFE_MODE_REQUESTED'
}

$reconFixedPoint = $null
$resolvedReconSchemaPath = $null
if ($Mode -eq 'recon') {
    if (-not $ReconWorktree) {
        Stop-Guard -Reason 'RECON_WORKTREE_REQUIRED'
    }
    if (-not (Test-Path -LiteralPath $ReconSchemaPath -PathType Leaf) -or (Split-Path -Leaf $ReconSchemaPath) -ne 'qwen-assist-recon.schema.json') {
        Stop-Guard -Reason 'RECON_SCHEMA_UNAVAILABLE'
    }
    try {
        $resolvedReconSchemaPath = (Resolve-Path -LiteralPath $ReconSchemaPath).Path
    }
    catch {
        Stop-Guard -Reason 'RECON_SCHEMA_UNAVAILABLE'
    }
    $reconFixedPoint = Get-ReconFixedPoint -Worktree $ReconWorktree
}

$requiredCliCapabilities = if ($Mode -eq 'recon') {
    @(
        '--prompt',
        '--bare',
        '--approval-mode',
        '--output-format',
        '--json-schema',
        '--max-session-turns',
        '--max-tool-calls',
        '--max-wall-time',
        '--max-subagent-depth',
        '--exclude-tools',
        '--disabled-slash-commands'
    )
}
else {
    @(
        '--prompt',
        '--max-session-turns',
        '--max-tool-calls',
        '--max-wall-time',
        '--max-subagent-depth'
    )
}

try {
    $helpOutput = (& $QwenCommand '--help' 2>&1 | Out-String)
    $helpExitCode = if (Test-Path Variable:global:LASTEXITCODE) {
        [int]$global:LASTEXITCODE
    }
    else {
        0
    }
}
catch {
    Stop-Guard -Reason 'QWEN_CLI_UNAVAILABLE'
}

$missingCliCapabilities = @(
    $requiredCliCapabilities | Where-Object { $helpOutput -notlike "*$_*" }
)
if ($helpExitCode -ne 0 -or $missingCliCapabilities.Count -gt 0) {
    Stop-Guard -Reason 'QWEN_CLI_CAPABILITY_MISSING'
}

try {
    $settings = Get-Content -LiteralPath $SettingsPath -Raw | ConvertFrom-Json
}
catch {
    Stop-Guard -Reason 'LOCAL_SETTINGS_UNAVAILABLE'
}

$modelSettingsProperty = $settings.PSObject.Properties['model']
$modelSettings = if ($null -eq $modelSettingsProperty -or $modelSettingsProperty.Value -isnot [pscustomobject]) {
    $null
}
else {
    $modelSettingsProperty.Value
}
$skipLoopDetection = if ($null -eq $modelSettings) { $null } else { $modelSettings.PSObject.Properties['skipLoopDetection'] }
$maxToolCallsPerTurn = if ($null -eq $modelSettings) { $null } else { $modelSettings.PSObject.Properties['maxToolCallsPerTurn'] }
$maxSubagentDepth = if ($null -eq $modelSettings) { $null } else { $modelSettings.PSObject.Properties['maxSubagentDepth'] }
$reasoningEffort = if ($null -eq $modelSettings) { $null } else { $modelSettings.PSObject.Properties['reasoningEffort'] }
if ($null -eq $skipLoopDetection -or $skipLoopDetection.Value -ne $false) {
    Stop-Guard -Reason 'LOOP_DETECTION_DISABLED'
}
if ($null -eq $maxToolCallsPerTurn -or $maxToolCallsPerTurn.Value -isnot [long] -or $maxToolCallsPerTurn.Value -lt 1 -or $maxToolCallsPerTurn.Value -gt 20) {
    Stop-Guard -Reason 'MAX_TOOL_CALLS_INVALID'
}
if ($null -eq $maxSubagentDepth -or $maxSubagentDepth.Value -isnot [long]) {
    Stop-Guard -Reason 'MAX_SUBAGENT_DEPTH_INVALID'
}
if ($maxSubagentDepth.Value -gt 1) {
    Stop-Guard -Reason 'MAX_SUBAGENT_DEPTH_EXCEEDED'
}
if ($maxSubagentDepth.Value -ne 1) {
    Stop-Guard -Reason 'MAX_SUBAGENT_DEPTH_INVALID'
}

$reasoningEffortValue = if ($null -eq $reasoningEffort) { '' } else { [string]$reasoningEffort.Value }
try {
    $modePolicyArguments = @('--mode', $Mode, '--reasoning-effort', $reasoningEffortValue)
    $modePolicyJson = & python (Join-Path $PSScriptRoot 'qwen_mode_contract.py') @modePolicyArguments 2>$null | Out-String
    $modePolicyExitCode = if (Test-Path Variable:global:LASTEXITCODE) { [int]$global:LASTEXITCODE } else { 0 }
    if ($modePolicyExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($modePolicyJson)) {
        Stop-Guard -Reason 'MODE_POLICY_UNAVAILABLE'
    }
    $modePolicy = $modePolicyJson | ConvertFrom-Json
}
catch {
    Stop-Guard -Reason 'MODE_POLICY_UNAVAILABLE'
}
if ($modePolicy.status -ne 'QWEN_MODE_READY') {
    Write-GuardStatus -Status ([string]$modePolicy.status) -Reason ([string]$modePolicy.reason)
    exit 3
}

try {
    $extensionManifest = Get-Content -LiteralPath (Join-Path $ExtensionRoot 'qwen-extension.json') -Raw | ConvertFrom-Json
}
catch {
    Stop-Guard -Reason 'PROOFLOOP_EXTENSION_MISSING'
}
if ($null -eq $extensionManifest.PSObject.Properties['name'] -or $extensionManifest.PSObject.Properties['name'].Value -ne 'proofloop-skills') {
    Stop-Guard -Reason 'PROOFLOOP_EXTENSION_MISSING'
}

$limits = if ($Mode -eq 'recon') {
    [ordered]@{
        max_session_turns = 3
        max_tool_calls = 6
        max_wall_time = '5m'
        max_subagent_depth = 1
    }
}
else {
    [ordered]@{
        max_session_turns = 20
        max_tool_calls = 20
        max_wall_time = '30m'
        max_subagent_depth = 1
    }
}
$launchId = [guid]::NewGuid().ToString('N')
$reconLedgerId = if ($Mode -eq 'recon') { [guid]::NewGuid().ToString('N') } else { $null }
$reconSessionId = if ($Mode -eq 'recon') { [guid]::NewGuid().ToString('N') } else { $null }
$reconFreshEvidenceId = $null
if ($Mode -eq 'recon') {
    try {
        [IO.Directory]::CreateDirectory($ReceiptDirectory) | Out-Null
    }
    catch {
        Stop-Guard -Reason 'RECEIPT_WRITE_FAILED'
    }
    $reconFreshEvidenceId = New-ReconFreshEvidenceId -Directory $ReceiptDirectory
}
$receipt = [ordered]@{
    receipt_type = if ($Mode -eq 'recon') { 'QWEN_RECON_GUARD' } else { 'QWEN_SESSION_GUARD' }
    receipt_version = 1
    launch_id = $launchId
    issued_at_utc = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
    mode = $Mode
    limits = $limits
    loop_detection = $true
    extension_available = $true
}
if ($Mode -eq 'recon') {
    $receipt.ledger_id = $reconLedgerId
    $receipt.session_id = $reconSessionId
    $receipt.fresh_evidence_id = $reconFreshEvidenceId
    $receipt.read_only = $true
    $receipt.role_dispatch = $false
    $receipt.subagent_dispatch = $false
    $receipt.acceptance = $false
    $receipt.structured_output = $true
    $receipt.worktree_clean = $true
    $receipt.fixed_point = $reconFixedPoint
}

try {
    [IO.Directory]::CreateDirectory($ReceiptDirectory) | Out-Null
    $receiptPrefix = if ($Mode -eq 'recon') { 'QWEN_RECON_GUARD' } else { 'QWEN_SESSION_GUARD' }
    $receiptPath = Join-Path $ReceiptDirectory "$receiptPrefix-$launchId.json"
    [IO.File]::WriteAllText($receiptPath, ($receipt | ConvertTo-Json -Compress -Depth 3), [Text.UTF8Encoding]::new($false))
}
catch {
    Stop-Guard -Reason 'RECEIPT_WRITE_FAILED'
}

$guardWorktree = @{ available = $true }
if ($Mode -eq 'recon') {
    $guardWorktree.clean = $true
    $guardWorktree.fixed_point = $reconFixedPoint
}
$guardInput = [ordered]@{
    operation = 'guard_preflight'
    mode = $Mode
    now_utc = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
    max_receipt_age_seconds = 300
    settings = @{
        skipLoopDetection = [bool]$skipLoopDetection.Value
        maxToolCallsPerTurn = [int]$maxToolCallsPerTurn.Value
        maxSubagentDepth = [int]$maxSubagentDepth.Value
    }
    worktree = $guardWorktree
    capabilities = @{ markers = @($requiredCliCapabilities + 'plan') }
    receipt = $receipt
    terminal_stop = $false
}
$guardDecision = Invoke-QwenGuardPolicy -PolicyInput $guardInput
if ($guardDecision.status -ne 'QWEN_GUARD_READY') {
    $guardExitCode = if ($guardDecision.status -eq 'BLOCKED_CAPABILITY') { 3 } else { 4 }
    Write-GuardStatus -Status ([string]$guardDecision.status) -Reason ([string]$guardDecision.reason) -LaunchId $launchId
    exit $guardExitCode
}

$cliCompatibilityConsumer = Join-Path $PSScriptRoot 'invoke_qwen_finish_ticket_cli.ps1'
if ($Mode -eq 'protocol') {
    $qwenArguments = @(Get-QwenRegistryArguments -Mode 'protocol' -Ticket $Ticket)

    try {
        $qwenExitCode = 0
        $script:ModelRequestStarted = $true
        $outputTokenLimit = [int]$modePolicy.process_environment.QWEN_CODE_MAX_OUTPUT_TOKENS
        & $cliCompatibilityConsumer -Mode protocol -QwenCommand $QwenCommand `
            -QwenArgumentsJson ($qwenArguments | ConvertTo-Json -Compress) -OutputTokenLimit $outputTokenLimit *> $null
        if (Test-Path Variable:global:LASTEXITCODE) {
            $qwenExitCode = $global:LASTEXITCODE
        }
    }
    catch {
        Write-GuardStatus -Status 'QWEN_COMMAND_FAILED' -Reason 'QWEN_COMMAND_UNAVAILABLE' -LaunchId $launchId
        exit 4
    }

    if ($qwenExitCode -ne 0) {
        Write-GuardStatus -Status 'QWEN_COMMAND_FAILED' -Reason 'QWEN_COMMAND_FAILED' -LaunchId $launchId
        exit $qwenExitCode
    }

    Write-GuardStatus -Status 'QWEN_SESSION_GUARD_READY' -LaunchId $launchId
    exit 0
}

try {
    $reconOutput = (& $cliCompatibilityConsumer -Mode recon -QwenCommand $QwenCommand -Ticket $Ticket -SchemaPath $resolvedReconSchemaPath -Worktree $ReconWorktree -ReconBaseline $reconFixedPoint -CredentialTarget $CredentialTarget 2>$null | Out-String).Trim()
    $qwenExitCode = if (Test-Path Variable:global:LASTEXITCODE) { [int]$global:LASTEXITCODE } else { 0 }
}
catch {
    Write-GuardStatus -Status 'QWEN_UNUSABLE' -Reason 'QWEN_COMMAND_UNAVAILABLE' -LaunchId $launchId
    exit 4
}

if ($qwenExitCode -ne 0) {
    $failureProjection = Get-QwenFailureProjection -Output $reconOutput
    Write-GuardStatus -Status 'QWEN_UNUSABLE' -Reason $failureProjection.reason -LaunchId $launchId -Diagnostic $failureProjection.diagnostic
    exit 4
}

$reconValidation = Convert-ReconOutput -Output $reconOutput -ExpectedBaseline $reconFixedPoint
if (-not $reconValidation.valid) {
    Write-GuardStatus -Status 'QWEN_UNUSABLE' -Reason ([string]$reconValidation.reason) -LaunchId $launchId
    exit 4
}
@{
    status = 'QWEN_RECON_READY'
    launch_id = $launchId
    role_dispatch = $false
    subagent_dispatch = $false
    acceptance = $false
    read_only = $true
    structured_output_valid = $true
    writes = $false
    implementation = $false
    report = $reconValidation.report
} | ConvertTo-Json -Compress -Depth 8
