import unittest
from unittest.mock import patch, MagicMock, mock_open
import tempfile
from PIL import Image

import packages.shared_utils.tools_setup as ts
from packages.shared_utils.csv_exporter import upsert_metadata_csv
from packages.shared_utils.cost_tracker import CostTracker
from backend.processors.media_converter import _safe_rgb_convert
from packages.shared_utils.filter import PLATFORM_RULES


class TestPatch2026(unittest.TestCase):
    
    @patch('packages.shared_utils.tools_setup._download')
    @patch('packages.shared_utils.tools_setup._is_valid_zip', return_value=True)
    @patch('packages.shared_utils.tools_setup.zipfile.ZipFile')
    def test_zip_slip_prevention(self, mock_zip, mock_is_valid, mock_download):
        mock_zf = MagicMock()
        # Simulate a path traversal attempt
        mock_zf.namelist.return_value = ['../malicious.exe']
        mock_zip.return_value.__enter__.return_value = mock_zf
        
        caught_errors = []
        def progress_callback(msg):
            if "Path traversal attempt detected" in msg:
                caught_errors.append(msg)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Force discovery to fail so it attempts download
            with patch('packages.shared_utils.tools_setup.discover_tools', 
                       return_value={'exiftool': None, 'ghostscript': 'gs', 'ffmpeg': 'ffmpeg'}), \
                 patch('packages.shared_utils.tools_setup.find_ghostscript_binary', return_value='gs'):
                
                ts.ensure_tools_installed(tools_dir=tmpdir, progress_callback=progress_callback)
        
        self.assertTrue(any("../malicious.exe" in e for e in caught_errors))
        mock_zf.extract.assert_not_called()

    @patch('builtins.open', new_callable=mock_open)
    @patch('packages.shared_utils.csv_exporter._csv_lock')
    def test_csv_exporter_lock(self, mock_lock, mock_file):
        upsert_metadata_csv("dummy.csv", "test.jpg", "Test", "Test", ["test"])
        mock_lock.__enter__.assert_called()

    def test_cost_tracker_lock(self):
        tracker = CostTracker()
        tracker._lock = MagicMock()
        tracker._add("openai", "gpt-4o", 10, 10)
        tracker._lock.__enter__.assert_called()

    def test_encode_image_white_background(self):
        img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        res = _safe_rgb_convert(img)
        self.assertEqual(res.mode, "RGB")
        self.assertEqual(res.getpixel((0, 0)), (255, 255, 255))

        # Also test LA (Luminance + Alpha)
        img_la = Image.new("LA", (10, 10), (0, 0))
        res_la = _safe_rgb_convert(img_la)
        self.assertEqual(res_la.mode, "RGB")
        self.assertEqual(res_la.getpixel((0, 0)), (255, 255, 255))

    def test_compliance_sync_limits(self):
        self.assertEqual(PLATFORM_RULES["Shutterstock"]["title_max_chars"], 2048)
        self.assertEqual(PLATFORM_RULES["Vecteezy"]["title_min_words"], 3)
        self.assertEqual(PLATFORM_RULES["Vecteezy"]["title_max_words"], 8)

if __name__ == '__main__':
    unittest.main()
