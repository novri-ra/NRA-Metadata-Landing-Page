import os
import tempfile
import unittest
from pathlib import Path

from backend.processors import system_detector
from backend.processors.system_detector import (
    detect_exiftool,
    detect_ffmpeg,
    detect_ghostscript,
    detect_gtk3,
    discover_tools,
    reset_tool_cache,
)


def _make_tree(root: Path, files: dict[str, bytes | str]):
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content)


class ToolDiscoveryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tools_dir = Path(self.tmp.name) / "tools"
        self.logs: list[str] = []

    def tearDown(self):
        reset_tool_cache()
        self.tmp.cleanup()

    def _log(self, msg):
        self.logs.append(msg)

    def test_exiftool_nested_subfolder_detected(self):
        _make_tree(
            self.tools_dir,
            {"exiftool/exiftool.exe": b"MZ"},
        )
        path = detect_exiftool(log=self._log, tools_dir=self.tools_dir)
        self.assertTrue(path.endswith("exiftool.exe"))
        self.assertTrue(any("[SUCCESS] ExifTool found at:" in m for m in self.logs))

    def test_exiftool_missing_emits_error(self):
        path = detect_exiftool(log=self._log, tools_dir=self.tools_dir)
        self.assertIsNone(path)
        self.assertTrue(
            any("[ERROR] ExifTool TIDAK ditemukan" in m for m in self.logs)
        )

    def test_ghostscript_nested_bin_detected(self):
        _make_tree(
            self.tools_dir,
            {"ghostscript/bin/gswin64c.exe": b"MZ"},
        )
        path = detect_ghostscript(log=self._log, tools_dir=self.tools_dir)
        self.assertTrue(path.endswith("gswin64c.exe"))
        self.assertTrue(any("[SUCCESS] Ghostscript found at:" in m for m in self.logs))

    def test_ghostscript_prefers_shallow_path(self):
        _make_tree(
            self.tools_dir,
            {
                "ghostscript/bin/gswin64c.exe": b"MZ",
                "gswin64c.exe": b"MZ",
            },
        )
        path = detect_ghostscript(log=self._log, tools_dir=self.tools_dir)
        self.assertEqual(path, str(self.tools_dir / "gswin64c.exe"))

    def test_ffmpeg_nested_bin_detected(self):
        _make_tree(
            self.tools_dir,
            {"ffmpeg/bin/ffmpeg.exe": b"MZ"},
        )
        path = detect_ffmpeg(log=self._log, tools_dir=self.tools_dir)
        self.assertTrue(path.endswith("ffmpeg.exe"))
        self.assertTrue(any("[SUCCESS] FFmpeg found at:" in m for m in self.logs))

    def test_ffmpeg_missing_is_warn_not_error(self):
        path = detect_ffmpeg(log=self._log, tools_dir=self.tools_dir)
        self.assertIsNone(path)
        self.assertTrue(any("[WARN] FFmpeg tidak ditemukan" in m for m in self.logs))

    def test_gtk3_adds_bin_dir_to_path(self):
        _make_tree(
            self.tools_dir,
            {"gtk3/bin/libgtk-3-0.dll": b"MZ"},
        )
        original_path = os.environ.get("PATH", "")
        try:
            bin_dir = detect_gtk3(log=self._log, tools_dir=self.tools_dir)
            self.assertIsNotNone(bin_dir)
            self.assertTrue(bin_dir.endswith("gtk3" + os.sep + "bin"))
            self.assertIn(bin_dir, os.environ["PATH"].split(os.pathsep))
            self.assertTrue(any("[SUCCESS] GTK3 Runtime detected" in m for m in self.logs))
        finally:
            os.environ["PATH"] = original_path

    def test_gtk3_missing_warns(self):
        detect_gtk3(log=self._log, tools_dir=self.tools_dir)
        self.assertTrue(any("[WARN] GTK3 Runtime tidak terdeteksi" in m for m in self.logs))

    def test_discover_tools_schema_and_logging(self):
        reset_tool_cache()
        result = discover_tools(log=self._log)
        self.assertEqual(set(result), {"exiftool", "ghostscript", "ffmpeg", "gtk3"})
        for key, value in result.items():
            self.assertTrue(value is None or isinstance(value, str))
        self.assertTrue(self.logs)
        reset_tool_cache()

    def test_exiftool_detected_in_repo_tools(self):
        reset_tool_cache()
        base = Path(system_detector._base_dir())
        repo_exe = base / "tools" / "exiftool" / "exiftool.exe"
        if not repo_exe.exists():
            self.skipTest("repo tools/exiftool/exiftool.exe not present")
        path = detect_exiftool()
        self.assertEqual(path, str(repo_exe))
        reset_tool_cache()


if __name__ == "__main__":
    unittest.main()