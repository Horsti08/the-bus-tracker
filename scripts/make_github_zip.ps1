# ZIP nur fuer GitHub/Render (ohne EXE, ohne lokale DB)
$Root = Split-Path $PSScriptRoot -Parent
$Zip = Join-Path $Root "the-bus-tracker-github.zip"
if (Test-Path $Zip) { Remove-Item $Zip -Force }

$temp = Join-Path $env:TEMP "but-github-upload"
if (Test-Path $temp) { Remove-Item $temp -Recurse -Force }
New-Item -ItemType Directory -Path $temp | Out-Null

$exclude = @("dist", "build", "data", "__pycache__", ".git", "agent-tools", "*.zip")
Get-ChildItem $Root -Force | Where-Object {
    $n = $_.Name
    $n -notin @("dist", "build", "data", "__pycache__", ".git", "agent-tools") -and $n -notlike "*.zip"
} | ForEach-Object {
    Copy-Item $_.FullName -Destination (Join-Path $temp $_.Name) -Recurse -Force -ErrorAction SilentlyContinue
}

Compress-Archive -Path "$temp\*" -DestinationPath $Zip -Force
Remove-Item $temp -Recurse -Force
Write-Host "ZIP erstellt: $Zip"
Write-Host "Groesse MB:" ([math]::Round((Get-Item $Zip).Length / 1MB, 2))
