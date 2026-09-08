import os
import sys
import zipfile
import urllib.request
import tempfile
import threading

def get_base_path() -> str:
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def ensure_tools_installed(tools_dir=None, progress_callback=None):
    if not tools_dir:
        tools_dir = os.path.join(get_base_path(), "tools")
    
    os.makedirs(tools_dir, exist_ok=True)
    
    # We define the expected binary relative to tools_dir and the download URL.
    # We use reliable portable zip distributions.
    tools_config = {
        "exiftool": {
            "exe": os.path.join("exiftool", "exiftool.exe"),
            "url": "https://github.com/exiftool/exiftool/releases/download/12.98/exiftool-12.98_win.zip",
            "extract_folder": "exiftool"
        },
        "ghostscript": {
            "exe": os.path.join("ghostscript", "bin", "gswin64c.exe"),
            "url": "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10031/ghostscript-10.03.1-win64.zip",
            "extract_folder": "ghostscript"
        },
        "ffmpeg": {
            "exe": os.path.join("ffmpeg", "bin", "ffmpeg.exe"),
            "url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
            "extract_folder": "ffmpeg"
        }
    }

    if sys.platform != "win32":
        return # Auto-downloader logic currently tailored for Windows portable ZIPs

    def download_and_extract(tool_name, config):
        exe_path = os.path.join(tools_dir, config["exe"])
        alt_exe_path = os.path.join(tools_dir, f"{tool_name}.exe")
        
        # Check if already installed
        if os.path.exists(exe_path) or os.path.exists(alt_exe_path):
            return

        if progress_callback:
            progress_callback(f"[INFO] Downloading {tool_name}...")
        else:
            print(f"[INFO] Downloading {tool_name}...")

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                temp_zip_path = tmp.name
                urllib.request.urlretrieve(config["url"], temp_zip_path)

            target_extract = os.path.join(tools_dir, config["extract_folder"])
            os.makedirs(target_extract, exist_ok=True)

            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                # We extract everything into target_extract.
                # Note: Some zip files contain a root folder. The user might need to rename,
                # but we'll extract as-is and let `MediaProcessor` search a bit if needed, 
                # or we just rely on standard paths.
                zip_ref.extractall(target_extract)
                
            os.remove(temp_zip_path)
            
            # Post-processing: Exiftool zip renames itself inside, FFmpeg has a root folder.
            # To keep it robust without overcomplicating, we'll let the embedder logic scan 
            # for the exe inside the extract_folder.
            
            if progress_callback:
                progress_callback(f"[SUCCESS] {tool_name} installed.")
            else:
                print(f"[SUCCESS] {tool_name} installed.")

        except Exception as e:
            msg = f"[WARN] Failed to download {tool_name}: {e}"
            if progress_callback:
                progress_callback(msg)
            else:
                print(msg)

    threads = []
    for t_name, t_config in tools_config.items():
        t = threading.Thread(target=download_and_extract, args=(t_name, t_config))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()
