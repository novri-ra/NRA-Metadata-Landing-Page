import os
import subprocess
import sys

from backend.processors._tools import no_window_kwargs


def check_exiftool() -> tuple[bool, str]:
    """Check if ExifTool is available in system PATH or local tools dir."""
    try:
        from backend.processors.system_detector import detect_exiftool

        path = detect_exiftool(silent=True)
    except Exception:  # pragma: no cover - import guard for exotic layouts
        path = None
    if path:
        return True, f"Found at {path}"

    try:
        cmd = ["exiftool", "-ver"]
        cwd = None
        try:
            from shutil import which

            found = which("exiftool.exe") or which("exiftool")
            if found:
                cmd = [found, "-ver"]
                cwd = os.path.dirname(os.path.abspath(found))
        except Exception:  # pragma: no cover - which() quirks
            pass
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
            cwd=cwd,
            **no_window_kwargs(),
        )
        if res.returncode == 0:
            return True, f"Found in system PATH (v{res.stdout.strip()})"
    except (OSError, subprocess.TimeoutExpired):
        pass

    return False, "ExifTool not found. Metadata writing will fail."


def check_msedge() -> tuple[bool, str]:
    """Check for Microsoft Edge installation required for headless SVG rendering."""
    if sys.platform != "win32":
        return False, "Not on Windows, Edge fallback unavailable."

    paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]

    for p in paths:
        if os.path.exists(p):
            return True, f"Found at {p}"

    return False, "Microsoft Edge not found. SVG preview extraction may fail."


def run_environment_checks() -> list[tuple[str, bool, str]]:
    """Run all environment checks and return results."""
    results = []

    # 1. ExifTool
    ok, msg = check_exiftool()
    results.append(("ExifTool", ok, msg))

    # 2. Microsoft Edge
    ok, msg = check_msedge()
    results.append(("Microsoft Edge", ok, msg))

    return results
