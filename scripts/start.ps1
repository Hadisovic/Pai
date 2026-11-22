# Launcher for Pai with local .env and .pai-policy.json
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Test-Path ".env")) {
    Write-Error "Missing .env file. Please create .env with DISCORD_TOKEN and PAI_GROQ_KEY."
    exit 1
}

if (-not (Test-Path ".pai-policy.json")) {
    Write-Error "Missing .pai-policy.json file. Please configure the approved guild and channel IDs."
    exit 1
}

# Load .env into process environment
Get-Content ".env" | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $idx = $line.IndexOf("=")
        $key = $line.Substring(0, $idx).Trim()
        $val = $line.Substring($idx + 1).Trim()
        [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
    }
}

if (-not $env:DISCORD_TOKEN) {
    Write-Error "DISCORD_TOKEN is not set in .env."
    exit 1
}

if (-not $env:PAI_GROQ_KEY) {
    Write-Error "PAI_GROQ_KEY is not set in .env."
    exit 1
}

Write-Host "Running runtime doctor..." -ForegroundColor Cyan
uv run python -m pai --doctor

Write-Host "Checking policy..." -ForegroundColor Cyan
uv run python -m pai --policy .pai-policy.json

Write-Host "Connecting Pai to Discord..." -ForegroundColor Green
uv run python -m pai --connect --database pai.sqlite --groq-free --policy .pai-policy.json
