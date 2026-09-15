import os
import sys
import subprocess
import zipfile
import urllib.request
import tempfile
import threading
from pathlib import Path

from backend.processors._tools import no_window_kwargs
from backend.processors.system_detector import discover_tools, reset_tool_cache


def get_tools_directory() -> Path:
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parent.parent.parent
    tools_dir = base_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    return tools_dir


def find_ghostscript_binary(tools_dir=None):
    if sys.platform != "win32":
        return "gs"

    from backend.processors.system_detector import detect_ghostscript

    return detect_ghostscript(silent=True, tools_dir=Path(tools_dir) if tools_dir else None)


_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
}


def _download(url: str, dest: str, timeout: int = 120):
    """Download url to dest, following redirects."""
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        # Reject HTML responses (CDN challenge pages)
        ct = resp.headers.get("Content-Type", "").lower()
        if "html" in ct:
            raise ValueError(f"Server returned HTML instead of binary (Content-Type: {ct})")
        with open(dest, "wb") as out:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                out.write(chunk)


def _is_valid_zip(path: str) -> bool:
    """Check ZIP magic bytes PK\\x03\\x04."""
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"PK\x03\x04"
    except OSError:
        return False


def ensure_tools_installed(tools_dir=None, progress_callback=None):
    td = Path(tools_dir) if tools_dir else get_tools_directory()
    td.mkdir(parents=True, exist_ok=True)

    def _log(msg):
        if progress_callback:
            progress_callback(msg)
        else:
            print(msg)

    found = discover_tools(log=_log)

    if sys.platform != "win32":
        _log("[INFO] Non-Windows platform - download skipped, detection complete.")
        return

    def _setup_exiftool():
        exe_in_subdir = td / "exiftool" / "exiftool.exe"
        exe_flat = td / "exiftool.exe"
        if exe_in_subdir.exists():
            _log(f"[SUCCESS] ExifTool found at: {exe_in_subdir.resolve()}")
            return
        elif exe_flat.exists():
            _log(f"[SUCCESS] ExifTool found at: {exe_flat.resolve()}")
            return

        _log(f"[ERROR] ExifTool NOT found at: {exe_in_subdir.resolve()}")
        _log("[INFO] Downloading ExifTool...")
        urls = [
            "https://oliverbetz.de/cms/files/Artikel/ExifTool-for-Windows/exiftool-13.59_64.zip",
            "https://sourceforge.net/projects/exiftool/files/exiftool-13.59_64.zip/download",
            "https://github.com/philharvey/ExifTool/releases/download/13.59/exiftool-13.59_64.zip",
        ]
        for url in urls:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                    tmp_path = tmp.name
                _download(url, tmp_path, timeout=20)
                if not _is_valid_zip(tmp_path):
                    os.remove(tmp_path)
                    _log(f"[WARN] ExifTool mirror returned non-zip payload, trying next...")
                    continue
                extract_dir = td / "exiftool"
                extract_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(tmp_path, "r") as zf:
                    zf.extractall(extract_dir)
                os.remove(tmp_path)
                # Oliver Betz package contains exiftool.exe directly
                # Phil Harvey package contains exiftool(-k).exe
                for f in extract_dir.rglob("exiftool(-k).exe"):
                    f.rename(extract_dir / "exiftool.exe")
                    break
                if (extract_dir / "exiftool.exe").exists():
                    _log("[SUCCESS] ExifTool installed.")
                    return
                # Search nested folders
                for f in extract_dir.rglob("exiftool.exe"):
                    _log("[SUCCESS] ExifTool installed.")
                    return
                _log("[WARN] ExifTool zip extracted but exiftool.exe not found inside.")
                return
            except Exception as e:
                _log(f"[WARN] ExifTool mirror failed ({e}), trying next...")
                continue
        _log("[WARN] All ExifTool download mirrors failed.")

    def _setup_ghostscript():
        gs_path = find_ghostscript_binary(td)
        if gs_path:
            _log(f"[SUCCESS] Ghostscript found at: {gs_path}")
            return
            
        _log("[INFO] Downloading Ghostscript...")
        installer = td / "gs_installer.exe"
        try:
            url = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10080/gs10080w64.exe"
            installer = td / "gs_installer.exe"
            _download(url, str(installer))
            _log("[INFO] Installing Ghostscript silently...")
            
            target_dir = str((td / "ghostscript").resolve())
            cmd = [str(installer), "/S", f"/D={target_dir}"]
            
            env = os.environ.copy()
            env["__COMPAT_LAYER"] = "RunAsInvoker"
            
            result = subprocess.run(
                cmd,
                check=False,
                timeout=120,
                env=env,
                **no_window_kwargs(),
            )
            
            if installer.exists():
                os.remove(str(installer))
            
            if result.returncode != 0:
                _log(f"[WARN] Ghostscript installer exited with code {result.returncode}.")
            
            gs_path_new = find_ghostscript_binary(td)
            if gs_path_new:
                _log(f"[SUCCESS] Ghostscript installed and verified at {gs_path_new}")
            else:
                _log("[WARN] Ghostscript installer ran but gswin64c.exe not found. Install manually or add to PATH.")
        except Exception as e:
            if installer.exists():
                os.remove(str(installer))
            _log(f"[WARN] Failed to download/install Ghostscript: {e}. Vector preview will use system PATH fallback.")

    def _setup_ffmpeg():
        if (td / "ffmpeg.exe").exists() or (td / "ffmpeg" / "bin" / "ffmpeg.exe").exists():
            return
        _log("[INFO] Downloading FFmpeg...")
        try:
            url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                tmp_path = tmp.name
            _download(url, tmp_path)
            if not _is_valid_zip(tmp_path):
                os.remove(tmp_path)
                _log("[WARN] FFmpeg download returned non-zip payload.")
                return
            with zipfile.ZipFile(tmp_path, "r") as zf:
                for info in zf.infolist():
                    if info.filename.endswith("bin/ffmpeg.exe"):
                        info.filename = "ffmpeg.exe"
                        zf.extract(info, str(td))
                        break
            os.remove(tmp_path)
            if (td / "ffmpeg.exe").exists():
                _log("[SUCCESS] FFmpeg installed.")
            else:
                _log("[WARN] FFmpeg zip extracted but ffmpeg.exe not found.")
        except Exception as e:
            _log(f"[WARN] Failed to download FFmpeg: {e}. Video frame extraction will use system PATH fallback.")

    threads = []
    if not found.get("exiftool"):
        threads.append(threading.Thread(target=_setup_exiftool, daemon=True))
    else:
        _log("[INFO] ExifTool already detected - skipping download.")
    if not found.get("ghostscript"):
        threads.append(threading.Thread(target=_setup_ghostscript, daemon=True))
    else:
        _log("[INFO] Ghostscript already detected - skipping download.")
    if not found.get("ffmpeg"):
        threads.append(threading.Thread(target=_setup_ffmpeg, daemon=True))
    else:
        _log("[INFO] FFmpeg already detected - skipping download.")
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    reset_tool_cache()
