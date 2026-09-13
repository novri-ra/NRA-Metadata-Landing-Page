"""Directory watcher service. No Tkinter dependencies.

Polls a directory and fires a callback when new allowed files appear,
debouncing so a file mid-copy does not retrigger repeatedly.
"""
import os
import threading
import time
from collections.abc import Callable


class FolderWatcher:
    """Polls a directory and fires ``on_new_files`` when files appear.

    The app wires in simple callbacks instead of holding tkinter refs:
    ``get_directory`` returns the folder to watch, ``is_allowed`` filters
    file names, ``is_busy`` pauses scans, and ``on_new_files`` receives
    the batch of allowed files currently present.
    """

    def __init__(
        self,
        get_directory: Callable[[], str],
        is_allowed: Callable[[str], bool],
        is_busy: Callable[[], bool],
        on_new_files: Callable[[list[str]], None],
        poll_interval: float = 3.0,
        debounce: float = 1.0,
    ):
        self._get_directory = get_directory
        self._is_allowed = is_allowed
        self._is_busy = is_busy
        self._on_new_files = on_new_files
        self._poll_interval = poll_interval
        self._debounce = debounce
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_fire = 0.0

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=self._poll_interval + self._debounce + 1)
            self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _loop(self):
        while not self._stop.wait(self._poll_interval):
            self._scan()

    def _scan(self):
        now = time.time()
        if now - self._last_fire < self._debounce:
            return
        try:
            directory = self._get_directory()
            if not directory or not os.path.isdir(directory):
                return
            if self._is_busy():
                return
            files = [
                f
                for f in os.listdir(directory)
                if os.path.isfile(os.path.join(directory, f))
                and self._is_allowed(f)
            ]
            if files:
                self._last_fire = now
                self._on_new_files(files)
        except Exception:
            pass