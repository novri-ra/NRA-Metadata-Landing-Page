import os
import sys
import subprocess

def check_exiftool() -> tuple[bool, str]:
    """Check if ExifTool is available in system PATH or local tools dir."""
    local_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'exiftool', 'exiftool.exe'))
    
    if os.path.exists(local_path):
        return True, "Found in local tools directory"
        
    try:
        res = subprocess.run(["exiftool", "-ver"], capture_output=True, text=True)
        if res.returncode == 0:
            return True, f"Found in system PATH (v{res.stdout.strip()})"
    except Exception:
        pass
        
    return False, "ExifTool not found. Metadata writing will fail."

def check_msedge() -> tuple[bool, str]:
    """Check for Microsoft Edge installation required for headless SVG rendering."""
    if sys.platform != "win32":
        return False, "Not on Windows, Edge fallback unavailable."
        
    paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
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
