@echo off
setlocal enabledelayedexpansion
title NRA-Metadata Launcher
cd /d "%~dp0"
set "PYTHONPATH=%CD%"

set "frame=+--------------------------------------------------+"

echo.
echo %frame%
echo |          NRA-Metadata - Auto Launcher          |
echo %frame%
echo [DIR] Project Directory : %CD%
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
call :FOLDER_CHECK "tools\exiftool" "ExifTool"
call :FOLDER_CHECK "tools\ghostscript" "Ghostscript"
call :FOLDER_CHECK "tools\ffmpeg" "FFmpeg"
call :FOLDER_CHECK "tools\gtk3" "GTK3 Runtime"
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
    echo. > "cache\.deps_installed"
    echo [SUCCESS] Dependensi berhasil dipasang (fresh install).
) else (
    echo [WARN] Instalasi dependensi mengalami kendala. Mencoba melanjutkan...
)
echo --------------------------------------------------------------
goto :INIT_CONFIG

:DEPS_CACHED
echo [OK] Dependensi sudah terpasang (cache cache\.deps_installed ditemukan).
echo [*] Melewati instalasi ulang pip (hapus cache\.deps_installed untuk fresh).
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
echo. > "cache\.deps_installed"
goto :INIT_CONFIG

:FALLBACK_INSTALLER
echo [*] Mengunduh runtime Python resmi...
if not exist "tools" mkdir tools
set "INSTALLER_PATH=tools\python_installer.exe"
if not exist "%INSTALLER_PATH%" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%INSTALLER_PATH%'"
)
if exist "%INSTALLER_PATH%" (
    echo [*] Memasang Python lokal (fresh install)...
    start /wait "" "%INSTALLER_PATH%" /quiet InstallAllUsers=0 PrependPath=1 Include_tcltk=1 Include_pip=1
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
    echo [*] Memasang dependensi...
    python -m pip install -r requirements.txt --no-warn-script-location
    echo. > "cache\.deps_installed"
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
echo [3/4] Initial configuration
echo %frame%
echo [*] Menjalankan scripts\init_config.py ...
python scripts\init_config.py
set "IC_ERR=%ERRORLEVEL%"
if not "%IC_ERR%"=="0" goto :INIT_FAILED
echo [SUCCESS] Konfigurasi awal siap.
echo %frame%
goto :LAUNCH_APP

:INIT_FAILED
echo [ERROR] scripts\init_config.py keluar dengan exit code %IC_ERR%.
pause
exit /b %IC_ERR%

:LAUNCH_APP
echo.
echo %frame%
echo [4/4] Launching NRA-Metadata
echo %frame%
echo [*] Menjalankan NRA-Metadata...
echo.
python apps\desktop\src\main.py
set "APP_EXIT=%ERRORLEVEL%"
if not "%APP_EXIT%"=="0" goto :END

:END
echo.
echo %frame%
if "%APP_EXIT%"=="" set "APP_EXIT=0"
if "%APP_EXIT%"=="0" (
    echo Launcher selesai dengan sukses.
) else (
    echo [WARN] Aplikasi berhenti dengan exit code %APP_EXIT%.
)
echo %frame%
pause
exit /b %APP_EXIT%

:FOLDER_CHECK
if exist "%~1" (
    echo   [OK]  %~2 folder : %~1
) else (
    echo   [..]  %~2 folder belum ada di %~1 - deteksi otomatis via PATH
)
exit /b 0