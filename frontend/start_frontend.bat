@echo off
setlocal

cd /d "%~dp0"
echo ============================================================
echo   Starting SatQuery AI Frontend Dev Server
echo ============================================================

echo [1/3] Checking dependencies...
if not exist "node_modules\" (
    echo   Installing dependencies...
    call npm.cmd install
) else (
    echo   + Dependencies found in node_modules.
)

echo [2/3] Verifying TypeScript contracts...
call npx.cmd tsc --noEmit

echo [3/3] Starting Vite dev server on http://localhost:3000 ...
call npm.cmd run dev

endlocal
