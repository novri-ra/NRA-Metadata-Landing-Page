import os
import subprocess
import sys
import tempfile
import threading
import urllib.request
import zipfile
from pathlib import Path

from backend.processors._tools import no_window_kwargs
from backend.processors.system_detector import discover_tools, reset_tool_cache


def get_tools_directory() -> Path:
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parent.parent.parent
    tools_dir = base_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    return tools_dir


def find_ghostscript_binary(tools_dir=None):
    if sys.platform != "win32":
        return "gs"

    from backend.processors.system_detector import detect_ghostscript

    return detect_ghostscript(silent=True, tools_dir=Path(tools_dir) if tools_dir else None)





_VERIFY_ARGS = {
    "exiftool": ["-ver"],
    "ghostscript": ["--version"],
    "ffmpeg": ["-version"],
}
_VERIFY_LABELS = {
    "exiftool": "ExifTool",
    "ghostscript": "Ghostscript",
    "ffmpeg": "FFmpeg",
}


def _verify_binary(exe_path: str, tool: str) -> tuple[bool, str]:
    """Quick execution probe (<=2s, no window). Returns (ok, version_text)."""
    if not exe_path or not os.path.isfile(exe_path):
        return False, ""
    args = [exe_path] + _VERIFY_ARGS.get(tool, ["--version"])
    try:
        res = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
            **no_window_kwargs(),
        )
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return False, ""
    if res.returncode != 0:
        return False, ""
    out = (res.stdout or "").strip().splitlines()
    return True, (out[0] if out else "v?")





def ensure_tools_installed(tools_dir=None, progress_callback=None):
    td = Path(tools_dir) if tools_dir else get_tools_directory()
    td.mkdir(parents=True, exist_ok=True)

    def _log(msg):
        if progress_callback:
            progress_callback(msg)
        else:
            print(msg)

    found = discover_tools(log=_log)

    if sys.platform != "win32":
        _log("[INFO] Non-Windows platform - detection complete.")
        return

    def _verified(exe: str | None, tool: str):
        ok, ver = _verify_binary(exe or "", tool)
        if ok:
            _log(
                f"[INFO] {_VERIFY_LABELS[tool]} detected at: {exe} "
                f"({ver})"
            )
        else:
            _log(
                f"[WARN] {_VERIFY_LABELS[tool]} found at {exe} but failed "
                f"execution probe."
            )
        return ok

    ready = {
        tool: (found.get(tool) is not None) and _verified(found[tool], tool)
        for tool in ("exiftool", "ghostscript", "ffmpeg")
    }

    def _setup_ghostscript():
        gs_path = find_ghostscript_binary(td)
        if gs_path:
            _log(f"[SUCCESS] Ghostscript found at: {gs_path}")
            return
            
        _log("[INFO] Downloading Ghostscript...")
        installer = td / "gs_installer.exe"
        try:
            url = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10080/gs10080w64.exe"
            installer = td / "gs_installer.exe"
            _download(url, str(installer))
            _log("[INFO] Installing Ghostscript silently...")
            
            target_dir = str((td / "ghostscript").resolve())
            cmd = [str(installer), "/S", f"/D={target_dir}"]
            
            env = os.environ.copy()
            env["__COMPAT_LAYER"] = "RunAsInvoker"
            
            result = subprocess.run(
                cmd,
                check=False,
                timeout=120,
                env=env,
                **no_window_kwargs(),
            )
            
            if installer.exists():
                os.remove(str(installer))
            
            if result.returncode != 0:
                _log(f"[WARN] Ghostscript installer exited with code {result.returncode}.")
            
            gs_path_new = find_ghostscript_binary(td)
            if gs_path_new:
                _log(f"[SUCCESS] Ghostscript installed and verified at {gs_path_new}")
            else:
                _log("[WARN] Ghostscript installer ran but gswin64c.exe not found. Install manually or add to PATH.")
        except Exception as e:  # noqa: BLE001
            if installer.exists():
                os.remove(str(installer))
            _log(f"[WARN] Failed to download/install Ghostscript: {e}. Vector preview will use system PATH fallback.")

    threads = []
    if not ready["ghostscript"]:
        threads.append(threading.Thread(target=_setup_ghostscript, daemon=True))
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    reset_tool_cache()
