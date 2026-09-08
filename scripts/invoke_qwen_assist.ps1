[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$Prompt,

    [Parameter(Mandatory)]
    [string]$SchemaPath,

    [Parameter(Mandatory)]
    [string]$Worktree
)

$ErrorActionPreference = 'Stop'
$requiredMarkers = @(
    '--prompt', '--output-format', '--json-schema', '--worktree',
    '--approval-mode', '--max-session-turns', '--max-wall-time',
    '--max-tool-calls', '--exclude-tools'
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
# This wrapper preserves that supported configuration and adds no model,
# fallback or permissive flags. The Qwen plan mode is the technical write and
# command guard; its output is still validated by qwen_assist.py.
& qwen `
    '--approval-mode' 'plan' `
    '--output-format' 'json' `
    '--json-schema' "@$SchemaPath" `
    '--worktree' $Worktree `
    '--max-session-turns' '12' `
    '--max-wall-time' '10m' `
    '--max-tool-calls' '20' `
    '--max-subagent-depth' '1' `
    '--exclude-tools' 'Agent' `
    '--disabled-slash-commands' 'review,loop' `
    '--prompt' $Prompt
exit $LASTEXITCODE
