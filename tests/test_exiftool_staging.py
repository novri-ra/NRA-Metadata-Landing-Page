import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

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

    def test_removes_stale_tmp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "img.jpg"
            _make_file(target)
            stale = Path(str(target) + "_exiftool_tmp")
            stale.write_bytes(b"stale")
            os.chmod(stale, stat.S_IREAD)
            ec._prepare_target(str(target))
            self.assertFalse(stale.exists())


class EssentialFlagsTest(unittest.TestCase):
    def test_exe_carries_essential_windows_flags(self):
        self.assertEqual(
            exiftool_flags(r"C:\tools\exiftool.exe"),
            [
                "-api",
                "Windows=1",
                "-overwrite_original",
                "-m",
                "-charset",
                "filename=utf8",
            ],
        )

    def test_non_exe_skips_windows_api_only(self):
        self.assertEqual(
            exiftool_flags("exiftool"),
            ["-overwrite_original", "-m", "-charset", "filename=utf8"],
        )


class StageCopyTest(unittest.TestCase):
    def test_keeps_original_extension(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as root:
            target = Path(tmp) / "IMG_01.EPS"
            _make_file(target)
            orig_root = ec._staging_root
            ec._staging_root = lambda: root
            try:
                staged = ec._stage_copy(str(target))
                self.assertIsNotNone(staged)
                self.assertTrue(staged.endswith(".EPS"))
                self.assertTrue(Path(staged).is_file())
            finally:
                ec._staging_root = orig_root


class StagingFallbackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name)
        self.calls: list[list] = []

    def tearDown(self):
        self.tmp.cleanup()

    def _fake_run(self, cmd, timeout):
        self.calls.append(cmd)
        target = cmd[-1]
        if str(Path(target)).startswith(str(Path(self.tmp.name) / "staging")):
            with open(target, "a", encoding="utf-8") as f:
                f.write("TAG")
            return SimpleNamespace(returncode=0, stdout="ok", stderr="")
        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr=f"Error creating file: {target}_exiftool_tmp - {target}",
        )

    def test_fallback_stages_and_moves_back_on_temp_failure(self):
        orig_run = ec._run_exiftool
        orig_root = ec._staging_root
        staging = Path(self.tmp.name) / "staging"
        staging.mkdir()
        ec._run_exiftool = self._fake_run
        ec._staging_root = lambda: str(staging)
        try:
            target = self.work / "img.jpg"
            _make_file(target)
            result = ec._run_with_staging_fallback(
                str(target), ["exiftool", "-Title=x", str(target)], timeout=10
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(len(self.calls), 2)
            self.assertNotEqual(self.calls[0][-1], self.calls[1][-1])
            self.assertEqual(
                Path(target).read_text(encoding="utf-8"), "ORIGTAG"
            )
        finally:
            ec._run_exiftool = orig_run
            ec._staging_root = orig_root

    def test_non_temp_failure_does_not_trigger_fallback(self):
        orig_run = ec._run_exiftool
        orig_root = ec._staging_root
        staging = Path(self.tmp.name) / "staging2"
        staging.mkdir()
        ec._run_exiftool = lambda cmd, timeout: SimpleNamespace(
            returncode=2, stdout="", stderr="Corrupt image data"
        )
        ec._staging_root = lambda: str(staging)
        try:
            target = self.work / "img.jpg"
            _make_file(target)
            result = ec._run_with_staging_fallback(
                str(target), ["exiftool", str(target)], timeout=10
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(len(self.calls), 0)
            self.assertEqual(Path(target).read_text(), "ORIG")
        finally:
            ec._run_exiftool = orig_run
            ec._staging_root = orig_root


if __name__ == "__main__":
    unittest.main()