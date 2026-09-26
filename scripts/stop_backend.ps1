# SatQuery AI — Backend Shutdown Script (Windows PowerShell)
# Gracefully terminates owned backend process trees recorded in .pids.json.

$ErrorActionPreference = "SilentlyContinue"
$sqRoot = Resolve-Path "$PSScriptRoot\.."
$pidFile = Join-Path $sqRoot ".pids.json"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Stopping SatQuery AI Backend Processes" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (-not (Test-Path $pidFile)) {
    Write-Host "No active .pids.json found. No owned processes to terminate." -ForegroundColor Yellow
    exit 0
}

$rawJson = Get-Content -Path $pidFile -Raw
$pids = ConvertFrom-Json $rawJson

if ($null -ne $pids) {
    $props = $pids.PSObject.Properties
    foreach ($prop in $props) {
        $pName = $prop.Name
        $pId = $prop.Value
        if ($null -ne $pId -and $pId -gt 0 -and $pId -ne $PID) {
            Write-Host "Stopping $pName process (PID $pId)..." -ForegroundColor Yellow
            cmd.exe /c "taskkill /F /T /PID $pId >nul 2>&1"
            Write-Host "  + $pName process stopped." -ForegroundColor Green
        }
    }
}

# Also ensure port 8000 is freed if a dangling process remains
try {
    $portConn = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -gt 0 -and $_.OwningProcess -ne $PID }
    foreach ($c in $portConn) {
        Write-Host "Killing dangling process on port 8000 (PID $($c.OwningProcess))..." -ForegroundColor Yellow
        cmd.exe /c "taskkill /F /T /PID $($c.OwningProcess) >nul 2>&1"
    }
} catch {}

Remove-Item -Path $pidFile -Force -ErrorAction SilentlyContinue
Write-Host "`nAll owned backend processes terminated successfully.`n" -ForegroundColor Green
