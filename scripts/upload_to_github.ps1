# The Bus Tracker -> GitHub hochladen (Horsti08/the-bus-tracker)
#
# TOKEN (eine Variante waehlen):
#   A) Classic: https://github.com/settings/tokens -> "Generate new token (classic)" -> Haken "repo"
#   B) Fine-grained: https://github.com/settings/tokens?type=beta -> Repository "the-bus-tracker" -> Contents: Read and write
#
#   $env:GITHUB_TOKEN = "ghp_xxxx"   oder   "github_pat_xxxx"
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
    Write-Host "FEHLER: Kein Token. Setze `$env:GITHUB_TOKEN" -ForegroundColor Red
    exit 1
}

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
}

$env:PATH = "$(Split-Path $GitExe -Parent);$env:PATH"
$env:GIT_TERMINAL_PROMPT = "0"
$git = $GitExe

function Run-Git {
    param(
        [Parameter(Mandatory, ValueFromRemainingArguments = $true)]
        [string[]]$GitCommand,
        [switch]$Optional,
        [switch]$ShowOutput
    )
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $out = & $git @GitCommand 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    if ($ShowOutput -or ($code -ne 0 -and -not $Optional)) {
        $out | ForEach-Object { Write-Host $_ }
    }
    if (-not $Optional -and $code -ne 0) {
        throw "Git Exit $code : git $($GitCommand -join ' ')"
    }
    return $code
}

# Token testen (GitHub API)
Write-Host "Pruefe GitHub-Token..." -ForegroundColor Cyan
try {
    $headers = @{
        Authorization = "Bearer $Token"
        Accept        = "application/vnd.github+json"
        "User-Agent"  = "TheBusTracker"
    }
    $user = Invoke-RestMethod -Uri "https://api.github.com/user" -Headers $headers -TimeoutSec 15
    Write-Host "Angemeldet als: $($user.login)" -ForegroundColor Green
} catch {
    Write-Host "TOKEN UNGUELTIG oder abgelaufen!" -ForegroundColor Red
    Write-Host "Neuen Token erstellen (classic mit 'repo' ODER fine-grained mit Contents Read+Write auf the-bus-tracker)" -ForegroundColor Yellow
    exit 1
}

# Auth-URL (funktioniert mit classic + fine-grained)
$repoWithAuth = "https://x-access-token:$Token@github.com/Horsti08/the-bus-tracker.git"

Write-Host "Bereite Dateien vor..." -ForegroundColor Cyan

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

if ($status) {
    Run-Git commit -m "The Bus Tracker v1.2.0 - Community API, Telemetry, EXE"
} else {
    Write-Host "Commit bereits vorhanden." -ForegroundColor Yellow
}

Run-Git branch -M $Branch -Optional
Run-Git remote remove origin -Optional
if ((Run-Git remote add origin $repoWithAuth -Optional) -ne 0) {
    Run-Git remote set-url origin $repoWithAuth
}

Write-Host "Push nach GitHub..." -ForegroundColor Cyan
$prev = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pushOut = & $git push -u origin $Branch --force 2>&1
$pushCode = $LASTEXITCODE
$ErrorActionPreference = $prev

$pushOut | ForEach-Object { Write-Host $_ }

if ($pushCode -ne 0) {
    Write-Host ""
    Write-Host "PUSH FEHLGESCHLAGEN (Exit $pushCode)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Haeufige Ursachen:" -ForegroundColor Yellow
    Write-Host "  1) Fine-grained Token: Repository 'the-bus-tracker' auswaehlen + Contents: Read AND write"
    Write-Host "  2) Classic Token: Haken bei 'repo' (full control)"
    Write-Host "  3) Token widerrufen -> neuen erstellen"
    Write-Host "  4) Repo-Name pruefen: Horsti08/the-bus-tracker"
    exit 1
}

Run-Git remote set-url origin $Repo

Write-Host ""
Write-Host "FERTIG! https://github.com/Horsti08/the-bus-tracker" -ForegroundColor Green
Write-Host "Naechster Schritt: Render -> New -> Blueprint -> Apply" -ForegroundColor Yellow
