"""Raster rendering of EPS/AI vector previews.

Uses Ghostscript for rasterization with a safety timeout, then falls back to
extracting the embedded ExifTool ``-PreviewImage``. All subprocess calls are
bounded so a malformed vector cannot hang the worker pool.
"""

import glob
import os
import subprocess

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
            subprocess.run(cmd, check=True, capture_output=True, timeout=RENDER_TIMEOUT)
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                try:
                    with Image.open(out_path) as verify_img:
                        verify_img.verify()
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
        except subprocess.CalledProcessError as e:
            log(f"[{filename}] Ghostscript error. Fallback triggered.", "warn")

    # ExifTool Fallback
    log(f"[{filename}] Format: {ext.upper()}. Using ExifTool fallback...", "info")
    exiftool_path = get_tool_path("exiftool")
    if exiftool_path == "exiftool":
        candidates = glob.glob(
            os.path.join(get_base_path(), "tools", "exiftool*", "**", "exiftool*.exe"),
            recursive=True,
        )
        if candidates:
            exiftool_path = candidates[0]

    cmd_fallback = [exiftool_path, "-b", "-PreviewImage", file_path]
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
        log(f"[{filename}] ExifTool error.", "warn")

    log_failed_file(
        os.path.dirname(file_path),
        os.path.basename(file_path),
        "All vector rendering methods failed",
    )
    return None