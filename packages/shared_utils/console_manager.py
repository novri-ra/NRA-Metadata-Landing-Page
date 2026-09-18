import ctypes
import sys

# Windows console visibility flags
SW_HIDE = 0
SW_SHOW = 5

_console_visible = True

def toggle_console(visible: bool) -> bool:
    """
    Shows or hides the native Windows console window.
    Returns True if successfully changed or not on Windows.
    """
    global _console_visible
    if sys.platform != "win32":
        return True

    try:
        kernel32 = ctypes.WinDLL('kernel32')
        user32 = ctypes.WinDLL('user32')
        hwnd = kernel32.GetConsoleWindow()
        
        if hwnd:
            user32.ShowWindow(hwnd, SW_SHOW if visible else SW_HIDE)
            _console_visible = visible
            return True
        return False
    except Exception:  # noqa: BLE001
        return False

def is_console_visible() -> bool:
    return _console_visible
