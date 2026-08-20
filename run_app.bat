@echo off
setlocal enabledelayedexpansion
title NRA-Metadata Launcher
cd /d "%~dp0"
set "PYTHONPATH=%CD%"

echo =======================================================
echo         NRA-Metadata - Auto Launcher
echo =======================================================
echo.

:: 1. Cek Python Global di Sistem (Pastikan memiliki Tkinter)
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python -c "import tkinter, customtkinter" >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        echo [*] Python global dengan dependensi lengkap ditemukan.
        echo [*] Menjalankan NRA-Metadata...
        echo.
        python apps\desktop\src\main.py
        goto :END
    )
    python -c "import tkinter" >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        echo [*] Python sistem ditemukan. Menginstal/memeriksa dependensi...
        python -m pip install -r requirements.txt --no-warn-script-location
        echo [*] Menjalankan NRA-Metadata...
        echo.
        python apps\desktop\src\main.py
        goto :END
    )
)

:: 2. Auto-Install Python 3.11 Resmi via Winget (Jika Tersedia di Windows)
where winget >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [*] Python belum terpasang. Memasang Python 3.11 resmi via Windows Package Manager...
    winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
    if !ERRORLEVEL! equ 0 (
        echo [*] Python 3.11 berhasil dipasang. Menyiapkan dependensi...
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
        python -m pip install --upgrade pip
        python -m pip install -r requirements.txt
        python apps\desktop\src\main.py
        goto :END
    )
)

:: 3. Fallback: Download & Silent Install Python Installer Resmi (Full Tkinter Support)
echo [*] Mengunduh runtime Python 3.11 installer resmi (dengan dukungan penuh Tkinter)...
if not exist "tools" mkdir tools
set "INSTALLER_PATH=tools\python_installer.exe"

if not exist "!INSTALLER_PATH!" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; " ^
      "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '!INSTALLER_PATH!'"
)

if exist "!INSTALLER_PATH!" (
    echo [*] Memasang Python lokal portabel...
    start /wait "" "!INSTALLER_PATH!" /quiet InstallAllUsers=0 PrependPath=1 Include_tcltk=1 Include_pip=1
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
    python -m pip install -r requirements.txt
    python apps\desktop\src\main.py
    goto :END
)

:ERROR
echo.
echo [ERROR] Gagal menyiapkan environment Python.
echo Silakan pastikan koneksi internet aktif atau pasang Python 3.11 manual dari python.org.

:END
echo.
echo =======================================================
echo Launcher selesai. Tekan sembarang tombol untuk keluar.
pause