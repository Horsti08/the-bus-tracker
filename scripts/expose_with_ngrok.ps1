# Schnell öffentliche URL (ohne Render) – ngrok muss installiert sein: https://ngrok.com
# Terminal 1: python run_server.py
# Terminal 2: .\scripts\expose_with_ngrok.ps1
# Die angezeigte https-URL in shared/__init__.py unter COMMUNITY_API_ENDPOINTS eintragen, dann build.ps1

Write-Host "Starte ngrok Tunnel auf Port 5050..."
ngrok http 5050
