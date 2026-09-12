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


def get_tool_path(tool_name: str) -> str:
    base = get_base_path()
    if sys.platform == "win32":
        candidates = {
            "exiftool": ["exiftool.exe"],
            "ghostscript": ["gswin64c.exe", "gswin32c.exe", "gs.exe"],
            "ffmpeg": ["ffmpeg.exe"],
        }.get(tool_name, [f"{tool_name}.exe"])
        tools_root = os.path.join(base, "tools")
        tool_subdir = os.path.join(tools_root, tool_name)
        if os.path.isdir(tool_subdir):
            for dirpath, _dirs, files in os.walk(tool_subdir):
                lower_files = [f.lower() for f in files]
                for exe_name in candidates:
                    if exe_name.lower() in lower_files:
                        idx = lower_files.index(exe_name.lower())
                        return os.path.join(dirpath, files[idx])
        for exe_name in candidates:
            flat = os.path.join(tools_root, exe_name)
            if os.path.exists(flat):
                return flat
        if getattr(sys, "frozen", False):
            for exe_name in candidates:
                meipass = os.path.join(sys._MEIPASS, "tools", exe_name)
                if os.path.exists(meipass):
                    return meipass
        from shutil import which

        found = which(tool_name)
        if not found:
            for exe_name in candidates:
                found = which(exe_name)
                if found:
                    break
        if found:
            return found
    return tool_name