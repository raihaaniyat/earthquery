@echo off
rem SatQuery AI — Windows Backend Launcher Helper
rem Bypasses PowerShell script execution policy restrictions safely.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_backend.ps1"
