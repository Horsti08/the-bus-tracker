# Deploy fuer alle Spieler - EXE bauen + GitHub + optional Auto-Update
# Nutzung:
#   $env:GITHUB_TOKEN = "ghp_xxxx"
#   cd "G:\The Bus Tracker"
#   .\scripts\DEPLOY_FUER_ALLE.ps1

param(
    [string]$ReleaseDownloadUrl = "",
    [string]$Token = $env:GITHUB_TOKEN
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

$Version = "1.3.1"
$sharedPath = Join-Path $Root "shared\__init__.py"
if (Test-Path $sharedPath) {
    $shared = Get-Content $sharedPath -Raw
    if ($shared -match 'APP_VERSION = "([^"]+)"') {
        $Version = $Matches[1]
    }
}

Write-Host ""
Write-Host "========================================"
Write-Host " THE BUS TRACKER - Deploy fuer ALLE"
Write-Host " Version: $Version"
Write-Host "========================================"
Write-Host ""

Write-Host "[1/4] Baue EXE ..." -ForegroundColor Yellow
& (Join-Path $Root "build.ps1")
$exe = Join-Path $Root "dist\TheBusTracker.exe"
if (-not (Test-Path $exe)) {
    Write-Host "FEHLER: dist\TheBusTracker.exe fehlt" -ForegroundColor Red
    exit 1
}
Write-Host "OK: $exe" -ForegroundColor Green
Write-Host ""

Write-Host "[2/4] GitHub Upload (wie frueher upload_to_github.ps1) ..." -ForegroundColor Yellow
if (-not $Token) {
    Write-Host "FEHLER: Kein GITHUB_TOKEN gesetzt." -ForegroundColor Red
    Write-Host 'Setze: $env:GITHUB_TOKEN = "ghp_DEIN_TOKEN"' -ForegroundColor Yellow
    Write-Host "Oder nur GitHub: .\scripts\upload_to_github.ps1" -ForegroundColor Yellow
    exit 1
}

& (Join-Path $Root "scripts\upload_to_github.ps1") -Token $Token
Write-Host "OK: Code auf GitHub" -ForegroundColor Green
Write-Host "Render: dashboard.render.com - Service the-bus-tracker-api auf LIVE warten" -ForegroundColor Cyan
Write-Host ""

Write-Host "[3/4] Auto-Update ..." -ForegroundColor Yellow
if ($ReleaseDownloadUrl) {
    & (Join-Path $Root "scripts\publish_update.ps1") -DownloadUrl $ReleaseDownloadUrl -Version $Version -Changelog "Update $Version"
    & (Join-Path $Root "scripts\upload_to_github.ps1") -Token $Token
    Write-Host "OK: Auto-Update aktiv" -ForegroundColor Green
}
else {
    Write-Host "Auto-Update: erst GitHub Release mit EXE, dann:" -ForegroundColor Yellow
    Write-Host '.\scripts\DEPLOY_FUER_ALLE.ps1 -ReleaseDownloadUrl "DEIN_DOWNLOAD_LINK"' -ForegroundColor Yellow
    Write-Host "Oder: .\scripts\publish_update.ps1 -DownloadUrl `"LINK`"" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "[4/4] Server-Test ..." -ForegroundColor Yellow
$healthOk = $false
try {
    $h = Invoke-RestMethod -Uri "https://the-bus-tracker-api.onrender.com/health" -TimeoutSec 25
    Write-Host "OK: Render online, Server-Version $($h.version)" -ForegroundColor Green
    $healthOk = $true
}
catch {
    Write-Host "Hinweis: Render noch nicht erreichbar - 2-5 Min warten nach Deploy" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Fertig: dist\TheBusTracker.exe starten"
Write-Host " Fuer alle: EXE schicken oder Auto-Update mit Release-Link"
Write-Host "========================================"
Write-Host ""
