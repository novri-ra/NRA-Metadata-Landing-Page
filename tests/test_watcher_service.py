import os
import tempfile
import unittest

from backend.services.folder_watcher import FolderWatcher


def _make_dir(files):
    tmp = tempfile.mkdtemp()
    for name in files:
        open(os.path.join(tmp, name), "w").close()
    return tmp


class FolderWatcherTest(unittest.TestCase):
    def test_instantiation(self):
        watcher = FolderWatcher(
            get_directory=lambda: "/tmp", is_allowed=lambda f: True,
            is_busy=lambda: False, on_new_files=lambda files: None,
        )
        self.assertFalse(watcher.running)

    def test_start_spawns_thread(self):
        watcher = FolderWatcher(
            get_directory=lambda: "/tmp", is_allowed=lambda f: True,
            is_busy=lambda: False, on_new_files=lambda files: None,
        )
        watcher.start()
        self.assertTrue(watcher.running)
        watcher.stop()
        self.assertFalse(watcher.running)

    def test_start_is_idempotent(self):
        watcher = FolderWatcher(
            get_directory=lambda: "/tmp", is_allowed=lambda f: True,
            is_busy=lambda: False, on_new_files=lambda files: None,
        )
        watcher.start()
        first = watcher._thread
        watcher.start()
        self.assertIs(first, watcher._thread)
        watcher.stop()

    def test_loop_ignores_disallowed_files(self):
        tmp = _make_dir(["a.zip", "b.txt"])
        seen = []
        watcher = FolderWatcher(
            get_directory=lambda: tmp,
            is_allowed=lambda f: f.endswith(".zip"),
            is_busy=lambda: False,
            on_new_files=lambda files: seen.extend(files),
        )
        watcher._scan()
        self.assertEqual(seen, ["a.zip"])

    def test_loop_skips_when_busy(self):
        tmp = _make_dir(["a.zip"])
        seen = []
        watcher = FolderWatcher(
            get_directory=lambda: tmp,
            is_allowed=lambda f: True,
            is_busy=lambda: True,
            on_new_files=lambda files: seen.extend(files),
        )
        watcher._scan()
        self.assertEqual(seen, [])

    def test_loop_fires_callback_with_present_files(self):
        tmp = _make_dir(["a.zip", "b.zip"])
        watcher = FolderWatcher(
            get_directory=lambda: tmp,
            is_allowed=lambda f: True,
            is_busy=lambda: False,
            on_new_files=unittest.mock.Mock(),
        )
        watcher._scan()
        watcher._on_new_files.assert_called_once_with(["a.zip", "b.zip"])

    def test_loop_handles_missing_directory(self):
        watcher = FolderWatcher(
            get_directory=lambda: "/nonexistent/path/xyz",
            is_allowed=lambda f: True,
            is_busy=lambda: False,
            on_new_files=unittest.mock.Mock(),
        )
        watcher._scan()
        watcher._on_new_files.assert_not_called()

    def test_debounce_between_fires(self):
        tmp = _make_dir(["a.zip"])
        watcher = FolderWatcher(
            get_directory=lambda: tmp,
            is_allowed=lambda f: True,
            is_busy=lambda: False,
            on_new_files=unittest.mock.Mock(),
            poll_interval=0.01,
            debounce=60.0,
        )
        watcher._scan()
        watcher._scan()
        watcher._on_new_files.assert_called_once_with(["a.zip"])


if __name__ == "__main__":
    unittest.main()