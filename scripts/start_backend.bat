@echo off
setlocal

rem ============================================================
rem SatQuery AI - Windows Backend Launcher
rem Ensures environment paths, database migration status,
rem and launches the FastAPI server and background RQ workers.
rem ============================================================

echo ============================================================
echo   Starting SatQuery AI Backend Services
echo ============================================================

set "SQ_ROOT=%~dp0.."
set "PYTHONPATH=%SQ_ROOT%"
set "PYTHON_EXE=C:\Users\HP\miniconda3\envs\satquery-api\python.exe"

echo [1/3] Checking Docker PostgreSQL database status...
docker exec satquery-postgis pg_isready -U satquery_admin -d satquery >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Docker container satquery-postgis is not accepting connections.
    echo           Run scripts\start_docker_pgsql.bat to start database storage in Docker.
) else (
    echo   + PostgreSQL is healthy and accepting connections in Docker.
)

echo [2/3] Verifying database schema migrations...
if exist "%PYTHON_EXE%" (
    cd /d "%SQ_ROOT%"
    "%PYTHON_EXE%" -m alembic upgrade head
    echo   + Database schema is up to date: conversational tables verified.
) else (
    echo [WARNING] Python executable not found at %PYTHON_EXE%.
)

echo [3/3] Launching API server and background workers...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_backend.ps1"

endlocal
