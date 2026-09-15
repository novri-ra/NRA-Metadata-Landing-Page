@echo off
rem Launcher: bypasses the ExecutionPolicy and runs setup_tools.ps1 in place.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_tools.ps1"
pause