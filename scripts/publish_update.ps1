# Nach .\build.ps1: EXE veröffentlichen + Auto-Update aktivieren
#
# 1) Lade dist\TheBusTracker.exe hoch (GitHub Release, Google Drive, eigener Server)
# 2) Trage die oeffentliche URL unten ein
# 3) Dieses Skript aktualisiert releases\version.json (dann GitHub pushen)

param(
    [Parameter(Mandatory = $true)]
    [string]$DownloadUrl,
    [string]$Version = "",
    [string]$Changelog = "Bugfixes und Verbesserungen"
)

$Root = Split-Path $PSScriptRoot -Parent
if (-not $Version) {
    $shared = Get-Content (Join-Path $Root "shared\__init__.py") -Raw
    if ($shared -match 'APP_VERSION = "([^"]+)"') {
        $Version = $Matches[1]
    } else {
        $Version = "1.0.0"
    }
}

$manifest = @{
    version            = $Version
    mandatory          = $false
    changelog          = $Changelog
    download_url       = $DownloadUrl
    community_api_url  = "https://the-bus-tracker-api.onrender.com"
    community_api_urls = @("https://the-bus-tracker-api.onrender.com")
} | ConvertTo-Json -Depth 3

$path = Join-Path $Root "releases\version.json"
$manifest | Set-Content -Path $path -Encoding UTF8

Write-Host ""
Write-Host "releases\version.json aktualisiert:" -ForegroundColor Green
Write-Host $manifest
Write-Host ""
Write-Host "Naechster Schritt – auf GitHub pushen:" -ForegroundColor Yellow
Write-Host '  $env:GITHUB_TOKEN = "DEIN_TOKEN"'
Write-Host '  cd "G:\The Bus Tracker"'
Write-Host '  .\scripts\upload_to_github.ps1'
Write-Host ""
Write-Host "Alle EXEs pruefen dann beim Start / alle 30 Min auf Updates." -ForegroundColor Cyan
