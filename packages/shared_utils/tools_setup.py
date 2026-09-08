import os
import sys
import zipfile
import urllib.request
import tempfile
import threading
from pathlib import Path


def get_tools_directory() -> Path:
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parent.parent.parent
    tools_dir = base_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    return tools_dir


_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _download(url: str, dest: str):
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as out:
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            out.write(chunk)


def ensure_tools_installed(tools_dir=None, progress_callback=None):
    if sys.platform != "win32":
        return

    td = Path(tools_dir) if tools_dir else get_tools_directory()
    td.mkdir(parents=True, exist_ok=True)

    def _log(msg):
        if progress_callback:
            progress_callback(msg)
        else:
            print(msg)

    def _setup_exiftool():
        candidates = [td / "exiftool" / "exiftool.exe", td / "exiftool.exe"]
        if any(c.exists() for c in candidates):
            return
        _log("[INFO] Downloading ExifTool...")
        try:
            url = "https://exiftool.org/exiftool-13.10.zip"
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                tmp_path = tmp.name
            _download(url, tmp_path)
            extract_dir = td / "exiftool"
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(tmp_path, "r") as zf:
                zf.extractall(extract_dir)
            os.remove(tmp_path)
            # Rename exiftool(-k).exe to exiftool.exe if needed
            for f in extract_dir.rglob("exiftool(-k).exe"):
                f.rename(extract_dir / "exiftool.exe")
                break
            # Also check for exiftool.exe directly extracted
            _log("[SUCCESS] ExifTool installed.")
        except Exception as e:
            _log(f"[WARN] Failed to download ExifTool: {e}")

    def _setup_ghostscript():
        candidates = [
            td / "ghostscript" / "bin" / "gswin64c.exe",
            td / "gswin64c.exe",
        ]
        if any(c.exists() for c in candidates):
            return
        _log("[INFO] Downloading Ghostscript...")
        try:
            url = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10040/gs10040w64.exe"
            dest = td / "gswin64c.exe"
            _download(url, str(dest))
            _log("[SUCCESS] Ghostscript installed.")
        except Exception as e:
            _log(f"[WARN] Failed to download Ghostscript: {e}")

    def _setup_ffmpeg():
        candidates = [
            td / "ffmpeg" / "bin" / "ffmpeg.exe",
            td / "ffmpeg.exe",
        ]
        if any(c.exists() for c in candidates):
            return
        _log("[INFO] Downloading FFmpeg...")
        try:
            url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                tmp_path = tmp.name
            _download(url, tmp_path)
            with zipfile.ZipFile(tmp_path, "r") as zf:
                # Extract only ffmpeg.exe from the archive to save space
                for info in zf.infolist():
                    if info.filename.endswith("bin/ffmpeg.exe"):
                        info.filename = "ffmpeg.exe"
                        zf.extract(info, str(td))
                        break
            os.remove(tmp_path)
            _log("[SUCCESS] FFmpeg installed.")
        except Exception as e:
            _log(f"[WARN] Failed to download FFmpeg: {e}")

    threads = [
        threading.Thread(target=_setup_exiftool, daemon=True),
        threading.Thread(target=_setup_ghostscript, daemon=True),
        threading.Thread(target=_setup_ffmpeg, daemon=True),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
