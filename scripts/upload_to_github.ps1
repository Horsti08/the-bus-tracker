# The Bus Tracker -> GitHub hochladen (Horsti08/the-bus-tracker)
# Einmal GitHub Token erstellen: https://github.com/settings/tokens -> Generate new token (classic)
# Haken: repo (voller Zugriff auf Repositories)
#
# Dann in PowerShell:
#   $env:GITHUB_TOKEN = "ghp_DEIN_TOKEN_HIER"
#   cd "G:\The Bus Tracker"
#   .\scripts\upload_to_github.ps1

param(
    [string]$Token = $env:GITHUB_TOKEN,
    [string]$Repo = "https://github.com/Horsti08/the-bus-tracker.git",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

if (-not $Token) {
    Write-Host ""
    Write-Host "FEHLER: Kein GitHub-Token." -ForegroundColor Red
    Write-Host ""
    Write-Host "1) Oeffne: https://github.com/settings/tokens" -ForegroundColor Yellow
    Write-Host "2) Generate new token (classic) -> Haken bei 'repo'" -ForegroundColor Yellow
    Write-Host "3) Token kopieren, dann:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host '   $env:GITHUB_TOKEN = "ghp_xxxxxxxx"' -ForegroundColor Cyan
    Write-Host '   cd "G:\The Bus Tracker"' -ForegroundColor Cyan
    Write-Host '   .\scripts\upload_to_github.ps1' -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

# --- Portable Git (MinGit) falls kein Git installiert ---
$MinGitDir = Join-Path $env:LOCALAPPDATA "MinGit"
$GitExe = Join-Path $MinGitDir "cmd\git.exe"

if (-not (Test-Path $GitExe)) {
    Write-Host "Lade Portable Git..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $MinGitDir -Force | Out-Null
    $zipUrl = "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/MinGit-2.47.1-64-bit.zip"
    $zipPath = Join-Path $env:TEMP "MinGit.zip"
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
    Expand-Archive -Path $zipPath -DestinationPath $MinGitDir -Force
    Remove-Item $zipPath -Force
    Write-Host "Git bereit: $GitExe" -ForegroundColor Green
}

$env:PATH = "$(Split-Path $GitExe -Parent);$env:PATH"
$git = $GitExe

function Run-Git {
    param(
        [Parameter(Mandatory, ValueFromRemainingArguments = $true)]
        [string[]]$GitCommand,
        [switch]$Optional
    )
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $git @GitCommand 2>&1 | Out-Null
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    if (-not $Optional -and $code -ne 0) {
        throw "Git fehlgeschlagen (Exit $code): git $($GitCommand -join ' ')"
    }
    return $code
}

# Repo-URL mit Token (nicht in Logs speichern)
$repoWithAuth = "https://${Token}@github.com/Horsti08/the-bus-tracker.git"

Write-Host "Bereite Dateien vor..." -ForegroundColor Cyan

# .gitignore falls nicht vorhanden
if (-not (Test-Path ".gitignore")) {
    @"
dist/
build/
data/
__pycache__/
*.pyc
.env
*.db
agent-tools/
the-bus-tracker-github.zip
"@ | Set-Content -Path ".gitignore" -Encoding UTF8
}

Run-Git init
Run-Git config user.email "horsti08@users.noreply.github.com"
Run-Git config user.name "Horsti08"

Run-Git add -A
& $git status --short | Select-Object -First 25

$ErrorActionPreference = "Continue"
$status = & $git status --porcelain 2>&1
$ErrorActionPreference = "Stop"

if (-not $status) {
    Write-Host "Nichts Neues zu committen." -ForegroundColor Yellow
} else {
    Run-Git commit -m "The Bus Tracker v1.2.0 - Community API, Telemetry, EXE"
}

Run-Git branch -M $Branch -Optional

# Remote setzen (remove ist OK wenn origin noch nicht existiert)
Run-Git remote remove origin -Optional
if ((Run-Git remote add origin $repoWithAuth -Optional) -ne 0) {
    Run-Git remote set-url origin $repoWithAuth
}

Write-Host "Push nach GitHub..." -ForegroundColor Cyan
Run-Git push -u origin $Branch --force

# Token aus Remote entfernen (Sicherheit)
Run-Git remote set-url origin $Repo

Write-Host ""
Write-Host "FERTIG! Code ist auf GitHub:" -ForegroundColor Green
Write-Host "https://github.com/Horsti08/the-bus-tracker" -ForegroundColor Cyan
Write-Host ""
Write-Host "Naechster Schritt: Render Dashboard -> New -> Blueprint -> Repo waehlen -> Apply" -ForegroundColor Yellow
