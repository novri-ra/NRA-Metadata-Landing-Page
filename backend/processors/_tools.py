"""Private helpers shared by the processors package: tool resolution and
failed-file logging. Kept as an internal module (underscore prefix) so the
public surface of ``backend.processors`` stays clean.
"""

import os
import sys
import threading
from datetime import UTC, datetime

_fail_log_lock = threading.Lock()


def log_failed_file(working_dir: str, filename: str, reason: str):
    with _fail_log_lock:
        log_path = os.path.join(working_dir, "failed_files.log")
        ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {filename}: {reason}\n")


def get_base_path() -> str:
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def get_tool_path(tool_name: str) -> str | None:
    """Resolve an external tool, delegating to the centralized discovery.

    Detection reuses the startup cache so workers do not rescan the filesystem
    on every media operation; a final ``shutil.which`` fallback covers tools
    added to PATH after startup. Returns ``None`` when nothing was found --
    never the bare command name -- so callers fail loudly instead of silently
    launching whatever the shell happens to resolve.
    """
    from backend.processors.system_detector import get_detected_tool_path

    found = get_detected_tool_path(tool_name)
    if found:
        return found
    from shutil import which

    candidates = {
        "exiftool": ["exiftool.exe"],
        "ghostscript": ["gswin64c.exe", "gswin32c.exe", "gs.exe"],
        "ffmpeg": ["ffmpeg.exe"],
    }.get(tool_name, [f"{tool_name}.exe"])
    for exe_name in candidates:
        for candidate in (exe_name, os.path.splitext(exe_name)[0]):
            found = which(candidate)
            if found:
                return found
    return None


def exiftool_flags(exiftool_path: str) -> list:
    """Essential flags for every ExifTool subprocess call.

    Applies the Windows API mode (wide-char/long-path I/O) on the bundled .exe
    build, in-place overwrite, tolerance of minor errors (``-m``), and UTF-8
    filenames. ``-api Windows=1`` was validated against the bundled 13.26
    binary; the old ``WindowsLongPath`` alias is the deprecated spelling.
    """
    flags = ["-overwrite_original_in_place", "-m", "-charset", "filename=utf8"]
    if str(exiftool_path).lower().endswith(".exe"):
        return ["-api", "Windows=1"] + flags
    return flags