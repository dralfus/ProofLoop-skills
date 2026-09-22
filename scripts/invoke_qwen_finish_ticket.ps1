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

function Write-GuardStatus {
    param(
        [Parameter(Mandatory)] [string]$Status,
        [string]$Reason,
        [string]$LaunchId,
        [object]$Diagnostic
    )

    $result = @{ status = $Status }
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
    param([Parameter(Mandatory)] [object]$Report)

    if ($null -eq $Report -or $Report -isnot [pscustomobject]) {
        return @{ valid = $false; reason = 'MALFORMED_REPORT' }
    }
    $allowedFields = @('status', 'baseline', 'facts', 'state_owner', 'callback_boundary', 'acceptance_risk', 'stop_reason', 'writes')
    $unexpected = @($Report.PSObject.Properties.Name | Where-Object { $_ -notin $allowedFields })
    if ($unexpected.Count -gt 0) {
        return @{ valid = $false; reason = 'MALFORMED_REPORT' }
    }
    if ($Report.PSObject.Properties['status'] -eq $null -or [string]$Report.status -notin @('EVIDENCE_FOUND', 'BLOCKED', 'QWEN_UNUSABLE')) {
        return @{ valid = $false; reason = 'INVALID_STATUS' }
    }
    $writesProperty = $Report.PSObject.Properties['writes']
    $stopReasonProperty = $Report.PSObject.Properties['stop_reason']
    if ($null -eq $writesProperty -or $null -eq $stopReasonProperty) {
        return @{ valid = $false; reason = 'MALFORMED_REPORT' }
    }
    if ($null -eq $Report.writes -or $Report.writes -isnot [array]) {
        return @{ valid = $false; reason = 'MALFORMED_REPORT' }
    }
    foreach ($write in @($Report.writes)) {
        if ($write -isnot [string]) {
            return @{ valid = $false; reason = 'MALFORMED_REPORT' }
        }
    }
    if (@($Report.writes).Count -gt 0) {
        return @{ valid = $false; reason = 'READ_ONLY_VIOLATION' }
    }
    if ($null -ne $Report.stop_reason -and $Report.stop_reason -isnot [string]) {
        return @{ valid = $false; reason = 'MALFORMED_REPORT' }
    }
    if ([string]$Report.status -eq 'EVIDENCE_FOUND' -and ($null -ne $Report.stop_reason -or @($Report.writes).Count -ne 0)) {
        return @{ valid = $false; reason = 'MALFORMED_REPORT' }
    }
    if ([string]$Report.status -ne 'EVIDENCE_FOUND') {
        return @{ valid = $false; reason = 'RECON_REPORT_BLOCKED' }
    }
    foreach ($field in @('baseline', 'state_owner', 'callback_boundary', 'acceptance_risk')) {
        if ($Report.PSObject.Properties[$field] -eq $null -or $Report.$field -isnot [string] -or -not $Report.$field.Trim()) {
            return @{ valid = $false; reason = 'INCOMPLETE_RECON' }
        }
    }
    if ($Report.PSObject.Properties['facts'] -eq $null) {
        return @{ valid = $false; reason = 'INSUFFICIENT_FACTS' }
    }
    if ($Report.facts -isnot [array]) {
        return @{ valid = $false; reason = 'MALFORMED_FACT' }
    }
    $facts = @($Report.facts)
    if ($facts.Count -lt 3) {
        return @{ valid = $false; reason = 'INSUFFICIENT_FACTS' }
    }
    foreach ($fact in $facts) {
        if ($fact -isnot [pscustomobject] -or @($fact.PSObject.Properties.Name).Count -ne 3 -or
            $fact.PSObject.Properties['file'] -eq $null -or $fact.file -isnot [string] -or -not $fact.file.Trim() -or
            $fact.PSObject.Properties['line'] -eq $null -or ($fact.line -isnot [int32] -and $fact.line -isnot [int64]) -or $fact.line -lt 1 -or
            $fact.PSObject.Properties['fact'] -eq $null -or $fact.fact -isnot [string] -or -not $fact.fact.Trim()) {
            return @{ valid = $false; reason = 'MALFORMED_FACT' }
        }
    }
    return @{ valid = $true; report = $Report }
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
    param([Parameter(Mandatory)] [string]$Output)

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
    return Test-ReconReport -Report $parsed
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

$cliCompatibilityConsumer = Join-Path $PSScriptRoot 'invoke_qwen_finish_ticket_cli.ps1'
if ($Mode -eq 'protocol') {
    $qwenArguments = @(
        '--max-session-turns', [string]$limits.max_session_turns,
        '--max-tool-calls', [string]$limits.max_tool_calls,
        '--max-wall-time', $limits.max_wall_time,
        '--max-subagent-depth', [string]$limits.max_subagent_depth,
        '--prompt', "/finish-ticket ticket $Ticket"
    )

    try {
        $qwenExitCode = 0
        & $cliCompatibilityConsumer -Mode protocol -QwenCommand $QwenCommand -QwenArgumentsJson ($qwenArguments | ConvertTo-Json -Compress) *> $null
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

$reconValidation = Convert-ReconOutput -Output $reconOutput
if (-not $reconValidation.valid) {
    Write-GuardStatus -Status 'QWEN_UNUSABLE' -Reason ([string]$reconValidation.reason) -LaunchId $launchId
    exit 4
}
if ($reconValidation.report.baseline -ne $reconFixedPoint) {
    Write-GuardStatus -Status 'QWEN_UNUSABLE' -Reason 'BASELINE_MISMATCH' -LaunchId $launchId
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
