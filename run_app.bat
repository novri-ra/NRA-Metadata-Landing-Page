@echo off
setlocal enabledelayedexpansion
title NRA-Metadata Launcher
cd /d "%~dp0"
set "PYTHONPATH=%CD%"

echo =======================================================
echo         NRA-Metadata - Auto Launcher
echo =======================================================
echo.

:: Provisioning Work Directories
if not exist "cache" mkdir cache
if not exist "logs" mkdir logs
if not exist "output" mkdir output

:: 1. Deteksi Python Sistem & Cek Dukungan Tkinter
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python -c "import tkinter" >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        echo [*] Python sistem terdeteksi. Memeriksa dan memperbarui dependensi...
        python -m pip install -r requirements.txt --quiet --no-warn-script-location
        echo [*] Memeriksa konfigurasi awal...
        python scripts\init_config.py
        echo [*] Menjalankan NRA-Metadata...
        echo.
        python apps\desktop\src\main.py
        goto :END
    )
)

:: 2. Auto-Install via Winget jika Python belum ada
where winget >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [*] Python belum terpasang. Memasang Python 3.11 via Winget...
    winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
    if !ERRORLEVEL! equ 0 (
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
        echo [*] Memasang dependensi dari requirements.txt...
        python -m pip install --upgrade pip --quiet
        python -m pip install -r requirements.txt --quiet --no-warn-script-location
        python scripts\init_config.py
        python apps\desktop\src\main.py
        goto :END
    )
)

:: 3. Fallback Installer Resmi
echo [*] Mengunduh runtime Python resmi...
if not exist "tools" mkdir tools
set "INSTALLER_PATH=tools\python_installer.exe"
if not exist "!INSTALLER_PATH!" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; " ^
      "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '!INSTALLER_PATH!'"
)
if exist "!INSTALLER_PATH!" (
    start /wait "" "!INSTALLER_PATH!" /quiet InstallAllUsers=0 PrependPath=1 Include_tcltk=1 Include_pip=1
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
    echo [*] Memasang dependensi...
    python -m pip install -r requirements.txt --quiet --no-warn-script-location
    python scripts\init_config.py
    python apps\desktop\src\main.py
    goto :END
)

:ERROR
echo.
echo [ERROR] Gagal menyiapkan environment Python.
pause
exit /b 1

:END
echo.
echo =======================================================
echo Launcher selesai.
pause