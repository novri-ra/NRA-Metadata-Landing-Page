import os
import stat
import tempfile
import unittest
from pathlib import Path

from backend.processors import exiftool_client as ec
from backend.processors._tools import exiftool_flags


def _make_file(path: Path, content: bytes = b"ORIG") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


class PrepareTargetTest(unittest.TestCase):
    def test_clears_read_only_on_file_and_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sub" / "img.jpg"
            _make_file(target)
            os.chmod(target, stat.S_IREAD)
            os.chmod(target.parent, stat.S_IREAD)
            ec._prepare_target(str(target))
            self.assertTrue(os.access(target, os.W_OK))
            self.assertTrue(os.access(target.parent, os.W_OK))


class EssentialFlagsTest(unittest.TestCase):
    def test_exe_carries_in_place_overwrite_flag(self):
        self.assertEqual(
            exiftool_flags(r"C:\tools\exiftool.exe"),
            [
                "-api",
                "Windows=1",
                "-overwrite_original_in_place",
                "-m",
                "-charset",
                "filename=utf8",
            ],
        )

    def test_non_exe_skips_windows_api_only(self):
        self.assertEqual(
            exiftool_flags("exiftool"),
            ["-overwrite_original_in_place", "-m", "-charset", "filename=utf8"],
        )

    def test_sanitize_command_targets_in_place_overwrite(self):
        from unittest import mock

        captured = {}
        proc = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch("backend.processors.exiftool_client._run_exiftool") as run:
            run.return_value = proc
            ec.ExifToolClient().sanitize_ai_metadata("sub/dir/test_image.png")
            captured = run.call_args.args[0]
        joined = " ".join(captured)
        self.assertIn("-overwrite_original_in_place", joined)
        self.assertNotIn("-overwrite_original ", joined + " ")
        self.assertIn("\\test_image.png", captured[-1])


if __name__ == "__main__":
    unittest.main()