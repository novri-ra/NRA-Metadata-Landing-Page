@echo off
setlocal EnableDelayedExpansion
title NRA-Metadata Launcher

cd /d "%~dp0"

echo [NRA-Metadata] Memeriksa environment Python...

:: Cek Python Global
python --version >nul 2>&1
if %ERRORLEVEL% equ 0 (
    for /f "tokens=2" %%v in ('python --version') do set "PY_VER=%%v"
    echo [NRA-Metadata] Menggunakan Python Global v!PY_VER!
    set "PYTHON_EXE=python"
    
    :: Install deps global jika belum
    if not exist ".global_deps_installed" (
        echo [NRA-Metadata] Menginstal dependensi ke global Python...
        python -m pip install --upgrade pip >nul 2>&1
        python -m pip install -r requirements.txt >nul 2>&1
        echo done > ".global_deps_installed"
    )
    goto :LaunchApp
)

echo [NRA-Metadata] Python global tidak terdeteksi.
echo [NRA-Metadata] Menyiapkan runtime portable otomatis (Zero-Setup)...

set "RUNTIME_DIR=tools\python_runtime"
set "PYTHON_EXE=%RUNTIME_DIR%\python.exe"

if not exist "%RUNTIME_DIR%" (
    mkdir "%RUNTIME_DIR%"
)

if not exist "%PYTHON_EXE%" (
    echo [NRA-Metadata] Mengunduh Python 3.11 Embeddable...
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip' -OutFile 'tools\python-embed.zip'"
    
    echo [NRA-Metadata] Mengekstrak Python...
    powershell -Command "Expand-Archive -Path 'tools\python-embed.zip' -DestinationPath '%RUNTIME_DIR%' -Force"
    del "tools\python-embed.zip"
    
    echo [NRA-Metadata] Mengkonfigurasi environment Python portable...
    :: Un-comment import site di file ._pth agar pip bisa bekerja
    powershell -Command "(Get-Content '%RUNTIME_DIR%\python311._pth') -replace '#import site', 'import site' | Set-Content '%RUNTIME_DIR%\python311._pth'"
    
    echo [NRA-Metadata] Mengunduh PIP...
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%RUNTIME_DIR%\get-pip.py'"
    
    echo [NRA-Metadata] Menginstal PIP...
    "%PYTHON_EXE%" "%RUNTIME_DIR%\get-pip.py" --no-warn-script-location
)

:: Install Dependencies Portable
if not exist "%RUNTIME_DIR%\.deps_installed" (
    echo [NRA-Metadata] Menginstal dependensi proyek (ini hanya terjadi sekali, harap tunggu)...
    "%PYTHON_EXE%" -m pip install --upgrade pip --no-warn-script-location
    "%PYTHON_EXE%" -m pip install -r requirements.txt --no-warn-script-location
    echo done > "%RUNTIME_DIR%\.deps_installed"
)

:LaunchApp
echo [NRA-Metadata] Menjalankan Aplikasi...
set PYTHONPATH=%CD%
"%PYTHON_EXE%" apps\desktop\src\main.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [FATAL ERROR] Aplikasi berhenti secara tidak wajar (Crash).
    echo Silakan baca log di atas untuk mengetahui masalahnya.
    pause
)

endlocal
