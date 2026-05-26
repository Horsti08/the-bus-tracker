# The Bus Tracker – Build mit Auto-Updater & eingebettetem Server
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

python -m pip install -r requirements.txt -q

$ver = "?"
if (Test-Path "$Root\shared\__init__.py") {
    if ((Get-Content "$Root\shared\__init__.py" -Raw) -match 'APP_VERSION = "([^"]+)"') { $ver = $Matches[1] }
}
Write-Host "Baue TheBusTracker.exe v$ver ..."
python -m PyInstaller `
    --noconfirm `
    --onefile `
    --windowed `
    --name "TheBusTracker" `
    --paths "$Root" `
    --hidden-import "uvicorn.logging" `
    --hidden-import "uvicorn.loops" `
    --hidden-import "uvicorn.loops.auto" `
    --hidden-import "uvicorn.protocols" `
    --hidden-import "uvicorn.protocols.http" `
    --hidden-import "uvicorn.protocols.http.auto" `
    --hidden-import "uvicorn.lifespan" `
    --hidden-import "uvicorn.lifespan.on" `
    --collect-all customtkinter `
    --collect-submodules server `
    "$Root\client\main.py"

Write-Host ""
Write-Host "Fertig: dist\TheBusTracker.exe"
Write-Host "Update-Manifest: releases\version.json (download_url eintragen fuer Auto-Update)"
