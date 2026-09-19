import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

def get_tools_directory() -> Path:
    base_dir = Path(__file__).resolve().parent.parent
    tools_dir = base_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    return tools_dir

def log(msg):
    print(msg)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
}

def download(url: str, dest: str, timeout: int = 120):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        ct = resp.headers.get("Content-Type", "").lower()
        if "html" in ct:
            raise ValueError(f"Server returned HTML (Content-Type: {ct})")
        with open(dest, "wb") as out:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                out.write(chunk)

def check_zip(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"PK\x03\x04"
    except OSError:
        return False

def setup_exiftool(td: Path):
    exe1 = td / "exiftool" / "exiftool.exe"
    exe2 = td / "exiftool.exe"
    if exe1.exists():
        log("[OK] ExifTool sudah terpasang. (Skipped)")
        return
    if exe2.exists():
        log("[OK] ExifTool sudah terpasang. (Skipped)")
        return
    
    log("[INFO] Downloading ExifTool...")
    urls = [
        "https://oliverbetz.de/cms/files/Artikel/ExifTool-for-Windows/exiftool-13.59_64.zip",
        "https://sourceforge.net/projects/exiftool/files/exiftool-13.59_64.zip/download",
        "https://github.com/philharvey/ExifTool/releases/download/13.59/exiftool-13.59_64.zip",
    ]
    
    for url in urls:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                tmp_path = tmp.name
            download(url, tmp_path, timeout=30)
            if not check_zip(tmp_path):
                os.remove(tmp_path)
                log("[WARN] ExifTool mirror returned invalid zip, trying next...")
                continue
                
            extract_dir = td / "exiftool"
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(tmp_path, "r") as zf:
                target_abs = os.path.abspath(extract_dir) + os.sep
                for member in zf.namelist():
                    member_abs = os.path.abspath(os.path.join(extract_dir, member))
                    if not member_abs.startswith(target_abs):
                        continue
                    zf.extract(member, extract_dir)
            os.remove(tmp_path)
            
            for f in extract_dir.rglob("exiftool(-k).exe"):
                f.rename(extract_dir / "exiftool.exe")
                break
                
            if (extract_dir / "exiftool.exe").exists() or any(extract_dir.rglob("exiftool.exe")):
                log("[SUCCESS] ExifTool berhasil diunduh dan diekstrak.")
                return
            log("[WARN] ExifTool zip extracted but no exe found.")
        except Exception as e:
            log(f"[WARN] ExifTool download failed ({e}), trying next...")
    log("[ERROR] Gagal mengunduh ExifTool.")

def setup_ffmpeg(td: Path):
    exe1 = td / "ffmpeg.exe"
    exe2 = td / "ffmpeg" / "bin" / "ffmpeg.exe"
    if exe1.exists() or exe2.exists():
        log("[OK] FFmpeg sudah terpasang. (Skipped)")
        return
        
    log("[INFO] Downloading FFmpeg...")
    url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp_path = tmp.name
        download(url, tmp_path, timeout=120)
        if not check_zip(tmp_path):
            os.remove(tmp_path)
            log("[ERROR] FFmpeg download returned invalid zip.")
            return
            
        with zipfile.ZipFile(tmp_path, "r") as zf:
            for info in zf.infolist():
                if info.filename.endswith("bin/ffmpeg.exe"):
                    info.filename = "ffmpeg.exe"
                    zf.extract(info, str(td))
                    break
        os.remove(tmp_path)
        
        if (td / "ffmpeg.exe").exists():
            log("[SUCCESS] FFmpeg berhasil diunduh dan diekstrak.")
        else:
            log("[ERROR] FFmpeg zip extracted but no exe found.")
    except Exception as e:
        log(f"[ERROR] Gagal mengunduh FFmpeg: {e}")

def main():
    if os.name != "nt":
        log("[INFO] Non-Windows OS detected. Skipping portable tools download.")
        return
    td = get_tools_directory()
    setup_exiftool(td)
    setup_ffmpeg(td)

if __name__ == "__main__":
    main()
