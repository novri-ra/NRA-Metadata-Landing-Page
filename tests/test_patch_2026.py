import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from PIL import Image

import packages.shared_utils.tools_setup as ts
from backend.processors.media_converter import _safe_rgb_convert
from packages.shared_utils.cost_tracker import CostTracker
from packages.shared_utils.csv_exporter import sanitize_text, upsert_metadata_csv
from packages.shared_utils.filter import PLATFORM_RULES
from scripts.setup_tools import setup_exiftool


class TestPatch2026(unittest.TestCase):
    
    @patch('scripts.setup_tools.download')
    @patch('scripts.setup_tools.check_zip', return_value=True)
    @patch('scripts.setup_tools.zipfile.ZipFile')
    def test_zip_slip_prevention(self, mock_zip, mock_check_zip, mock_download):
        mock_zf = MagicMock()
        # A traversal member plus a legit one; only the safe member may extract.
        mock_zf.namelist.return_value = ['../malicious.exe', 'exiftool(-k).exe']
        mock_zip.return_value.__enter__.return_value = mock_zf

        with tempfile.TemporaryDirectory() as tmpdir:
            setup_exiftool(Path(tmpdir))

        extracted = [call.args[0] for call in mock_zf.extract.call_args_list]
        self.assertNotIn('../malicious.exe', extracted)
        self.assertIn('exiftool(-k).exe', extracted)

    def test_csv_formula_injection_neutralized(self):
        for evil in ("=2+2", "+CMD", "-1e10", "@SUM(A1)"):
            self.assertTrue(sanitize_text(evil).startswith("'"))
        self.assertEqual(sanitize_text("ordinary title"), "ordinary title")

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
