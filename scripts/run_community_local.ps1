# Community-Server lokal starten (zum Testen vor Render-Deploy)
$env:DATABASE_DIR = "$PSScriptRoot\..\data"
Set-Location "$PSScriptRoot\.."
Write-Host "Community-API: http://127.0.0.1:5050"
Write-Host "Trage in shared/__init__.py ein: COMMUNITY_API_ENDPOINTS = ['http://127.0.0.1:5050']"
python run_server.py
