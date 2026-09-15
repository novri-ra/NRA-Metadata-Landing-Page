"""Centralized detection of external media tools.

Tools are expected to live under the project's ``tools/`` directory, but users
often drop binaries in arbitrary subfolders (``tools/exiftool/``,
``tools/ghostscript/bin/``, ``tools/ffmpeg/bin/``, ``tools/gtk3/``). This
module performs an exhaustive recursive scan of ``tools/`` and then falls back
to the system ``PATH`` plus well-known Windows install locations so no binary
is missed. The GTK3 runtime, when located, is appended to ``PATH`` at runtime
for WeasyPrint/GTK components.

Log contract: each detector emits exactly one message per tool with an explicit
``[SUCCESS]`` / ``[WARN]`` / ``[ERROR]`` prefix so startup output (console
terminal and UI log tab) stays self-explanatory.
"""

import glob
import os
import re
import sys
from pathlib import Path
from shutil import which

_CACHE: dict[str, str | None] | None = None

_GS_VER_RE = re.compile(r"[\\/]gs(\d+(?:[._]\d+)*)", re.IGNORECASE)


def _version_key(path: str) -> tuple[int, ...]:
    """Numeric version tuple of a tools glob path (``gs9.56`` -> ``(9, 56)``).

    Lexicographic sort mis-ranks multi-digit releases (``"gs10" < "gs9"`` as
    strings); a numeric tuple keeps the newest Ghostscript on top.
    """
    m = _GS_VER_RE.search(path)
    if not m:
        return ()
    return tuple(int(t) for t in re.split(r"[._]", m.group(1)))


def _emit(msg: str, log) -> None:
    if log:
        log(msg)
    else:
        print(msg)


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent.parent


def _tools_root() -> Path:
    return _base_dir() / "tools"


def _resolve_binary(
    exe_names: list[str],
    *,
    tools_dir: Path | None = None,
    extra_globs: tuple[str, ...] = (),
) -> str | None:
    """Return the first existing binary, preferring the shallowest ``tools/``
    match, then extra install locations (latest version first), then PATH."""
    lowered = {name.lower(): name for name in exe_names}
    root = tools_dir if tools_dir is not None else _tools_root()
    if root.is_dir():
        matches = [
            p
            for p in root.rglob("*.exe")
            if p.is_file() and p.name.lower() in lowered
        ]
        if matches:
            matches.sort(key=lambda p: len(p.parts))
            return str(matches[0])
    if extra_globs:
        hits: list[str] = []
        for pattern in extra_globs:
            hits.extend(glob.glob(pattern))
        if hits:
            hits.sort(key=_version_key, reverse=True)
            return hits[0]
    for name in exe_names:
        stem = Path(name).stem
        for candidate in (name, stem):
            found = which(candidate)
            if found:
                return found
    return None


def detect_exiftool(
    log=None,
    tools_dir: Path | None = None,
    silent: bool = False,
) -> str | None:
    """Locate ``exiftool.exe`` under ``tools/`` or on the system PATH."""
    path = _resolve_binary(["exiftool.exe", "ExifTool.exe"], tools_dir=tools_dir)
    if not silent:
        if path:
            _emit(f"[SUCCESS] ExifTool found at: {path}", log)
        else:
            _emit(
                "[ERROR] ExifTool TIDAK ditemukan! Letakkan exiftool.exe "
                "di folder tools/exiftool/",
                log,
            )
    return path


def detect_ghostscript(
    log=None,
    tools_dir: Path | None = None,
    silent: bool = False,
) -> str | None:
    """Locate a Ghostscript CLI (``gswin64c.exe`` / ``gswin32c.exe`` / ``gs``)."""
    names = ["gswin64c.exe", "gswin32c.exe", "gs.exe"]
    root = tools_dir if tools_dir is not None else _tools_root()
    extra_globs: tuple[str, ...] = ()
    if sys.platform == "win32":
        program_files = [
            os.environ.get("ProgramFiles", "C:\\Program Files"),
            os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
        ]
        extra_globs = tuple(
            os.path.join(pf, "gs", "gs*", "bin", "gswin*c.exe")
            for pf in program_files
            if pf
        )
    path = _resolve_binary(names, tools_dir=root, extra_globs=extra_globs)
    if not silent:
        if path:
            _emit(f"[SUCCESS] Ghostscript found at: {path}", log)
        else:
            _emit(
                "[ERROR] Ghostscript TIDAK ditemukan! Letakkan di "
                "tools/ghostscript/bin/gswin64c.exe",
                log,
            )
    return path


def detect_ffmpeg(
    log=None,
    tools_dir: Path | None = None,
    silent: bool = False,
) -> str | None:
    """Locate ``ffmpeg.exe`` under ``tools/`` or on the system PATH."""
    path = _resolve_binary(["ffmpeg.exe"], tools_dir=tools_dir)
    if not silent:
        if path:
            _emit(f"[SUCCESS] FFmpeg found at: {path}", log)
        else:
            _emit(
                "[WARN] FFmpeg tidak ditemukan (opsional untuk pemrosesan video/audio).",
                log,
            )
    return path


def _gtk_search_roots(tools_dir: Path | None) -> list[Path]:
    roots: list[Path] = []
    tr = tools_dir if tools_dir is not None else _tools_root()
    roots.append(tr)
    if tr.is_dir():
        roots.extend(sorted(tr.glob("gtk*")))
        runtime = tr / "runtime"
        if runtime.is_dir():
            roots.extend(sorted(runtime.glob("gtk*")))
    if sys.platform == "win32":
        program_files = os.environ.get("ProgramFiles")
        if program_files:
            roots.append(Path(program_files) / "GTK3-Runtime-Win64" / "bin")
    gtk_path = os.environ.get("GTK_PATH")
    if gtk_path:
        roots.append(Path(gtk_path))
        roots.append(Path(gtk_path) / "bin")
    return roots


def detect_gtk3(
    log=None,
    tools_dir: Path | None = None,
    silent: bool = False,
) -> str | None:
    """Locate ``libgtk-3-0.dll`` and add its bin folder to ``PATH``."""
    dll_name = "libgtk-3-0.dll"
    bin_dir = None
    for root in _gtk_search_roots(tools_dir):
        if not root.is_dir():
            continue
        for dll in root.rglob(dll_name):
            if dll.is_file():
                bin_dir = dll.parent
                break
        if bin_dir:
            break
    if bin_dir is None and sys.platform == "win32":
        for entry in os.environ.get("PATH", "").split(os.pathsep):
            if entry and (Path(entry) / dll_name).is_file():
                bin_dir = Path(entry)
                break
    if bin_dir is not None:
        bin_str = str(bin_dir)
        path_entries = os.environ.get("PATH", "").split(os.pathsep)
        norm_bins = {e.rstrip("\\/").lower() for e in path_entries}
        if bin_str.rstrip("\\/").lower() not in norm_bins:
            os.environ["PATH"] = bin_str + os.pathsep + os.environ.get("PATH", "")
        if not silent:
            _emit(f"[SUCCESS] GTK3 Runtime detected at: {bin_str}", log)
        return bin_str
    if not silent:
        _emit(
            "[WARN] GTK3 Runtime tidak terdeteksi di tools/ maupun sistem "
            "(diperlukan jika menggunakan komponen WeasyPrint/GTK).",
            log,
        )
    return None


def discover_tools(log=None) -> dict[str, str | None]:
    """Run all detectors once and cache the result.

    Returns ``{"exiftool": path, "ghostscript": path, "ffmpeg": path,
    "gtk3": path}`` where each value is ``None`` when the tool was not found.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    _CACHE = {
        "exiftool": detect_exiftool(log=log),
        "ghostscript": detect_ghostscript(log=log),
        "ffmpeg": detect_ffmpeg(log=log),
        "gtk3": detect_gtk3(log=log),
    }
    return _CACHE


def get_detected_tool_path(tool_name: str) -> str | None:
    """Return the cached path for an external tool, running discovery once.

    Runtime callers use this so detection is performed a single time during
    startup instead of on every media operation.
    """
    if _CACHE is None:
        discover_tools()
    return _CACHE.get(tool_name) if _CACHE else None


def reset_tool_cache() -> None:
    """Clear the discovery cache (used by tests and re-detection)."""
    global _CACHE
    _CACHE = None