#Requires -Version 5.1
<#
.SYNOPSIS
  docker compose with the "tunnel" profile (web + ngrok).

.DESCRIPTION
  Requires `.env` in the repo root with NGROK_AUTHTOKEN (see .env.example).
  Konto ngrok musi być zweryfikowane — inaczej ERR_NGROK_4018.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

if (-not (Test-Path -LiteralPath (Join-Path $Root "docker-compose.yml"))) {
    Write-Error "docker-compose.yml not found in $Root"
}

$envPath = Join-Path $Root ".env"
if (-not (Test-Path -LiteralPath $envPath)) {
    Write-Warning "Brak pliku .env — skopiuj .env.example do .env i ustaw NGROK_AUTHTOKEN."
} else {
    $raw = Get-Content -LiteralPath $envPath -Raw
    if ($raw -notmatch '(?m)^\s*NGROK_AUTHTOKEN=\s*\S+') {
        Write-Warning ".env: ustaw linię NGROK_AUTHTOKEN=... (token z https://dashboard.ngrok.com/get-started/your-authtoken )."
    }
}

docker compose --profile tunnel up -d --build

Write-Host ""
Write-Host "App (local):  http://127.0.0.1:8000"
Write-Host "ngrok inspect: http://127.0.0.1:14040 (albo NGROK_INSPECT_PORT z .env). Public URL: docker compose logs ngrok"
Write-Host "Zatrzymanie:    docker compose down"
