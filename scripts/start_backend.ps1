# SatQuery AI — Backend Startup Script (Windows PowerShell)
# Launches API and background workers, recording owned process IDs in .pids.json.

$ErrorActionPreference = "Stop"
$sqRoot = Resolve-Path "$PSScriptRoot\.."
$sqConda = "C:\Users\HP\miniconda3\Scripts\conda.exe"
$pidFile = Join-Path $sqRoot ".pids.json"
$logDir = Join-Path $sqRoot "artifacts\logs"

if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Starting SatQuery AI Antigravity Backend (RTX 5060 Profile)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Check if already running
if (Test-Path $pidFile) {
    Write-Host "[WARNING] Existing .pids.json found. Stopping previous processes..." -ForegroundColor Yellow
    & (Join-Path $PSScriptRoot "stop_backend.ps1")
}

$pids = @{}

$apiPython = "C:\Users\HP\miniconda3\envs\satquery-api\python.exe"
$apiUvicorn = "C:\Users\HP\miniconda3\envs\satquery-api\Scripts\uvicorn.exe"

# 1. Start FastAPI Application in satquery-api
Write-Host "[1/3] Launching FastAPI REST API on http://127.0.0.1:8000..." -ForegroundColor Yellow
$apiLogOut = Join-Path $logDir "api_stdout.log"
$apiLogErr = Join-Path $logDir "api_stderr.log"

$apiProcess = Start-Process -FilePath $apiUvicorn `
    -ArgumentList "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $sqRoot `
    -RedirectStandardOutput $apiLogOut `
    -RedirectStandardError $apiLogErr `
    -PassThru

$pids["api"] = $apiProcess.Id
Write-Host "  + FastAPI API started with PID: $($apiProcess.Id)" -ForegroundColor Green

# 2. Check Redis and optionally launch RQ Workers
Write-Host "[2/3] Checking Redis connectivity for background workers..." -ForegroundColor Yellow
$redisCheckCode = @"
import sys, os
sys.path.insert(0, r'$sqRoot')
from redis import Redis
from backend.app.config import settings
try:
    r = Redis.from_url(settings.REDIS_URL, socket_timeout=1.5)
    r.ping()
    sys.exit(0)
except Exception as e:
    sys.exit(1)
"@
$tempCheckScript = Join-Path $logDir "check_redis.py"
Set-Content -Path $tempCheckScript -Value $redisCheckCode -Encoding UTF8

$env:PYTHONPATH = $sqRoot
$redisStatus = & $apiPython $tempCheckScript
$redisAvailable = ($LASTEXITCODE -eq 0)
Remove-Item -Path $tempCheckScript -Force -ErrorAction SilentlyContinue


if ($redisAvailable) {
    Write-Host "  + Redis is online. Launching background Workers..." -ForegroundColor Green
    
    $ingestLogOut = Join-Path $logDir "worker_ingest_stdout.log"
    $ingestLogErr = Join-Path $logDir "worker_ingest_stderr.log"
    $ingestWorker = Start-Process -FilePath $apiPython `
        -ArgumentList "-m", "backend.app.workers.runner", "--queues", "satquery-ingest", "--name", "ingest-worker-1" `
        -WorkingDirectory $sqRoot `
        -RedirectStandardOutput $ingestLogOut `
        -RedirectStandardError $ingestLogErr `
        -PassThru
    $pids["ingest_worker"] = $ingestWorker.Id
    Write-Host "  + Ingest Worker started with PID: $($ingestWorker.Id)" -ForegroundColor Green

    $analysisLogOut = Join-Path $logDir "worker_analysis_stdout.log"
    $analysisLogErr = Join-Path $logDir "worker_analysis_stderr.log"
    $analysisWorker = Start-Process -FilePath $apiPython `
        -ArgumentList "-m", "backend.app.workers.runner", "--queues", "satquery-analysis", "--name", "analysis-worker-1" `
        -WorkingDirectory $sqRoot `
        -RedirectStandardOutput $analysisLogOut `
        -RedirectStandardError $analysisLogErr `
        -PassThru
    $pids["analysis_worker"] = $analysisWorker.Id
    Write-Host "  + Analysis Worker started with PID: $($analysisWorker.Id)" -ForegroundColor Green
} else {
    Write-Host "  - Redis is unreachable (Docker/Redis container not started). Background workers deferred." -ForegroundColor DarkYellow
    Write-Host "    (API will handle synchronous operations and catalog inspection independently)" -ForegroundColor DarkYellow
}

# Save PIDs
$pids | ConvertTo-Json | Set-Content -Path $pidFile -Encoding UTF8

# 3. Liveness check
Write-Host "[3/3] Probing API liveness..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

try {
    $response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/live" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "  + Liveness probe succeeded: status=$($response.status)" -ForegroundColor Green
} catch {
    Write-Host "  [WARNING] API did not respond immediately. Check logs at: $apiLogErr" -ForegroundColor Yellow
}

Write-Host "`nBackend successfully initialized!" -ForegroundColor Green
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  API Liveness Probe:   http://127.0.0.1:8000/health/live" -ForegroundColor White
Write-Host "  API Readiness Probe:  http://127.0.0.1:8000/health/ready" -ForegroundColor White
Write-Host "  Interactive OpenAPI:  http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "  Capability Matrix:    http://127.0.0.1:8000/api/v1/capabilities" -ForegroundColor White
Write-Host "  Legacy Health Status: http://127.0.0.1:8000/api/health" -ForegroundColor White
Write-Host "  Logs Directory:       $logDir" -ForegroundColor White
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "To stop all backend processes gracefully, run: scripts\stop_backend.ps1`n" -ForegroundColor Cyan
