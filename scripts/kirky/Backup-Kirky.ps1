#requires -Version 7.4
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Join-Path $root 'source/.venv/Scripts/python.exe'
$db = Join-Path $root 'kirky.sqlite'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$snapshot = Join-Path $root "backups/$stamp.sqlite.pai"
$erasures = Join-Path $root "backups/$stamp.erasures.pai"
$secret = Get-Content -LiteralPath (Join-Path $root 'secrets/backup.dpapi') -Raw | ConvertTo-SecureString
$oldKey = $env:PAI_BACKUP_KEY
try {
    $env:PAI_BACKUP_KEY = [System.Net.NetworkCredential]::new('', $secret).Password
    & $python -m pai.backup backup $db $snapshot
    if ($LASTEXITCODE) { throw 'Kirky backup failed.' }
    & $python -m pai.backup erasures $db $erasures
    if ($LASTEXITCODE) { throw 'Kirky erasure checkpoint failed.' }
    "Kirky encrypted snapshot and erasures created in $root/backups."
} finally { $env:PAI_BACKUP_KEY = $oldKey }
