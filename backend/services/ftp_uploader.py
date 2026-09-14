"""FTP batch upload service. No Tkinter dependencies.

Wraps the low-level FTPClient with batch orchestration, retry logic,
and callback-driven progress/status reporting.
"""
import os
import time
from collections.abc import Callable

from packages.shared_utils.ftp_uploader import FTPClient


class FTPUploader:
    """Connects, uploads files with retry, reports via callbacks."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        passwd: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        cancel_check: Callable[[], bool] | None = None,
    ):
        self._client = FTPClient(host, port, user, passwd, cancel_check=cancel_check)
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    def connect(self) -> tuple[bool, str]:
        return self._client.connect()

    def disconnect(self):
        self._client.disconnect()

    def upload_file(self, local_path: str) -> bool:
        return self._client.upload_file(local_path)

    def collect_files(self, folder: str, zip_only: bool) -> list[str]:
        valid_exts = (".zip",) if zip_only else (".zip", ".eps", ".jpg", ".svg", ".csv")
        result = []
        for root, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(valid_exts):
                    result.append(os.path.join(root, f))
        return result

    def upload_batch(
        self,
        folder: str,
        zip_only: bool,
        log_cb: Callable[[str, str], None] | None = None,
        progress_cb: Callable[[float], None] | None = None,
    ) -> tuple[int, int]:
        """Upload all matching files. Returns (success, total).

        Connects, walks *folder*, and uploads each file with up to
        *max_retries* attempts.  Calls *log_cb(message, level)* for
        status/progress lines and *progress_cb(fraction)* with each
        file completed.
        """
        ok, msg = self.connect()
        if not ok:
            if log_cb:
                log_cb(f"FTP Connect Error: {msg}", "error")
            return 0, 0

        files = self.collect_files(folder, zip_only)
        if not files:
            self.disconnect()
            if log_cb:
                log_cb("No valid files to upload via FTP.", "error")
            return 0, 0

        total = len(files)
        if log_cb:
            log_cb(f"FTP Uploading {total} files...", "info")
        if progress_cb:
            progress_cb(0)

        success = 0
        try:
            for i, fpath in enumerate(files):
                if self._client.cancel_check():
                    if log_cb:
                        log_cb("FTP: upload canceled by user.", "error")
                    break
                fname = os.path.basename(fpath)
                if log_cb:
                    log_cb(f"FTP: uploading {fname}...", "processing")

                uploaded = False
                for attempt in range(1, self._max_retries + 1):
                    if self.upload_file(fpath):
                        uploaded = True
                        break
                    if attempt < self._max_retries:
                        if log_cb:
                            log_cb(
                                f"FTP: retry {fname} (attempt {attempt + 1})...",
                                "processing",
                            )
                        time.sleep(self._retry_delay)

                if uploaded:
                    if log_cb:
                        log_cb(f"FTP: OK {fname}", "success")
                    success += 1
                else:
                    if log_cb:
                        log_cb(f"FTP: FAIL {fname}", "error")

                if progress_cb:
                    progress_cb((i + 1) / total)
        finally:
            self.disconnect()
        if log_cb:
            log_cb(f"FTP Upload Complete: {success}/{total} successful.", "info")
        return success, total
