import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps/desktop/src"))

from controllers import offline_retag_controller as ctrl


def _stub_app():
    class _Btn:
        def __init__(self):
            self.state = None

        def configure(self, **kw):
            self.state = kw.get("state")

    class _Processor:
        def __init__(self):
            self.calls = []

        def embed_metadata(self, *args):
            self.calls.append(args)
            return True

    class _Progress:
        def __init__(self):
            self.value = None

        def set(self, v):
            self.value = v

    log = []

    class _App:
        pass

    app = _App()
    app._btn = _Btn()
    app.retag_btn = _Btn()
    app.start_btn = _Btn()
    app.progress_bar = _Progress()
    app.processor = _Processor()
    app.log = lambda msg, level: log.append((level, msg))
    app._call_main = lambda fn, *args, **kw: fn(*args, **kw)
    app.log_lines = log
    return app


class FindAssetTest(unittest.TestCase):
    def test_finds_nested_file(self):
        tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(tmp, "sub"))
        with open(os.path.join(tmp, "sub", "a.jpg"), "w"):
            pass
        self.assertEqual(
            ctrl._find_asset(tmp, "a.jpg"), os.path.join(tmp, "sub", "a.jpg")
        )

    def test_missing_file_returns_none(self):
        tmp = tempfile.mkdtemp()
        self.assertIsNone(ctrl._find_asset(tmp, "ghost.jpg"))


class RunOfflineRetagTest(unittest.TestCase):
    def _run(self, csv_path, target_dir, rows, **kw):
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            import csv

            w = csv.writer(f)
            w.writerow(["Filename", "Title", "Description", "Keywords"])
            for r in rows:
                w.writerow(r)
        app = _stub_app()
        with mock.patch.object(ctrl, "get_file_hash", return_value="hash1"), mock.patch.object(
            ctrl, "set_cached_metadata"
        ) as m_set, mock.patch.object(
            ctrl, "extract_preview_image", return_value=None
        ):
            ctrl._run_offline_retag(app, csv_path, target_dir, 50, "Author", "Copy")
        return app, m_set

    def test_success_path(self):
        tmp = tempfile.mkdtemp()
        with open(os.path.join(tmp, "a.jpg"), "w"):
            pass
        csv_path = os.path.join(tmp, "in.csv")
        app, m_set = self._run(csv_path, tmp, [["a.jpg", "T", "D", "k1, k2"]])

        self.assertEqual(app.processor.calls[0][0], os.path.join(tmp, "a.jpg"))
        self.assertEqual(app.processor.calls[0][1], "T")
        self.assertEqual(app.processor.calls[0][2], "D")
        self.assertEqual(app.processor.calls[0][3], ["k1", "k2"])
        self.assertEqual(app.processor.calls[0][4], "Copy")
        self.assertEqual(app.processor.calls[0][5], "Author")
        m_set.assert_called_once_with("hash1", {"title": "T", "description": "D", "keywords": ["k1", "k2"]})
        self.assertEqual(app.progress_bar.value, 1.0)
        self.assertEqual(app.retag_btn.state, "normal")
        self.assertEqual(app.start_btn.state, "normal")
        self.assertIn(("success", "Successfully tagged 1/1 files from CSV."), app.log_lines)

    def test_missing_file_skipped(self):
        tmp = tempfile.mkdtemp()
        csv_path = os.path.join(tmp, "in.csv")
        app, m_set = self._run(csv_path, tmp, [["ghost.jpg", "T", "D", "k1"]])

        self.assertEqual(app.processor.calls, [])
        m_set.assert_not_called()
        self.assertIn(("error", "ghost.jpg not found in folder"), app.log_lines)
        self.assertEqual(app.progress_bar.value, 0)

    def test_csv_read_error_reenables(self):
        app = _stub_app()
        with mock.patch.object(ctrl, "get_file_hash") as m_hash:
            ctrl._run_offline_retag(app, "/nonexistent/in.csv", "/tmp", 50, "", "")
        m_hash.assert_not_called()
        self.assertEqual(app.retag_btn.state, "normal")
        self.assertEqual(app.start_btn.state, "normal")


if __name__ == "__main__":
    unittest.main()