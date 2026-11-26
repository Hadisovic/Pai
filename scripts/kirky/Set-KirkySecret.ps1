#requires -Version 7.4
param(
    [Parameter(Mandatory)]
    [ValidateSet('discord', 'groq')]
    [string]$Kind
)
$ErrorActionPreference = 'Stop'
$secret = Read-Host "Enter the separate Kirky $Kind secret locally" -AsSecureString
if ($secret.Length -eq 0) { throw 'No secret was supplied.' }
$path = Join-Path $PSScriptRoot "secrets/$Kind.dpapi"
$secret | ConvertFrom-SecureString | Set-Content -LiteralPath $path -Encoding ascii -NoNewline
'Saved for the current Windows user.'
