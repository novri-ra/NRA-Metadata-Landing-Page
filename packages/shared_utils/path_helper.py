import os
import sys

def get_app_dir() -> str:
    """Get the application directory, supporting both frozen executable and dev mode."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_bundled_resource(relative_path: str) -> str:
    """Resolve resources, checking PyInstaller _MEIPASS bundle first, then app dir."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled = os.path.join(sys._MEIPASS, relative_path)
        if os.path.exists(bundled):
            return bundled
    return os.path.join(get_app_dir(), relative_path)
