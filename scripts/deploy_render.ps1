# The Bus Tracker – Render Deploy (automatisch oder Schritt-für-Schritt)
param(
    [string]$RenderApiKey = $env:RENDER_API_KEY,
    [string]$GitHubRepoUrl = "",
    [switch]$OpenDashboard
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

Write-Host "=== The Bus Tracker – Render Deploy ===" -ForegroundColor Cyan
Write-Host ""

# --- Option 1: Render API (wenn API-Key gesetzt) ---
if ($RenderApiKey) {
    Write-Host "API-Key gefunden. Erstelle Service per Render API..." -ForegroundColor Yellow

    if (-not $GitHubRepoUrl) {
        Write-Host "FEHLER: GitHubRepoUrl noetig fuer API-Deploy."
        Write-Host "Beispiel: https://github.com/DEINUSER/the-bus-tracker"
        exit 1
    }

    $headers = @{
        Authorization = "Bearer $RenderApiKey"
        "Content-Type" = "application/json"
    }

    # Workspace-ID holen
    $owners = Invoke-RestMethod -Uri "https://api.render.com/v1/owners" -Headers $headers
    $ownerId = $owners[0].owner.id
    Write-Host "Workspace: $($owners[0].owner.name)"

    $body = @{
        type = "web_service"
        name = "the-bus-tracker-api"
        ownerId = $ownerId
        repo = $GitHubRepoUrl
        branch = "main"
        autoDeploy = "yes"
        serviceDetails = @{
            runtime = "python"
            plan = "free"
            region = "frankfurt"
            buildCommand = "pip install -r requirements.txt"
            startCommand = "uvicorn server.main:app --host 0.0.0.0 --port `$PORT"
            healthCheckPath = "/health"
            envVars = @(
                @{ key = "PYTHON_VERSION"; value = "3.12.0" }
                @{ key = "DATABASE_DIR"; value = "/opt/render/project/src/data" }
            )
        }
    } | ConvertTo-Json -Depth 6

    try {
        $svc = Invoke-RestMethod -Method Post -Uri "https://api.render.com/v1/services" -Headers $headers -Body $body
        $serviceId = $svc.service.id
        Write-Host "Service erstellt: $serviceId" -ForegroundColor Green

        # Deploy ausloesen
        Invoke-RestMethod -Method Post -Uri "https://api.render.com/v1/services/$serviceId/deploys" -Headers $headers | Out-Null
        Write-Host "Deploy gestartet. Warte auf URL im Dashboard..." -ForegroundColor Green
        Write-Host "https://dashboard.render.com/web/$serviceId"
    } catch {
        Write-Host "API-Fehler: $_" -ForegroundColor Red
        Write-Host $_.Exception.Response
    }
    exit 0
}

# --- Option 2: Dashboard (Standard ohne API-Key) ---
Write-Host "Kein RENDER_API_KEY – oeffne Anleitung + Dashboard." -ForegroundColor Yellow
Write-Host ""
Write-Host @"
SCHRITT 1 – GitHub (einmalig)
  1. Neues Repo auf github.com: the-bus-tracker
  2. Ordner 'g:\The Bus Tracker' hochladen (ZIP oder GitHub Desktop)

SCHRITT 2 – Render
  1. https://dashboard.render.com/register
  2. New + → Blueprint
  3. GitHub verbinden → Repo 'the-bus-tracker' waehlen
  4. Render erkennt render.yaml automatisch
  5. Apply → Deploy (ca. 3–5 Min.)

SCHRITT 3 – URL in die EXE
  Nach Deploy: URL kopieren, z.B.
  https://the-bus-tracker-api.onrender.com

  In shared\__init__.py eintragen:
  COMMUNITY_API_ENDPOINTS = ["https://the-bus-tracker-api.onrender.com"]

  Dann: .\build.ps1

SCHRITT 4 – Test
  curl https://the-bus-tracker-api.onrender.com/health
"@ -ForegroundColor White

if ($OpenDashboard) {
    Start-Process "https://dashboard.render.com/select-repo?type=blueprint"
}

Write-Host ""
Write-Host "API-Deploy automatisch:" -ForegroundColor Cyan
Write-Host '  $env:RENDER_API_KEY = "rnd_..."'
Write-Host '  .\scripts\deploy_render.ps1 -GitHubRepoUrl "https://github.com/USER/the-bus-tracker"'
