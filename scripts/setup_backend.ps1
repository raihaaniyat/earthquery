# SatQuery AI — Backend Setup Script (Windows PowerShell)
# Idempotent setup: directories, environment checks, service bootstrapping, and model audits.

$ErrorActionPreference = "Stop"
$sqRoot = Resolve-Path "$PSScriptRoot\.."
$sqConda = "C:\Users\HP\miniconda3\Scripts\conda.exe"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  SatQuery AI — Antigravity Backend Automated Setup" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Ensure required storage and cache directories exist
Write-Host "[1/5] Initializing local storage and scratch directories..." -ForegroundColor Yellow
$dirs = @("data", "cache", "models", "storage", "storage\satquery-inputs", "storage\satquery-derived", "storage\scratch")
foreach ($d in $dirs) {
    $fullPath = Join-Path $sqRoot $d
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
        Write-Host "  + Created: $d" -ForegroundColor Green
    }
}

# 2. Check Conda Environments
Write-Host "`n[2/5] Verifying required Conda execution environments..." -ForegroundColor Yellow
$requiredEnvs = @("satquery-api", "satquery-core", "satquery-changeformer", "satquery-geoground", "satquery-tools")
$installedEnvs = (& $sqConda env list) -join " "

foreach ($envName in $requiredEnvs) {
    if ($installedEnvs -match $envName) {
        Write-Host "  [OK] $envName found" -ForegroundColor Green
    } else {
        Write-Host "  [MISSING] $envName not found! Please create environment." -ForegroundColor Red
    }
}

# 3. Check Docker / WSL Infrastructure
Write-Host "`n[3/5] Checking container infrastructure (PostGIS, Redis, S3)..." -ForegroundColor Yellow
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if ($null -ne $dockerCmd) {
    Write-Host "  + Docker detected. Starting Compose stack..." -ForegroundColor Green
    docker compose -f (Join-Path $sqRoot "docker\docker-compose.yml") up -d
} else {
    Write-Host "  [BLOCKER] Docker executable is not in PATH." -ForegroundColor DarkYellow
    Write-Host "  -> Action required: Install Docker Desktop with WSL 2 backend." -ForegroundColor DarkYellow
    Write-Host "  -> Note: SatQuery backend will automatically mirror S3 storage locally in 'storage/'." -ForegroundColor DarkGray
}

# 4. Run Model Verification Audit
Write-Host "`n[4/5] Running Model Verification & Provenance Check..." -ForegroundColor Yellow
& $sqConda run -n satquery-tools python (Join-Path $sqRoot "scripts\verify_models.py") --manifest (Join-Path $sqRoot "config\models.yaml")

# 5. Run System Doctor Diagnostics
Write-Host "`n[5/5] Running Infrastructure & Pipeline Diagnostics..." -ForegroundColor Yellow
& $sqConda run -n satquery-api python (Join-Path $sqRoot "scripts\doctor.py") --scope pipeline

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "  Setup complete! Launch the backend with: scripts\start_backend.ps1" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
