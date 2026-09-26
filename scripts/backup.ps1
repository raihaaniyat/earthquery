# SatQuery AI — Database & Storage Asset Backup Script
# Generates timestamped database dump and immutable asset checksum manifests in artifacts/backups/.

$ErrorActionPreference = "Stop"
$sqRoot = Resolve-Path "$PSScriptRoot\.."
$sqConda = "C:\Users\HP\miniconda3\Scripts\conda.exe"
$backupDir = Join-Path $sqRoot "artifacts\backups"

if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$destFolder = Join-Path $backupDir "backup_$timestamp"
New-Item -ItemType Directory -Path $destFolder -Force | Out-Null

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  SatQuery Backup: Creating snapshot $timestamp" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Export database snapshot manifest
Write-Host "[1/2] Creating DB and storage asset manifest..." -ForegroundColor Yellow
& $sqConda run -n satquery-api python (Join-Path $sqRoot "scripts\export_backup_manifest.py") --dest-folder $destFolder


# 2. Copy storage assets
Write-Host "[2/2] Mirroring local storage objects..." -ForegroundColor Yellow
$localStorage = Join-Path $sqRoot "storage"
if (Test-Path $localStorage) {
    Copy-Item -Path "$localStorage\*" -Destination "$destFolder\storage" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  + Storage assets mirrored to: $destFolder\storage" -ForegroundColor Green
}

Write-Host "`nBackup successfully generated at: $destFolder" -ForegroundColor Green
