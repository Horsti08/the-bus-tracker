# The Bus Tracker – Build mit Auto-Updater & eingebettetem Server
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

python -m pip install -r requirements.txt -q

Write-Host "Baue TheBusTracker.exe v1.1.0 ..."
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
