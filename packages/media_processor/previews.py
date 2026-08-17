import os
import tempfile
import subprocess
from PIL import Image

def get_msedge_path():
    paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]
    for p in paths:
        if os.path.exists(p): return p
    return None

from packages.media_processor.embedder import log_failed_file

def extract_preview_image(file_path: str, processor) -> str | None:
    ext = file_path.lower().split('.')[-1]
    temp_dir = tempfile.gettempdir()
    out_path = os.path.join(temp_dir, f"preview_{os.path.basename(file_path)}.jpg")

    if ext in ['jpg', 'jpeg', 'png', 'webp', 'bmp', 'tif', 'tiff']:
        try:
            img = Image.open(file_path).convert('RGB')
            img.thumbnail((1024, 1024))
            img.save(out_path, 'JPEG')
            return out_path
        except Exception as e:
            err = f"Image extract error: {e}"
            print(f"[SKIP ERROR] {os.path.basename(file_path)}: {err}")
            log_failed_file(os.path.dirname(file_path), os.path.basename(file_path), err)
            return None
    elif ext in ['eps', 'ai']:
        gs_path = processor.get_tool_path("ghostscript")
        cmd = [gs_path, "-dSAFER", "-dBATCH", "-dNOPAUSE", "-sDEVICE=jpeg", "-r150", f"-sOutputFile={out_path}", file_path]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return out_path
        except subprocess.CalledProcessError as e:
            err = f"Ghostscript error: {e.stderr}"
            print(f"[SKIP ERROR] {os.path.basename(file_path)}: {err}")
            log_failed_file(os.path.dirname(file_path), os.path.basename(file_path), err)
            return None
    elif ext in ['mp4', 'mov', 'avi', 'mkv']:
        ffmpeg_path = processor.get_tool_path("ffmpeg")
        cmd = [ffmpeg_path, "-y", "-i", file_path, "-ss", "00:00:01", "-vframes", "1", out_path]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return out_path
        except subprocess.CalledProcessError as e:
            err = f"FFmpeg error: {e.stderr}"
            print(f"[SKIP ERROR] {os.path.basename(file_path)}: {err}")
            log_failed_file(os.path.dirname(file_path), os.path.basename(file_path), err)
            return None
    elif ext == 'svg':
        edge_path = get_msedge_path()
        if edge_path:
            png_path = out_path.replace('.jpg', '.png')
            cmd = [edge_path, "--headless", "--disable-gpu", f"--screenshot={png_path}", "--window-size=1024,1024", f"file:///{os.path.abspath(file_path)}"]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                if os.path.exists(png_path):
                    img = Image.open(png_path).convert('RGB')
                    img.thumbnail((1024, 1024))
                    img.save(out_path, 'JPEG')
                    os.remove(png_path)
                    return out_path
            except Exception as e:
                err = f"Edge SVG extract error: {e}"
                print(f"[SKIP ERROR] {os.path.basename(file_path)}: {err}")
                log_failed_file(os.path.dirname(file_path), os.path.basename(file_path), err)
        
        # Fallback 1: svglib
        try:
            from svglib.svglib import svg2rlg
            from reportlab.graphics import renderPM
            drawing = svg2rlg(file_path)
            if drawing:
                png_path = out_path.replace('.jpg', '.png')
                renderPM.drawToFile(drawing, png_path, fmt="PNG")
                img = Image.open(png_path).convert('RGB')
                img.thumbnail((1024, 1024))
                img.save(out_path, 'JPEG')
                os.remove(png_path)
                return out_path
        except Exception as e:
            err = f"svglib extract error: {e}"
            print(f"[SKIP ERROR] {os.path.basename(file_path)}: {err}")
            log_failed_file(os.path.dirname(file_path), os.path.basename(file_path), err)
            
        # Fallback 2: Raw text inspection wrapper for LLM
        return file_path
    return None
