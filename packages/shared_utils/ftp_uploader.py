import ftplib
import os
from collections.abc import Callable


class FTPClient:
    def __init__(self, host: str, port: int, user: str, passwd: str, timeout: int = 30):
        self.host = host
        self.port = port
        self.user = user
        self.passwd = passwd
        self.timeout = timeout
        self.ftp = None

    def connect(self):
        try:
            self.ftp = ftplib.FTP()
            self.ftp.connect(self.host, self.port, timeout=self.timeout)
            self.ftp.login(self.user, self.passwd)
            return True, "Connected"
        except ftplib.all_errors as e:
            return False, str(e)

    def disconnect(self):
        if self.ftp:
            try:
                self.ftp.quit()
            except OSError:
                self.ftp.close()
            self.ftp = None

    def upload_file(
        self,
        local_path: str,
        remote_filename: str | None = None,
        progress_cb: Callable | None = None,
    ) -> bool:
        if not self.ftp:
            return False

        filename = remote_filename or os.path.basename(local_path)
        try:
            with open(local_path, "rb") as f:
                if progress_cb:
                    self.ftp.storbinary(
                        f"STOR {filename}", f, 8192, callback=progress_cb
                    )
                else:
                    self.ftp.storbinary(f"STOR {filename}", f, 8192)
            return True
        except ftplib.all_errors:
            return False

    def upload_batch(self, files: list[str], log_cb: Callable | None = None) -> int:
        success = 0
        for fpath in files:
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
