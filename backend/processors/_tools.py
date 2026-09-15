"""Private helpers shared by the processors package: tool resolution and
failed-file logging. Kept as an internal module (underscore prefix) so the
public surface of ``backend.processors`` stays clean.
"""

import os
import subprocess
import sys
import textwrap
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
        "exiftool": ["exiftool.exe", "ExifTool.exe"],
        "ghostscript": ["gswin64c.exe", "gswin32c.exe", "gs.exe"],
        "ffmpeg": ["ffmpeg.exe"],
    }.get(tool_name, [f"{tool_name}.exe"])
    for exe_name in candidates:
        for candidate in (exe_name, os.path.splitext(exe_name)[0]):
            found = which(candidate)
            if found:
                return found
    return None


_UTF8_BOX = ("┌", "─", "┐", "│", "└", "┘")
_ASCII_BOX = ("+", "-", "+", "|", "+", "+")


def _box_glyphs() -> tuple[str, str, str, str, str, str]:
    """Unicode box-drawing when the stream can carry it, ASCII fallback so a
    redirected/piped stdout (e.g. cp1252) never crashes with UnicodeEncodeError."""
    enc = (getattr(sys.stdout, "encoding", "") or "").lower()
    return _UTF8_BOX if "utf" in enc or enc == "cp65001" else _ASCII_BOX


def format_tool_failure(
    title: str, rows: list[tuple[str, str]], width: int = 110
) -> str:
    """Render a structured, boxed failure block for an external tool.

    Long values (a full CLI command, verbose stderr) are word-wrapped instead
    of flooding the terminal horizontally. Width is advisory; a value longer
    than the box simply spills onto continuation lines.
    """
    tl, h, tr, v, bl, br = _box_glyphs()
    label_w = max((len(label) for label, _ in rows), default=1)
    value_w = max(20, width - 5 - label_w)
    pad = " " * (label_w + 2)
    top = f"{tl}{h} {title} " + h * max(1, width - 5 - len(title)) + tr
    bottom = bl + h * (width - 2) + br
    body = [top]
    for label, value in rows:
        chunks = textwrap.wrap(
            (value or "").replace("\r", "").rstrip(),
            width=value_w,
            break_long_words=True,
            break_on_hyphens=False,
        ) or [""]
        body.append(f"{v} {label:<{label_w}}: {chunks[0]}".ljust(width - 2) + v)
        for extra in chunks[1:]:
            body.append(f"{v} {pad}{extra}".ljust(width - 2) + v)
    body.append(bottom)
    return "\n".join(body)


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


def no_window_kwargs() -> dict:
    """Return subprocess kwargs that suppress conhost windows on Windows.

    Without these, every external tool spawns a visible console window
    (conhost.exe flicker) and stalls the Tk event loop, freezing the UI.
    On non-Windows platforms this is a no-op.
    """
    if os.name != "nt":
        return {}
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    return {"creationflags": subprocess.CREATE_NO_WINDOW, "startupinfo": si}