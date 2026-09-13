import os
import tempfile
import unittest
from unittest import mock

from backend.services.ftp_uploader import FTPUploader


class FTPUploaderTest(unittest.TestCase):
    def _uploader(self, **kw):
        return FTPUploader("ftp.example.com", 21, "user", "pass", **kw)

    def test_instantiation(self):
        up = self._uploader()
        self.assertEqual(up._client.host, "ftp.example.com")
        self.assertEqual(up._client.port, 21)

    def test_collect_files_zip_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("a.zip", "b.eps", "c.JPG"):
                open(os.path.join(tmp, name), "w").close()
            found = self._uploader().collect_files(tmp, zip_only=True)
            self.assertEqual(found, [os.path.join(tmp, "a.zip")])

    def test_collect_files_allowed_extensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("a.zip", "b.eps", "c.svg", "d.csv", "e.txt"):
                open(os.path.join(tmp, name), "w").close()
            found = self._uploader().collect_files(tmp, zip_only=False)
            found = {os.path.basename(p) for p in found}
            self.assertEqual(found, {"a.zip", "b.eps", "c.svg", "d.csv"})

    def test_upload_batch_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("a.zip", "b.zip"):
                open(os.path.join(tmp, name), "w").close()
            up = self._uploader()
            logs, progs = [], []
            with mock.patch.object(
                up._client, "connect", return_value=(True, "Connected")
            ) as conn, mock.patch.object(
                up._client, "upload_file", return_value=True
            ) as upf, mock.patch.object(up._client, "disconnect") as disc:
                success, total = up.upload_batch(
                    tmp, True, log_cb=lambda m, l: logs.append((m, l)),
                    progress_cb=progs.append,
                )
            conn.assert_called_once()
            self.assertEqual(upf.call_count, 2)
            disc.assert_called_once()
            self.assertEqual((success, total), (2, 2))
            self.assertEqual(progs, [0, 0.5, 1.0])
            self.assertTrue(any("OK" in m for m, _ in logs))

    def test_connect_failure_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "a.zip"), "w").close()
            up = self._uploader()
            with mock.patch.object(
                up._client, "connect", return_value=(False, "refused")
            ) as conn, mock.patch.object(up._client, "disconnect") as disc:
                success, total = up.upload_batch(tmp, True, log_cb=lambda m, l: None)
            conn.assert_called_once()
            disc.assert_not_called()
            self.assertEqual((success, total), (0, 0))

    def test_no_files_disconnects(self):
        with tempfile.TemporaryDirectory() as tmp:
            up = self._uploader()
            with mock.patch.object(
                up._client, "connect", return_value=(True, "Connected")
            ), mock.patch.object(up._client, "disconnect") as disc, mock.patch.object(
                up._client, "upload_file"
            ) as upf:
                success, total = up.upload_batch(tmp, True, log_cb=lambda m, l: None)
            disc.assert_called_once()
            upf.assert_not_called()
            self.assertEqual((success, total), (0, 0))

    def test_retry_until_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "a.zip"), "w").close()
            up = self._uploader(max_retries=3)
            attempts = []

            def flaky(path):
                attempts.append(path)
                return len(attempts) >= 2

            with mock.patch.object(
                up._client, "connect", return_value=(True, "Connected")
            ), mock.patch.object(up._client, "upload_file", side_effect=flaky), mock.patch.object(
                up._client, "disconnect"
            ):
                success, total = up.upload_batch(tmp, True, log_cb=lambda m, l: None)
            self.assertEqual((success, total), (1, 1))
            self.assertEqual(len(attempts), 2)

    def test_fail_after_max_retries(self):
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "a.zip"), "w").close()
            up = self._uploader(max_retries=3)
            with mock.patch.object(
                up._client, "connect", return_value=(True, "Connected")
            ), mock.patch.object(up._client, "upload_file", return_value=False), mock.patch.object(
                up._client, "disconnect"
            ):
                success, total = up.upload_batch(tmp, True, log_cb=lambda m, l: None)
            self.assertEqual((success, total), (0, 1))


if __name__ == "__main__":
    unittest.main()