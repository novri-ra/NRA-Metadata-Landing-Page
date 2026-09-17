import unittest
from unittest.mock import patch, MagicMock
import sys

from packages.shared_utils.console_manager import toggle_console, is_console_visible

class TestConsoleManager(unittest.TestCase):
    def test_toggle_console_non_win32(self):
        with patch("sys.platform", "linux"):
            self.assertTrue(toggle_console(False))

    @patch("sys.platform", "win32")
    def test_toggle_console_win32_success(self):
        with patch("ctypes.WinDLL") as mock_windll:
            mock_kernel32 = MagicMock()
            mock_user32 = MagicMock()
            
            def windll_side_effect(name):
                if name == "kernel32": return mock_kernel32
                if name == "user32": return mock_user32
                return MagicMock()
                
            mock_windll.side_effect = windll_side_effect
            mock_kernel32.GetConsoleWindow.return_value = 12345
            
            # Hide
            self.assertTrue(toggle_console(False))
            mock_user32.ShowWindow.assert_called_with(12345, 0)
            self.assertFalse(is_console_visible())
            
            # Show
            self.assertTrue(toggle_console(True))
            mock_user32.ShowWindow.assert_called_with(12345, 5)
            self.assertTrue(is_console_visible())

    @patch("sys.platform", "win32")
    def test_toggle_console_win32_no_hwnd(self):
        with patch("ctypes.WinDLL") as mock_windll:
            mock_kernel32 = MagicMock()
            mock_windll.return_value = mock_kernel32
            mock_kernel32.GetConsoleWindow.return_value = 0
            
            self.assertFalse(toggle_console(False))
