"""Media conversion and preview dispatch for the worker pool.

Distinct format families:

- Raster images           -> resized JPEG preview (``raster_to_preview``)
- EPS/AI vectors          -> ``backend.processors.ghostscript_preview``
- Video files             -> FFmpeg frame extraction (``extract_video_frame``)
- SVG                     -> Edge / svglib rasterization, raw text fallback

The dispatcher no longer requires a processor/embedder instance; it resolves
tools internally so callers get a plain ``str | None`` preview path.
"""

import os
import subprocess
import tempfile

from PIL import Image


def _safe_rgb_convert(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        canvas = Image.new("RGBA", img.size, (255, 255, 255, 255))
        canvas.paste(img, mask=img.convert("RGBA").split()[-1])
        return canvas.convert("RGB")
    return img.convert("RGB")

from backend.processors._tools import (
    format_tool_failure,
    get_tool_path,
    log_failed_file,
    no_window_kwargs,
)
from backend.processors.ghostscript_preview import render_vector_preview


def get_msedge_path():
    paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def raster_to_preview(file_path: str, out_path: str, filename: str, _log) -> str | None:
    try:
        img = _safe_rgb_convert(Image.open(file_path))
        img.thumbnail((1024, 1024))
        img.save(out_path, "JPEG")
        _log(f"[{filename}] Image preview generated.", "success")
        return out_path
    except (OSError, ValueError) as e:
        err = f"Image preview generation failed: {e}"
        _log(f"[{filename}] {err}", "error")
        log_failed_file(os.path.dirname(file_path), filename, err)
        return None


def extract_video_frame(file_path: str, out_path: str, filename: str, _log) -> str | None:
    _log(f"[{filename}] Format: Video. Extracting frame using FFmpeg...", "info")
    ffmpeg_path = get_tool_path("ffmpeg")
    if not ffmpeg_path:
        err = "FFmpeg tidak ditemukan (jalankan setup_tools)"
        _log(f"[{filename}] {err}", "error")
        log_failed_file(os.path.dirname(file_path), filename, err)
        return None
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
        subprocess.run(cmd, check=True, capture_output=True, timeout=60, **no_window_kwargs())
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
                log_failed_file(os.path.dirname(file_path), os.path.basename(file_path), err)
        else:
            err = "FFmpeg produced empty or missing file"
            _log(f"[{filename}] {err}", "error")
            log_failed_file(os.path.dirname(file_path), os.path.basename(file_path), err)
        return None
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or b"").decode("utf-8", errors="replace")
        _log(
            format_tool_failure(
                "[FFMPEG FAILURE]",
                [
                    ("File", os.path.basename(file_path)),
                    ("ExitCode", str(e.returncode)),
                    ("Error", detail.strip()),
                ],
            ),
            "error",
        )
        log_failed_file(
            os.path.dirname(file_path),
            os.path.basename(file_path),
            f"FFmpeg error: {detail[:200]}",
        )
        return None
    except subprocess.TimeoutExpired:
        err = "FFmpeg timed out"
        _log(f"[{filename}] {err}", "error")
        log_failed_file(os.path.dirname(file_path), os.path.basename(file_path), err)
        return None
    except (OSError, ValueError) as e:
        err = f"FFmpeg error: {e}"
        _log(f"[{filename}] {err}", "error")
        log_failed_file(os.path.dirname(file_path), os.path.basename(file_path), err)
        return None


def extract_svg_preview(file_path: str, out_path: str, filename: str, _log) -> str | None:
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
            subprocess.run(cmd, check=True, capture_output=True, timeout=30, **no_window_kwargs())
            if os.path.exists(png_path):
                img = _safe_rgb_convert(Image.open(png_path))
                img.thumbnail((1024, 1024))
                img.save(out_path, "JPEG")
                _log(f"[{filename}] Preview extracted (Edge).", "success")
                return out_path
        except (OSError, ValueError, subprocess.TimeoutExpired) as e:
            err = f"Edge SVG extract error: {e}"
            _log(f"[{filename}] {err}", "warn")
            log_failed_file(os.path.dirname(file_path), os.path.basename(file_path), err)
        finally:
            if os.path.exists(png_path):
                try:
                    os.remove(png_path)
                except OSError:
                    pass

    # Fallback 1: svglib
    png_path = ""
    try:
        from reportlab.graphics import renderPM
        from svglib.svglib import svg2rlg

        drawing = svg2rlg(file_path)
        if drawing:
            png_path = out_path.replace(".jpg", ".png")
            renderPM.drawToFile(drawing, png_path, fmt="PNG")
            img = _safe_rgb_convert(Image.open(png_path))
            img.thumbnail((1024, 1024))
            img.save(out_path, "JPEG")
            _log(f"[{filename}] Preview extracted (svglib).", "success")
            return out_path
    except (OSError, ValueError) as e:
        err = f"svglib extract error: {e}"
        _log(f"[{filename}] {err}", "error")
        log_failed_file(os.path.dirname(file_path), os.path.basename(file_path), err)
    finally:
        if png_path and os.path.exists(png_path):
            try:
                os.remove(png_path)
            except OSError:
                pass

    # Fallback 2: Raw text inspection wrapper for LLM
    _log(f"[{filename}] No rasterizer found. Using raw SVG text fallback.", "warn")
    return file_path


def extract_preview_image(file_path: str, progress_callback=None) -> str | None:
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
        return raster_to_preview(file_path, out_path, filename, _log)
    elif ext in ["eps", "ai"]:
        return render_vector_preview(file_path, out_path, _log)
    elif ext in ["mp4", "mov", "avi", "mkv"]:
        return extract_video_frame(file_path, out_path, filename, _log)
    elif ext == "svg":
        _log(f"[{filename}] Format: SVG. Extracting preview...", "info")
        return extract_svg_preview(file_path, out_path, filename, _log)
    return None