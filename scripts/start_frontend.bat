@echo off
setlocal

rem ============================================================
rem SatQuery AI - Frontend Dev Server Launcher
rem Verifies dependencies, runs TypeScript checks, and starts Vite.
rem ============================================================

echo ============================================================
echo   Starting SatQuery AI Frontend Dev Server
echo ============================================================

cd /d "%~dp0..\frontend"

echo [1/3] Checking frontend dependencies...
if not exist "node_modules\" (
    echo   Installing dependencies via npm...
    call npm.cmd install
) else (
    echo   + Dependencies verified in node_modules.
)

echo [2/3] Verifying TypeScript contracts...
call npx.cmd tsc --noEmit
if errorlevel 1 (
    echo [WARNING] TypeScript check flagged warnings. Proceeding with Vite server...
) else (
    echo   + TypeScript contracts validated with 0 errors.
)

echo [3/3] Starting SatQuery Frontend on http://localhost:3000 ...
call npm.cmd run dev

endlocal
