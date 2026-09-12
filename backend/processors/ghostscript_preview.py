"""Raster rendering of EPS/AI vector previews.

Uses Ghostscript for rasterization with a safety timeout, then falls back to
extracting the embedded ExifTool ``-PreviewImage``. All subprocess calls are
bounded so a malformed vector cannot hang the worker pool. Ghostscript stderr
is surfaced to the log on failure so rendering problems stay diagnosable.
"""

import glob
import os
import subprocess
from pathlib import Path

from PIL import Image

from backend.processors._tools import get_base_path, get_tool_path, log_failed_file
from packages.shared_utils.tools_setup import find_ghostscript_binary

RENDER_TIMEOUT = 15  # seconds


def render_vector_preview(file_path: str, out_path: str, _log) -> str | None:
    def log(msg, level="info"):
        if _log:
            _log(msg, level)
        else:
            print(f"[{level.upper()}] {msg}")

    filename = os.path.basename(file_path)
    ext = file_path.lower().split(".")[-1]
    gs_path = find_ghostscript_binary()
    if gs_path:
        log(
            f"[{filename}] Format: {ext.upper()}. Rendering raster preview using Ghostscript...",
            "info",
        )
        # Ghostscript renders into a temp PNG (EPS has no MediaBox, so the page
        # geometry must be forced via -dEPSFitPage); we then convert to the
        # requested JPEG out_path so the AI pipeline always sees a bitmap.
        png_preview = os.path.splitext(out_path)[0] + ".png"
        cmd = [
            gs_path,
            "-dSAFER",
            "-dBATCH",
            "-dNOPAUSE",
            "-dEPSFitPage",
            "-sDEVICE=png16m",
            "-r150",
            "-dTextAlphaBits=4",
            "-dGraphicsAlphaBits=4",
            f"-sOutputFile={png_preview}",
            str(Path(file_path).resolve()),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=RENDER_TIMEOUT)
            if result.returncode != 0:
                log(
                    f"[ERROR] Ghostscript STDERR: {result.stderr.decode('utf-8', errors='ignore')}",
                    "error",
                )
            elif os.path.exists(png_preview) and os.path.getsize(png_preview) > 1024:
                try:
                    with Image.open(png_preview) as verify_img:
                        verify_img.verify()
                    with Image.open(png_preview) as img:
                        img.convert("RGB").save(out_path, "JPEG")
                    os.remove(png_preview)
                    log(f"[{filename}] Preview rendered successfully.", "success")
                    return out_path
                except (OSError, ValueError) as e:
                    log(f"[{filename}] Ghostscript produced invalid image: {e}", "error")
            else:
                log(f"[{filename}] Ghostscript produced empty or missing file", "error")
        except subprocess.TimeoutExpired:
            log(
                f"[{filename}] [WARN] Ghostscript timeout for {filename}, using fallback preview",
                "warn",
            )
        except OSError as e:
            log(f"[{filename}] Ghostscript error: {e}", "error")

    # ExifTool Fallback (embedded -PreviewImage)
    log(f"[{filename}] Format: {ext.upper()}. Using ExifTool fallback...", "info")
    exiftool_path = get_tool_path("exiftool")
    if exiftool_path == "exiftool":
        candidates = glob.glob(
            os.path.join(get_base_path(), "tools", "exiftool*", "**", "exiftool*.exe"),
            recursive=True,
        )
        if candidates:
            exiftool_path = candidates[0]

    cmd_fallback = [
        exiftool_path,
        "-b",
        "-PreviewImage",
        str(Path(file_path).resolve()),
    ]
    try:
        res = subprocess.run(
            cmd_fallback, check=True, capture_output=True, timeout=RENDER_TIMEOUT
        )
        if res.stdout and len(res.stdout) > 1024:
            with open(out_path, "wb") as f:
                f.write(res.stdout)
            try:
                with Image.open(out_path) as verify_img:
                    verify_img.verify()
                log(f"[{filename}] Preview extracted successfully via ExifTool.", "success")
                return out_path
            except (OSError, ValueError) as e:
                log(f"[{filename}] ExifTool produced invalid image: {e}", "error")
        else:
            log(f"[{filename}] ExifTool produced empty or missing preview.", "error")
    except subprocess.TimeoutExpired:
        log(f"[{filename}] ExifTool timeout.", "warn")
    except subprocess.CalledProcessError as e:
        detail = e.stderr.decode("utf-8", errors="ignore") if e.stderr else str(e)
        log(f"[{filename}] ExifTool error: {detail}", "warn")
    except OSError as e:
        log(f"[{filename}] ExifTool unavailable: {e}", "warn")

    log_failed_file(
        os.path.dirname(file_path),
        os.path.basename(file_path),
        "All vector rendering methods failed",
    )
    return None