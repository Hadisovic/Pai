#requires -Version 7.4
param([switch]$Check, [switch]$Handover)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$source = Join-Path $root 'source'
$python = Join-Path $source '.venv/Scripts/python.exe'
$revision = (Get-Content -LiteralPath (Join-Path $root 'revision.txt') -Raw).Trim()
$local = git -C $source rev-parse HEAD
if ($LASTEXITCODE -or $local -ne $revision -or $revision -notmatch '^[a-f0-9]{40}$') {
    throw 'Kirky source does not match its revision pin.'
}
if (git -C $source status --porcelain --untracked-files=no) { throw 'Kirky source has tracked changes.' }
$instance = Get-Content -LiteralPath (Join-Path $root 'instance.json') -Raw | ConvertFrom-Json
$policy = Get-Content -LiteralPath (Join-Path $root 'policy.json') -Raw | ConvertFrom-Json
if ($instance.name -ne 'Kirky' -or $policy.guild_id -ne $instance.guild_id -or
    $policy.channel_ids.Count -ne 1 -or $policy.channel_ids[0] -ne $instance.channel_id) {
    throw 'Check the Kirky instance name and exclusive test scope.'
}
if ($Check) {
    & $python -m pai --doctor
    if ($LASTEXITCODE) { throw 'Kirky local doctor failed.' }
    "Local preflight passed at $revision. Live activation gates were not changed."
    return
}
if (-not $instance.distress_reviewed -or -not $instance.bot_user_id -or
    $instance.bot_user_id -eq $instance.stable_bot_id -or -not $policy.admin_opt_in -or
    -not $policy.consenting_member_ids.Count -or $policy.media_opt_in) {
    throw 'Kirky requires a separate bot ID, safety review and approved channel consent. Media stays off.'
}
function Read-PrivateSecret([string]$file) {
    $secure = (Get-Content -LiteralPath (Join-Path $root "secrets/$file") -Raw).Trim() | ConvertTo-SecureString
    [System.Net.NetworkCredential]::new('', $secure).Password
}
$child = @{
    DISCORD_TOKEN = $null
    PAI_GROQ_KEY = $null
    KIRKY_DISCORD_TOKEN = Read-PrivateSecret 'discord.dpapi'
    KIRKY_GROQ_KEY = $null
    PYTHONNOUSERSITE = '1'
}
$argsList = @(
    '-u', '-m', 'pai', '--connect', '--instance-config', 'instance.json', '--policy', 'policy.json',
    '--database', 'kirky.sqlite', '--expected-revision', $revision,
    '--conversation-engine', 'timeline-roles', '--text-model', 'qwen'
)
if ($policy.external_ai_opt_in) {
    if ($Handover) {
        if (-not $env:KIRKY_GROQ_KEY) { throw 'Supply the shared key transiently from its approved local secret store.' }
        $child.KIRKY_GROQ_KEY = $env:KIRKY_GROQ_KEY
        $argsList += '--quota-handover'
    } elseif (-not $instance.isolated_free_quota_verified) {
        throw 'Hosted inference is blocked without approved isolated Free quota.'
    } else {
        $child.KIRKY_GROQ_KEY = Read-PrivateSecret 'groq.dpapi'
    }
    $argsList += '--groq-free'
}
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$errLog = Join-Path $root "logs/$stamp.err.log"
$proc = Start-Process -FilePath $python -ArgumentList $argsList -WorkingDirectory $root `
    -Environment $child -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $root "logs/$stamp.out.log") -RedirectStandardError $errLog
if ($proc.WaitForExit(2500)) {
    throw "Kirky exited during startup. See $errLog."
}
"Kirky launched. Confirm Discord readiness in $errLog."
