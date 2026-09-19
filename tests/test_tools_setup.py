import os
import tempfile
import unittest
from unittest import mock

from packages.shared_utils import tools_setup as ts





class SkipWhenDetectedTest(unittest.TestCase):
    def test_download_not_called_when_tools_present(self):
        # A detected + verified binary must skip warning entirely.
        with tempfile.TemporaryDirectory() as tmp:
            for rel in ("exiftool.exe", "gswin64c.exe", "ffmpeg.exe"):
                open(os.path.join(tmp, rel), "wb").close()
            logs = []

            with mock.patch(
                "packages.shared_utils.tools_setup.discover_tools",
                return_value={
                    "exiftool": os.path.join(tmp, "exiftool.exe"),
                    "ghostscript": os.path.join(tmp, "gswin64c.exe"),
                    "ffmpeg": os.path.join(tmp, "ffmpeg.exe"),
                },
            ), mock.patch.object(
                ts, "_verify_binary", side_effect=lambda p, t: (True, "test-v")
            ):
                ts.ensure_tools_installed(tmp, progress_callback=logs.append)
            
            self.assertEqual(len(logs), 3)
            self.assertTrue(all("detected at:" in m for m in logs))


if __name__ == "__main__":
    unittest.main()