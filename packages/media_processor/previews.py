import os
import subprocess
import tempfile

from PIL import Image


def get_msedge_path():
    paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None


from packages.media_processor.embedder import log_failed_file
from packages.shared_utils.tools_setup import find_ghostscript_binary


def extract_preview_image(file_path: str, processor, progress_callback=None) -> str | None:
    file_path = os.path.abspath(file_path)
    ext = file_path.lower().split(".")[-1]
    temp_dir = tempfile.gettempdir()
    out_path = os.path.join(temp_dir, f"preview_{os.path.basename(file_path)}.jpg")
    filename = os.path.basename(file_path)

    def _log(msg, level="info"):
        if progress_callback:
            progress_callback(msg, level)
        else:
            print(f"[{level.upper()}] {msg}")

    if ext in ["jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff"]:
        try:
            img = Image.open(file_path).convert("RGB")
            img.thumbnail((1024, 1024))
            img.save(out_path, "JPEG")
            _log(f"[{filename}] Image preview generated.", "success")
            return out_path
        except (OSError, ValueError) as e:
            err = f"Image preview generation failed: {e}"
            _log(f"[{filename}] {err}", "error")
            log_failed_file(
                os.path.dirname(file_path), filename, err
            )
            return None
    elif ext in ["eps", "ai"]:
        gs_path = find_ghostscript_binary()
        if gs_path:
            _log(f"[{filename}] Format: {ext.upper()}. Rendering raster preview using Ghostscript...", "info")
            cmd = [
                gs_path,
                "-dSAFER",
                "-dBATCH",
                "-dNOPAUSE",
                "-sDEVICE=jpeg",
                "-r150",
                "-dTextAlphaBits=4",
                "-dGraphicsAlphaBits=4",
                f"-sOutputFile={out_path}",
                file_path,
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=15)
                if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                    try:
                        with Image.open(out_path) as verify_img:
                            verify_img.verify()
                        _log(f"[{filename}] Preview rendered successfully.", "success")
                        return out_path
                    except (OSError, ValueError) as e:
                        err = f"Ghostscript produced invalid image: {e}"
                        _log(f"[{filename}] {err}", "error")
                else:
                    _log(f"[{filename}] Ghostscript produced empty or missing file", "error")
            except subprocess.TimeoutExpired:
                _log(f"[{filename}] [WARN] Ghostscript timeout for {filename}, using fallback preview", "warn")
            except subprocess.CalledProcessError as e:
                _log(f"[{filename}] Ghostscript error. Fallback triggered.", "warn")
                
        # ExifTool Fallback
        _log(f"[{filename}] Format: {ext.upper()}. Using ExifTool fallback...", "info")
        exiftool_path = processor.get_tool_path("exiftool")
        if exiftool_path == "exiftool":
            import glob
            candidates = glob.glob(os.path.join(processor.get_base_path(), "tools", "exiftool*", "**", "exiftool*.exe"), recursive=True)
            if candidates:
                exiftool_path = candidates[0]
                
        cmd_fallback = [
            exiftool_path,
            "-b",
            "-PreviewImage",
            file_path,
        ]
        try:
            res = subprocess.run(cmd_fallback, check=True, capture_output=True, timeout=15)
            if res.stdout and len(res.stdout) > 1024:
                with open(out_path, "wb") as f:
                    f.write(res.stdout)
                try:
                    with Image.open(out_path) as verify_img:
                        verify_img.verify()
                    _log(f"[{filename}] Preview extracted successfully via ExifTool.", "success")
                    return out_path
                except (OSError, ValueError) as e:
                    _log(f"[{filename}] ExifTool produced invalid image: {e}", "error")
            else:
                _log(f"[{filename}] ExifTool produced empty or missing preview.", "error")
        except subprocess.TimeoutExpired:
            _log(f"[{filename}] ExifTool timeout.", "warn")
        except subprocess.CalledProcessError as e:
            _log(f"[{filename}] ExifTool error.", "warn")
            
        log_failed_file(
            os.path.dirname(file_path), os.path.basename(file_path), "All vector rendering methods failed"
        )
        return None
    elif ext in ["mp4", "mov", "avi", "mkv"]:
        _log(f"[{filename}] Format: Video. Extracting frame using FFmpeg...", "info")
        ffmpeg_path = processor.get_tool_path("ffmpeg")
        cmd = [
            ffmpeg_path,
            "-y",
            "-i",
            file_path,
            "-ss",
            "00:00:01",
            "-vframes",
            "1",
            out_path,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            # Validate output
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                try:
                    with Image.open(out_path) as verify_img:
                        verify_img.verify()
                    _log(f"[{filename}] Frame extracted successfully.", "success")
                    return out_path
                except (OSError, ValueError) as e:
                    err = f"FFmpeg produced invalid image: {e}"
                    _log(f"[{filename}] {err}", "error")
                    log_failed_file(
                        os.path.dirname(file_path), os.path.basename(file_path), err
                    )
            else:
                err = "FFmpeg produced empty or missing file"
                _log(f"[{filename}] {err}", "error")
                log_failed_file(
                    os.path.dirname(file_path), os.path.basename(file_path), err
                )
            return None
        except subprocess.CalledProcessError as e:
            err = f"FFmpeg error: {e.stderr}"
            _log(f"[{filename}] {err}", "error")
            log_failed_file(
                os.path.dirname(file_path), os.path.basename(file_path), err
            )
            return None
    elif ext == "svg":
        _log(f"[{filename}] Format: SVG. Extracting preview...", "info")
        edge_path = get_msedge_path()
        if edge_path:
            png_path = out_path.replace(".jpg", ".png")
            cmd = [
                edge_path,
                "--headless",
                "--disable-gpu",
                f"--screenshot={png_path}",
                "--window-size=1024,1024",
                f"file:///{os.path.abspath(file_path)}",
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                if os.path.exists(png_path):
                    img = Image.open(png_path).convert("RGB")
                    img.thumbnail((1024, 1024))
                    img.save(out_path, "JPEG")
                    os.remove(png_path)
                    _log(f"[{filename}] Preview extracted (Edge).", "success")
                    return out_path
            except (OSError, ValueError) as e:
                err = f"Edge SVG extract error: {e}"
                _log(f"[{filename}] {err}", "warn")
                log_failed_file(
                    os.path.dirname(file_path), os.path.basename(file_path), err
                )

        # Fallback 1: svglib
        try:
            from reportlab.graphics import renderPM
            from svglib.svglib import svg2rlg

            drawing = svg2rlg(file_path)
            if drawing:
                png_path = out_path.replace(".jpg", ".png")
                renderPM.drawToFile(drawing, png_path, fmt="PNG")
                img = Image.open(png_path).convert("RGB")
                img.thumbnail((1024, 1024))
                img.save(out_path, "JPEG")
                os.remove(png_path)
                _log(f"[{filename}] Preview extracted (svglib).", "success")
                return out_path
        except (OSError, ValueError) as e:
            err = f"svglib extract error: {e}"
            _log(f"[{filename}] {err}", "error")
            log_failed_file(
                os.path.dirname(file_path), os.path.basename(file_path), err
            )

        # Fallback 2: Raw text inspection wrapper for LLM
        _log(f"[{filename}] No rasterizer found. Using raw SVG text fallback.", "warn")
        return file_path
    return None
