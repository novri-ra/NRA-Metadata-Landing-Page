# Standalone tool bootstrap for NRA-Metadata (Windows).
# Idempotent: skips any tool already present in tools/ or on PATH/Program Files,
# downloads only what is missing, and cleans up all temp files afterwards.
$ErrorActionPreference = "Stop"

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ToolsDir = Join-Path $RootDir "tools"

$UserAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

function Test-ExifTool {
    $Local = Join-Path $ToolsDir "exiftool\exiftool.exe"
    if (Test-Path $Local) { return "tools\exiftool\exiftool.exe" }
    $InPath = Get-Command "exiftool.exe" -ErrorAction SilentlyContinue
    if ($InPath) { return $InPath.Source }
    return $null
}

function Test-Ghostscript {
    $Local = Join-Path $ToolsDir "ghostscript\bin\gswin64c.exe"
    if (Test-Path $Local) { return "tools\ghostscript\bin\gswin64c.exe" }
    $InPath = Get-Command "gswin64c.exe" -ErrorAction SilentlyContinue
    if ($InPath) { return $InPath.Source }
    $Pf = @("$env:ProgramFiles", "${env:ProgramFiles(x86)}") | Where-Object { $_ }
    foreach ($p in $Pf) {
        $Hit = Get-ChildItem (Join-Path $p "gs\gs*\bin\gswin64c.exe") -ErrorAction SilentlyContinue |
            Sort-Object { [Version]($_.FullName -replace '.*\\gs([0-9._]+)\\.*', '$1') } -Descending | Select-Object -First 1
        if ($Hit) { return $Hit.FullName }
    }
    return $null
}

function Test-FFmpeg {
    $Local = Join-Path $ToolsDir "ffmpeg\bin\ffmpeg.exe"
    if (Test-Path $Local) { return "tools\ffmpeg\bin\ffmpeg.exe" }
    $InPath = Get-Command "ffmpeg.exe" -ErrorAction SilentlyContinue
    if ($InPath) { return $InPath.Source }
    return $null
}

function Invoke-Download($Url, $Dest) {
    $ProgressPreference = "SilentlyContinue"
    Invoke-WebRequest -Uri $Url -OutFile $Dest -UserAgent $UserAgent -UseBasicParsing
}

# ---------------------------------------------------------------- skip checks
$ExifTool = Test-ExifTool
if ($ExifTool) { Write-Host "ExifTool already installed, skipping." } else { Write-Host "ExifTool not found, queueing download..." }

$Ghostscript = Test-Ghostscript
if ($Ghostscript) { Write-Host "Ghostscript already installed, skipping." } else { Write-Host "Ghostscript not found, queueing download..." }

$FFmpeg = Test-FFmpeg
if ($FFmpeg) { Write-Host "FFmpeg already installed, skipping." } else { Write-Host "FFmpeg not found, queueing download..." }

if ($ExifTool -and $Ghostscript -and $FFmpeg) {
    Write-Host "All tools are already configured. No download needed."
    exit 0
}

New-Item -ItemType Directory -Force -Path (Join-Path $ToolsDir "exiftool") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $ToolsDir "ghostscript") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $ToolsDir "ffmpeg") | Out-Null

# ---------------------------------------------------------------- ExifTool
if (-not $ExifTool) {
    $Zip = Join-Path $ToolsDir "exiftool.zip"
    Write-Host "Downloading ExifTool..."
    try {
        $ExifUrls = @(
            "https://oliverbetz.de/cms/files/Artikel/ExifTool-for-Windows/exiftool-13.59_64.zip",
            "https://sourceforge.net/projects/exiftool/files/exiftool-13.59_64.zip/download",
            "https://github.com/philharvey/ExifTool/releases/download/13.59/exiftool-13.59_64.zip"
        )
        foreach ($url in $ExifUrls) {
            try {
                Invoke-Download $url $Zip
                if ((Get-Item $Zip).Length -lt 100) { continue }
                Expand-Archive -Path $Zip -DestinationPath (Join-Path $ToolsDir "exiftool") -Force
                $Renamed = Get-ChildItem (Join-Path $ToolsDir "exiftool") -Recurse -Filter "exiftool(-k).exe" | Select-Object -First 1
                if ($Renamed) { Move-Item $Renamed.FullName (Join-Path $ToolsDir "exiftool\exiftool.exe") -Force }
                if (Test-Path (Join-Path $ToolsDir "exiftool\exiftool.exe")) {
                    Write-Host "ExifTool installed."
                    break
                }
                Write-Host "ExifTool zip extracted but exiftool.exe missing, trying next mirror..."
            } catch {
                Write-Host "ExifTool mirror failed ($($_.Exception.Message)), trying next..."
            } finally {
                Remove-Item $Zip -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {
        Write-Host "ExifTool download failed: $($_.Exception.Message)"
    }
}

# ---------------------------------------------------------------- Ghostscript
if (-not $Ghostscript) {
    $Installer = Join-Path $ToolsDir "gs_installer.exe"
    Write-Host "Downloading Ghostscript..."
    try {
        Invoke-Download "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10080/gs10080w64.exe" $Installer
        Write-Host "Installing Ghostscript silently..."
        $Target = Join-Path $ToolsDir "ghostscript"
        $env:__COMPAT_LAYER = "RunAsInvoker"
        $Proc = Start-Process -FilePath $Installer -ArgumentList "/S", "/D=$Target" -Wait -PassThru
        Remove-Item Env:__COMPAT_LAYER -ErrorAction SilentlyContinue
        if ($Proc.ExitCode -ne 0) { Write-Host "Ghostscript installer exited with code $($Proc.ExitCode)." }
        if (Test-Path (Join-Path $Target "bin\gswin64c.exe")) {
            Write-Host "Ghostscript installed."
        } else {
            Write-Host "Ghostscript installer ran but gswin64c.exe not found. Install manually or add to PATH."
        }
    } catch {
        Write-Host "Failed to download/install Ghostscript: $($_.Exception.Message)"
    } finally {
        Remove-Item $Installer -Force -ErrorAction SilentlyContinue
    }
}

# ---------------------------------------------------------------- FFmpeg
if (-not $FFmpeg) {
    $Zip = Join-Path $ToolsDir "ffmpeg.zip"
    Write-Host "Downloading FFmpeg..."
    try {
        Invoke-Download "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip" $Zip
        $BinTarget = Join-Path $ToolsDir "ffmpeg\bin"
        Expand-Archive -Path $Zip -DestinationPath (Join-Path $ToolsDir "ffmpeg\_tmp") -Force
        $Exe = Get-ChildItem (Join-Path $ToolsDir "ffmpeg\_tmp") -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
        if ($Exe) {
            New-Item -ItemType Directory -Force -Path $BinTarget | Out-Null
            Move-Item $Exe.FullName (Join-Path $BinTarget "ffmpeg.exe") -Force
            Write-Host "FFmpeg installed."
        } else {
            Write-Host "FFmpeg zip extracted but ffmpeg.exe not found."
        }
        Remove-Item (Join-Path $ToolsDir "ffmpeg\_tmp") -Recurse -Force -ErrorAction SilentlyContinue
    } catch {
        Write-Host "Failed to download FFmpeg: $($_.Exception.Message)"
    } finally {
        Remove-Item $Zip -Force -ErrorAction SilentlyContinue
    }
}

# ---------------------------------------------------------------- cleanup
Write-Host "Setup complete."