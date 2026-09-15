import ftplib
import os
from collections.abc import Callable

# Flat tuple of exception classes: ftplib errors are already a tuple.
_IO_ERRORS = ftplib.all_errors + (OSError, IOError)


class FTPClient:
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        passwd: str,
        timeout: int = 30,
        cancel_check: Callable[[], bool] | None = None,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.passwd = passwd
        self.timeout = timeout
        self.cancel_check = cancel_check or (lambda: False)
        self.ftp = None

    def connect(self):
        try:
            self.ftp = ftplib.FTP()
            self.ftp.connect(self.host, self.port, timeout=self.timeout)
            self.ftp.login(self.user, self.passwd)
            return True, "Connected"
        except _IO_ERRORS as e:
            return False, str(e)

    def disconnect(self):
        ftp = self.ftp
        self.ftp = None
        if ftp is None:
            return
        try:
            ftp.quit()
        except _IO_ERRORS:
            try:
                ftp.close()
            except _IO_ERRORS:
                pass

    def upload_file(
        self,
        local_path: str,
        remote_filename: str | None = None,
        progress_cb: Callable | None = None,
    ) -> bool:
        if not self.ftp:
            return False
        if self.cancel_check():
            return False

        filename = remote_filename or os.path.basename(local_path)
        try:
            with open(local_path, "rb") as f:

                def _chunk(data):
                    if self.cancel_check():
                        raise RuntimeError("upload canceled")
                    if progress_cb:
                        progress_cb(data)

                if progress_cb or True:
                    self.ftp.storbinary(f"STOR {filename}", f, 8192, callback=_chunk)
            return True
        except _IO_ERRORS:
            return False
        except RuntimeError:
            return False

    def upload_batch(self, files: list[str], log_cb: Callable | None = None) -> int:
        success = 0
        for fpath in files:
            if self.cancel_check():
                if log_cb:
                    log_cb("Upload canceled.")
                break
            fname = os.path.basename(fpath)
            if log_cb:
                log_cb(f"Uploading {fname}...")
            if self.upload_file(fpath):
                success += 1
                if log_cb:
                    log_cb(f"Success: {fname}")
            else:
                if log_cb:
                    log_cb(f"Failed: {fname}")
        return success