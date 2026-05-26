# Nach GitHub Release: download_url in releases/version.json eintragen
# Beispiel:
#   .\scripts\publish_update.ps1 -DownloadUrl "https://github.com/Horsti08/the-bus-tracker/releases/download/v1.3.1/TheBusTracker.exe"

param(
    [Parameter(Mandatory = $true)]
    [string]$DownloadUrl,
    [string]$Version = "",
    [string]$Changelog = "Bugfixes und Verbesserungen"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent

if (-not $Version) {
    $sharedPath = Join-Path $Root "shared\__init__.py"
    $shared = Get-Content $sharedPath -Raw
    if ($shared -match 'APP_VERSION = "([^"]+)"') {
        $Version = $Matches[1]
    } else {
        $Version = "1.3.1"
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
Write-Host "OK: releases\version.json aktualisiert" -ForegroundColor Green
Write-Host $manifest
Write-Host ""
Write-Host "Jetzt noch ausfuehren:" -ForegroundColor Yellow
Write-Host '  .\scripts\upload_to_github.ps1' -ForegroundColor White
Write-Host ""
