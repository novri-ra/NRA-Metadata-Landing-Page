@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions EnableDelayedExpansion
title NRA-Metadata Launcher
cd /d "%~dp0"
set "PYTHONPATH=%CD%"

set "frame=+--------------------------------------------------+"

if /I "%~1"=="--help" goto :HELP
if /I "%~1"=="-h" goto :HELP
if /I "%~1"=="--check" goto :HELP

echo.
echo %frame%
echo ^|      NRA-Metadata - Auto Launcher      ^|
echo %frame%
echo [DIR] Project Directory: %CD%
echo %frame%
echo.

if not exist "cache" mkdir cache
if not exist "logs" mkdir logs
if not exist "output" mkdir output

:: 0. Pra-pemeriksaan folder tools eksternal
echo.
echo %frame%
echo [1/4] External tools pre-check (folder tools/)
echo %frame%
if exist "tools\exiftool" (
    echo   [OK]  ExifTool folder : tools\exiftool
) else (
    echo   [..]  ExifTool folder belum ada di tools\exiftool - deteksi otomatis via PATH
)
if exist "tools\ghostscript" (
    echo   [OK]  Ghostscript folder : tools\ghostscript
) else (
    echo   [..]  Ghostscript folder belum ada di tools\ghostscript - deteksi otomatis via PATH
)
if exist "tools\ffmpeg" (
    echo   [OK]  FFmpeg folder : tools\ffmpeg
) else (
    echo   [..]  FFmpeg folder belum ada di tools\ffmpeg - deteksi otomatis via PATH
)
if exist "tools\gtk3" (
    echo   [OK]  GTK3 Runtime folder : tools\gtk3
) else (
    echo   [..]  GTK3 Runtime folder belum ada di tools\gtk3 - deteksi otomatis via PATH
)
echo [i] Deteksi exhaustive berjalan otomatis di Python: recursive scan
echo [i] tools/ kemudian fallback ke PATH dan direktori umum Windows.
echo %frame%
echo.

:: 1. Deteksi Python Sistem & Cek Tkinter
echo.
echo %frame%
echo [2/4] Python environment check
echo %frame%
where python >nul 2>&1
if %ERRORLEVEL% neq 0 goto :CHECK_WINGET

python -c "import tkinter" >nul 2>&1
if %ERRORLEVEL% neq 0 goto :CHECK_WINGET

echo [SUCCESS] Python sistem terdeteksi (Tkinter tersedia).

if exist "cache\.deps_installed" goto :DEPS_CACHED

echo [i] Tidak ada cache dependensi - melakukan pemasangan fresh...
echo --------------------------------------------------------------
python -m pip install --upgrade pip
python -m pip install -r requirements.txt --no-warn-script-location
if %ERRORLEVEL% equ 0 (
    type nul > "cache\.deps_installed"
    echo [SUCCESS] Dependensi berhasil dipasang - fresh install.
) else (
    echo [WARN] Instalasi dependensi mengalami kendala. Mencoba melanjutkan...
)
echo --------------------------------------------------------------
goto :INIT_CONFIG

:DEPS_CACHED
echo [OK] Dependensi sudah terpasang - cache cache\.deps_installed ditemukan.
echo [*] Melewati instalasi ulang pip - hapus cache\.deps_installed untuk fresh.
goto :INIT_CONFIG

:CHECK_WINGET
where winget >nul 2>&1
if %ERRORLEVEL% neq 0 goto :FALLBACK_INSTALLER

echo [*] Python belum terpasang. Memasang Python 3.11 via Winget...
winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
if %ERRORLEVEL% neq 0 goto :FALLBACK_INSTALLER

set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
echo [*] Memasang dependensi (fresh install)...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt --no-warn-script-location
type nul > "cache\.deps_installed"
goto :INIT_CONFIG

:FALLBACK_INSTALLER
echo [*] Mengunduh runtime Python resmi...
if not exist "tools" mkdir tools
set "INSTALLER_PATH=tools\python_installer.exe"
if not exist "%INSTALLER_PATH%" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%INSTALLER_PATH%'"
)
if exist "%INSTALLER_PATH%" (
    echo [*] Memasang Python lokal - fresh install...
    start /wait "" "%INSTALLER_PATH%" /quiet InstallAllUsers=0 PrependPath=1 Include_tcltk=1 Include_pip=1
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
    echo [*] Memasang dependensi...
    python -m pip install -r requirements.txt --no-warn-script-location
    type nul > "cache\.deps_installed"
    goto :INIT_CONFIG
)

:ERROR
echo.
echo [ERROR] Gagal menyiapkan environment Python.
pause
exit /b 1

:INIT_CONFIG
echo.
echo %frame%
echo [3/4] Virtual Environment check
echo %frame%
if exist "venv\Scripts\activate.bat" (
    echo [i] Virtual environment ditemukan. Mengaktifkan venv...
    call "venv\Scripts\activate.bat"
) else (
    echo [i] venv tidak ditemukan, menggunakan global Python.
)
goto :LAUNCH_APP

:LAUNCH_APP
echo.
echo %frame%
echo [4/4] Launching NRA-Metadata
echo %frame%
echo [*] Menjalankan NRA-Metadata...
echo.
python apps\desktop\src\main.py
set "APP_EXIT=!ERRORLEVEL!"
goto :END

:END
echo.
echo %frame%
if "!APP_EXIT!"=="0" (
    echo [SUCCESS] Aplikasi selesai dengan sukses.
) else (
    echo [WARN] Aplikasi berhenti dengan exit code !APP_EXIT!.
    echo [HINT] Periksa error di atas; jendela oleh dipertahankan untuk debug.
)
echo %frame%
echo.
pause
exit /b !APP_EXIT!

:HELP
echo.
echo %frame%
echo ^|  NRA-Metadata Launcher - usage  ^|
echo ^|  Argumen opsional:               ^|
echo ^|    --help   Tampilkan bantuan lalu keluar.  ^|
echo ^|    --check  Pre-flight check lalu keluar.   ^|
echo %frame%
pause
exit /b 0