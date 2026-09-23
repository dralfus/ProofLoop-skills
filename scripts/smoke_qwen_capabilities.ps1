[CmdletBinding()]
param(
    [string]$QwenCommand = 'qwen',

    [string]$EvidencePath = (Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)) ('ProofLoop Skills\qwen-capability-smoke-' + [guid]::NewGuid().ToString('N') + '.json'))
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

try {
    $registryJson = & python (Join-Path $PSScriptRoot 'qwen_invocation_contract.py') '--mode' 'capability_smoke' '--contract' 2>$null | Out-String
    $registryExitCode = if (Test-Path Variable:global:LASTEXITCODE) { [int]$global:LASTEXITCODE } else { 0 }
    if ($registryExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($registryJson)) { throw 'Invocation registry unavailable.' }
    $invocationContract = $registryJson | ConvertFrom-Json
    $markerNames = @{
        '--prompt' = 'prompt'
        '--max-session-turns' = 'max_session_turns'
        '--max-tool-calls' = 'max_tool_calls'
        '--max-wall-time' = 'max_wall_time'
        '--max-subagent-depth' = 'max_subagent_depth'
    }
    $requiredCapabilities = [ordered]@{}
    foreach ($marker in @($invocationContract.required_markers)) {
        if (-not $markerNames.ContainsKey([string]$marker)) { throw 'Invocation registry capability marker is unsupported.' }
        $requiredCapabilities[$markerNames[[string]$marker]] = [string]$marker
    }
}
catch {
    @{ status = 'BLOCKED_CAPABILITY'; reason = 'INVOCATION_CONTRACT_UNAVAILABLE'; role_dispatch = $false; acceptance = $false } | ConvertTo-Json -Compress
    exit 3
}

function Invoke-QwenProbe {
    param([Parameter(Mandatory)] [string]$Argument)

    try {
        $global:LASTEXITCODE = 0
        $output = (& $QwenCommand $Argument 2>&1 | Out-String)
        $exitCode = if (Test-Path Variable:global:LASTEXITCODE) {
            [int]$global:LASTEXITCODE
        }
        else {
            0
        }
        return [pscustomobject]@{
            output = $output
            exit_code = $exitCode
        }
    }
    catch {
        return [pscustomobject]@{
            output = ''
            exit_code = 1
        }
    }
}

$versionProbe = Invoke-QwenProbe -Argument '--version'
$versionMatch = [regex]::Match($versionProbe.output, '(?<!\d)(\d+\.\d+\.\d+)(?!\d)')
$version = if ($versionMatch.Success) { $versionMatch.Groups[1].Value } else { $null }

$helpProbe = Invoke-QwenProbe -Argument '--help'
$capabilityProjection = [ordered]@{}
foreach ($capability in $requiredCapabilities.GetEnumerator()) {
    $capabilityProjection[$capability.Key] = $helpProbe.output -like "*$($capability.Value)*"
}

$missingCapabilities = @(
    $capabilityProjection.GetEnumerator() |
        Where-Object { -not $_.Value } |
        ForEach-Object { $_.Key }
)

$status = 'QWEN_CLI_CAPABILITY_READY'
$reason = $null
if ($versionProbe.exit_code -ne 0 -or $helpProbe.exit_code -ne 0) {
    $status = 'QWEN_CLI_SMOKE_INCOMPLETE'
    $reason = 'QWEN_COMMAND_FAILED'
}
elseif ($null -eq $version -or $missingCapabilities.Count -gt 0) {
    $status = 'BLOCKED_CAPABILITY'
    $reason = if ($null -eq $version) { 'VERSION_UNOBSERVED' } else { 'QWEN_CLI_CAPABILITY_MISSING' }
}

$evidence = [ordered]@{
    receipt_type = 'QWEN_CLI_CAPABILITY_SMOKE'
    status = $status
    version = $version
    capabilities = $capabilityProjection
    role_dispatch = $false
    acceptance = $false
}
if ($reason) {
    $evidence.reason = $reason
}

try {
    [IO.Directory]::CreateDirectory((Split-Path -Parent $EvidencePath)) | Out-Null
    [IO.File]::WriteAllText(
        $EvidencePath,
        ($evidence | ConvertTo-Json -Compress -Depth 4),
        [Text.UTF8Encoding]::new($false)
    )
}
catch {
    $evidence.status = 'QWEN_CLI_SMOKE_INCOMPLETE'
    $evidence.reason = 'EVIDENCE_WRITE_FAILED'
}

$evidence | ConvertTo-Json -Compress -Depth 4
if ($evidence.status -eq 'QWEN_CLI_CAPABILITY_READY') {
    exit 0
}
exit 3
