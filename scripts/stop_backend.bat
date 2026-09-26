@echo off
rem SatQuery AI — Windows Backend Shutdown Helper
rem Bypasses PowerShell script execution policy restrictions safely.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_backend.ps1"
