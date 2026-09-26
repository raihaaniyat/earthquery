@echo off
cd /d "%~dp0..\frontend"
echo Starting SatQuery Frontend Dev Server on http://localhost:3000 ...
call npm.cmd run dev
