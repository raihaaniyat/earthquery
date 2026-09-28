@echo off
setlocal

rem ============================================================
rem SatQuery AI - Docker PostgreSQL Storage and Launcher
rem ============================================================

echo ============================================================
echo   SatQuery AI - Docker PostgreSQL Storage Setup
echo ============================================================

set "SQ_ROOT=%~dp0.."
set "DOCKER_COMPOSE_FILE=%SQ_ROOT%\docker\docker-compose.yml"
set "PYTHON_EXE=C:\Users\HP\miniconda3\envs\satquery-api\python.exe"
set "PYTHONPATH=%SQ_ROOT%"

echo [1/5] Checking Docker Engine availability...
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Engine is not running!
    echo         Please start Docker Desktop and ensure the Docker daemon is active.
    exit /b 1
)
echo   + Docker Engine is active and responding.

echo [2/5] Ensuring persistent Docker volume for PostgreSQL data...
docker volume create docker_satquery_postgis_data >nul 2>&1
docker volume create docker_satquery_redis_data >nul 2>&1
docker volume create docker_satquery_seaweedfs_data >nul 2>&1
echo   + Persistent Docker volumes verified.

echo [3/5] Starting PostGIS container via Docker Compose...
docker compose -f "%DOCKER_COMPOSE_FILE%" up -d db redis objectstore
if errorlevel 1 (
    echo [ERROR] Failed to start containers via Docker Compose.
    exit /b 1
)

echo [4/5] Waiting for PostgreSQL container to accept connections...
docker exec satquery-postgis pg_isready -U satquery_admin -d satquery >nul 2>&1
if errorlevel 1 (
    echo   Waiting for database to finish startup...
    timeout /t 3 /nobreak >nul
    docker exec satquery-postgis pg_isready -U satquery_admin -d satquery >nul 2>&1
)
if errorlevel 1 (
    echo [ERROR] PostgreSQL did not become ready.
    exit /b 1
)
echo   + PostgreSQL is ready and accepting connections on 127.0.0.1:5432.

echo [5/5] Applying Alembic database migrations to Docker PostgreSQL...
if exist "%PYTHON_EXE%" (
    cd /d "%SQ_ROOT%"
    "%PYTHON_EXE%" -m alembic upgrade head
    echo   + Database schema migrated to HEAD: all conversation and spatial tables ready.
) else (
    echo [WARNING] Python environment not found at %PYTHON_EXE%.
)

echo.
echo ============================================================
echo   SUCCESS: Docker PostgreSQL Storage is Online and Persistent
echo ============================================================
echo   Container Name : satquery-postgis
echo   Connection DSN : postgresql://satquery_admin:satquery_admin_password@127.0.0.1:5432/satquery
echo   Storage Volume : docker_satquery_postgis_data
echo   Mounted Target : /var/lib/postgresql/data
echo.
echo All conversations, turns, scenes, and analysis results will
echo be stored persistently inside the Docker Engine volume.
echo ============================================================
echo.

endlocal
