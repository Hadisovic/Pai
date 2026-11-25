#requires -Version 7.4
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$lock = Join-Path $root 'run.lock'
function Test-Running {
    if (-not (Test-Path -LiteralPath $lock)) { return $false }
    $file = [System.IO.File]::Open($lock, 'Open', 'ReadWrite', 'ReadWrite')
    try {
        try { $file.Lock(0, 1) } catch [System.IO.IOException] { return $true }
        $file.Unlock(0, 1)
        return $false
    } finally { $file.Dispose() }
}
if (-not (Test-Running)) {
    'Kirky is stopped.'
    return
}
Set-Content -LiteralPath (Join-Path $root 'stop.request') -Value 'stop'
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    if (-not (Test-Running)) {
        'Kirky stopped.'
        return
    }
}
throw 'Kirky has not exited yet. Check its logs.'
