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

if not exist "logs" mkdir "logs"
if not exist "cache" mkdir "cache"
if not exist "output" mkdir "output"

:: 0. Pra-pemeriksaan folder tools eksternal
echo.
echo %frame%
echo [1/3] External tools pre-check (folder tools/)
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

:: 1. Deteksi Virtual Environment
echo.
echo %frame%
echo [2/3] Virtual Environment check
echo %frame%
if exist ".venv\Scripts\python.exe" (
    echo [i] Virtual environment '.venv' ditemukan.
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    echo [WARN] Virtual environment '.venv' tidak ditemukan!
    echo [*] Membuat virtual environment baru secara otomatis...

    where uv >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo [i] Menggunakan 'uv' untuk membuat venv...
        uv venv
    ) else (
        echo [i] Menggunakan 'python' bawaan untuk membuat venv...
        python -m venv .venv
    )

    if exist ".venv\Scripts\python.exe" (
        echo [SUCCESS] Virtual environment berhasil dibuat.
        set "PYTHON_EXE=.venv\Scripts\python.exe"
        if exist "cache\.deps_installed" del /q "cache\.deps_installed"
    ) else (
        echo [ERROR] Gagal membuat virtual environment. Pastikan Python terinstal dan masuk ke PATH.
        pause
        exit /b 1
    )
)

:: 2. Check Dependencies (Optional)
if exist "cache\.deps_installed" goto :LAUNCH_APP

echo [i] Tidak ada cache dependensi - melakukan pemasangan di dalam .venv...
echo --------------------------------------------------------------
"!PYTHON_EXE!" -m pip --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [i] pip tidak ditemukan di .venv, mencoba sinkronisasi via uv...
    where uv >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        uv pip install -r requirements.txt
        type nul > "cache\.deps_installed"
        echo [SUCCESS] Dependensi berhasil dipasang via uv.
    ) else (
        echo [WARN] uv maupun pip tidak tersedia di .venv. Mengabaikan check pip...
        type nul > "cache\.deps_installed"
    )
) else (
    "!PYTHON_EXE!" -m pip install --upgrade pip
    "!PYTHON_EXE!" -m pip install -r requirements.txt --no-warn-script-location
    if !ERRORLEVEL! equ 0 (
        type nul > "cache\.deps_installed"
        echo [SUCCESS] Dependensi berhasil dipasang via pip.
    ) else (
        echo [WARN] Instalasi dependensi mengalami kendala. Mencoba melanjutkan...
    )
)
echo --------------------------------------------------------------
goto :LAUNCH_APP

:LAUNCH_APP
echo.
echo %frame%
echo [3/3] Launching NRA-Metadata
echo %frame%
echo [*] Menjalankan NRA-Metadata...
echo.
"!PYTHON_EXE!" apps\desktop\src\main.py
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
exit /b 0