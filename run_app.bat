@echo off
setlocal enabledelayedexpansion
title NRA-Metadata Launcher
cd /d "%~dp0"
set "PYTHONPATH=%CD%"

echo =======================================================
echo         NRA-Metadata - Auto Launcher
echo =======================================================
echo.

if not exist "cache" mkdir cache
if not exist "logs" mkdir logs
if not exist "output" mkdir output

:: 1. Deteksi Python Sistem & Cek Tkinter
where python >nul 2>&1
if %ERRORLEVEL% neq 0 goto :CHECK_WINGET

python -c "import tkinter" >nul 2>&1
if %ERRORLEVEL% neq 0 goto :CHECK_WINGET

echo [*] Python sistem terdeteksi.
if exist "cache\.deps_installed" goto :LAUNCH_APP

echo [*] Mengunduh dan memasang dependensi dari requirements.txt...
echo -------------------------------------------------------
python -m pip install --upgrade pip
python -m pip install -r requirements.txt --no-warn-script-location
if %ERRORLEVEL% equ 0 (
    echo. > "cache\.deps_installed"
    echo [SUCCESS] Dependensi berhasil dipasang.
) else (
    echo [WARN] Instalasi dependensi mengalami kendala. Mencoba melanjutkan...
)
echo -------------------------------------------------------
goto :LAUNCH_APP

:CHECK_WINGET
where winget >nul 2>&1
if %ERRORLEVEL% neq 0 goto :FALLBACK_INSTALLER

echo [*] Python belum terpasang. Memasang Python 3.11 via Winget...
winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
if %ERRORLEVEL% neq 0 goto :FALLBACK_INSTALLER

set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
echo [*] Memasang dependensi...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt --no-warn-script-location
echo. > "cache\.deps_installed"
goto :LAUNCH_APP

:FALLBACK_INSTALLER
echo [*] Mengunduh runtime Python resmi...
if not exist "tools" mkdir tools
set "INSTALLER_PATH=tools\python_installer.exe"
if not exist "%INSTALLER_PATH%" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%INSTALLER_PATH%'"
)
if exist "%INSTALLER_PATH%" (
    echo [*] Memasang Python lokal...
    start /wait "" "%INSTALLER_PATH%" /quiet InstallAllUsers=0 PrependPath=1 Include_tcltk=1 Include_pip=1
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
    echo [*] Memasang dependensi...
    python -m pip install -r requirements.txt --no-warn-script-location
    echo. > "cache\.deps_installed"
    goto :LAUNCH_APP
)

:ERROR
echo.
echo [ERROR] Gagal menyiapkan environment Python.
pause
exit /b 1

:LAUNCH_APP
echo [*] Memeriksa konfigurasi awal...
python scripts\init_config.py
echo [*] Menjalankan NRA-Metadata...
echo.
python apps\desktop\src\main.py

:END
echo.
echo =======================================================
echo Launcher selesai.
pause