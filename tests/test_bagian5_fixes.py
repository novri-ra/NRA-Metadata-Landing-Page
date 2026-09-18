import csv
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from backend.core import config_manager
from backend.processors import system_detector
from backend.processors.exiftool_client import _normalize_date_created
from packages.shared_utils.csv_exporter import (
    build_editorial_caption,
    generate_microstock_csvs,
    upsert_editorial_csv,
)
from packages.shared_utils.env_check import check_exiftool
from packages.shared_utils.license_manager import (
    OFFLINE_SESSION_MAX_AGE_SECONDS,
    AuthClient,
)


class GhostscriptNumericVersionTest(unittest.TestCase):
    def test_numeric_sort_picks_gs10_over_gs9(self):
        paths = [
            r"C:\tools\ghostscript\gs9.56\bin\gswin64c.exe",
            r"C:\tools\ghostscript\gs10.02\bin\gswin64c.exe",
        ]
        self.assertEqual(
            system_detector._version_key(paths[0]), (9, 56)
        )
        self.assertEqual(
            system_detector._version_key(paths[1]), (10, 2)
        )
        self.assertEqual(
            system_detector._version_key(r"C:\gswin64c.exe"), ()
        )

    def test_latest_gs_version_wins(self):
        tmp = tempfile.mkdtemp()
        gs9 = os.path.join(tmp, "gs9.56", "bin", "gswin64c.exe")
        gs10 = os.path.join(tmp, "gs10.02", "bin", "gswin64c.exe")
        os.makedirs(os.path.dirname(gs9))
        os.makedirs(os.path.dirname(gs10))
        with open(gs9, "wb") as f:
            f.write(b"MZ")
        with open(gs10, "wb") as f:
            f.write(b"MZ")
        with patch.object(
            system_detector, "_tools_root", return_value=Path(tempfile.mkdtemp())
        ), patch("backend.processors.system_detector.which", return_value=None):
            found = system_detector._resolve_binary(
                ["gswin64c.exe"],
                extra_globs=(os.path.join(tmp, "gs*", "bin", "gswin*c.exe"),),
            )
        self.assertIsNotNone(found)
        self.assertIn("gs10.02", found)


class EnvCheckTimeoutTest(unittest.TestCase):
    def test_check_exiftool_timeout_falls_back_cleanly(self):
        calls = {}

        def fake_run(*args, **kwargs):
            calls.update(kwargs)
            raise subprocess.TimeoutExpired(args[0], timeout=kwargs.get("timeout"))

        with patch(
            "backend.processors.system_detector.detect_exiftool", return_value=None
        ), patch("packages.shared_utils.env_check.subprocess.run", side_effect=fake_run):
            ok, msg = check_exiftool()
        self.assertFalse(ok)
        self.assertIn("ExifTool not found", msg)
        self.assertEqual(calls.get("timeout"), 3)


class AtomicWriteTest(unittest.TestCase):
    def test_atomic_write_leaves_no_tmp(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "cfg.enc")
        config_manager.atomic_write_text(path, "hello")
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "hello")
        self.assertEqual(
            [n for n in os.listdir(tmpdir) if n.endswith(".tmp")], []
        )


class EditorialExportTest(unittest.TestCase):
    def _master(self, out_dir):
        path = os.path.join(out_dir, "metadata_output.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "Filename", "Title", "Description", "Keywords",
                    "IsAI", "IsEditorial", "City", "Country",
                    "CountryCode", "DateCreated",
                ],
            )
            w.writeheader()
            w.writerow(
                {
                    "Filename": "protest.eps",
                    "Title": "Protesters march downtown",
                    "Description": "Crowd of protesters marching along Main Street.",
                    "Keywords": "protest, march, downtown",
                    "IsAI": "0",
                    "IsEditorial": "1",
                    "City": "Jakarta",
                    "Country": "Indonesia",
                    "CountryCode": "ID",
                    "DateCreated": "2026-09-15",
                }
            )
        return path

    def test_editorial_caption_format(self):
        cap = build_editorial_caption(
            "Crowd of protesters marching.", "Jakarta", "Indonesia", "2026-09-15"
        )
        self.assertEqual(
            cap,
            "[Jakarta, Indonesia - September 15, 2026: Crowd of protesters marching.]",
        )
        self.assertEqual(
            build_editorial_caption("plain", "", "", ""), "plain"
        )

    def test_upsert_editorial_csv_header(self):
        tmpdir = tempfile.mkdtemp()
        master = os.path.join(tmpdir, "metadata_output.csv")
        upsert_editorial_csv(
            master, "a.eps", "T", "D", ["k"], True, "Jakarta", "ID", "ID", "2026-09-15"
        )
        with open(master, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows[0][5], "IsEditorial")
        self.assertEqual(rows[1][0], "a.eps")
        self.assertEqual(rows[1][5], "1")
        self.assertEqual(rows[1][9], "2026-09-15")

    def test_editorial_platform_columns(self):
        tmpdir = tempfile.mkdtemp()
        self._master(tmpdir)
        generate_microstock_csvs(tmpdir, {"Shutterstock", "Dreamstime"})
        with open(os.path.join(tmpdir, "shutterstock_export.csv"), encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]["Editorial"], "yes")
        with open(os.path.join(tmpdir, "dreamstime_export.csv"), encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]["Editorial"], "yes")

    def test_getty_editorial_export_generated(self):
        tmpdir = tempfile.mkdtemp()
        self._master(tmpdir)
        generate_microstock_csvs(tmpdir, {"Generic"})
        out = os.path.join(tmpdir, "getty_editorial_export.csv")
        self.assertTrue(os.path.exists(out))
        with open(out, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]["City"], "Jakarta")
        self.assertEqual(rows[0]["DateCreated"], "2026-09-15")


class EditorialExifTest(unittest.TestCase):
    def test_normalize_date_created(self):
        self.assertEqual(_normalize_date_created("2026-09-15"), "20260915")
        self.assertEqual(_normalize_date_created("2026/9/5"), "20260905")
        self.assertEqual(_normalize_date_created("20260915"), "20260915")


class LicenseGuardTest(unittest.TestCase):
    def setUp(self):
        self.client = AuthClient()
        self.client.username = "tester"
        self.client.session_token = "tok"
        self.client.config["auth_last_valid"] = str(int(time.time()))

    def test_html_response_maps_to_status_error(self):
        resp = requests.Response()
        resp.status_code = 200
        resp._content = b"<!DOCTYPE html><html></html>"
        resp.headers["Content-Type"] = "text/html"
        with patch.object(self.client.session, "post", return_value=resp):
            result = self.client._post({"action": "PING"})
        self.assertEqual(result.get("status"), "ERROR")
        self.assertTrue(result.get("network"))

    @patch("backend.core.config_manager.save_config")
    def test_offline_session_expired_revokes(self, _save):
        self.client.config["auth_last_valid"] = str(
            int(time.time()) - OFFLINE_SESSION_MAX_AGE_SECONDS - 1
        )
        with patch.object(
            self.client,
            "_post",
            return_value={"status": "ERROR", "network": True, "message": "down"},
        ):
            is_valid, msg = self.client.validate_session()
        self.assertFalse(is_valid)
        self.assertIn("expired", msg)

    @patch("backend.core.config_manager.save_config")
    def test_fresh_offline_session_allowed(self, _save):
        with patch.object(
            self.client,
            "_post",
            return_value={"status": "ERROR", "network": True, "message": "down"},
        ):
            is_valid, msg = self.client.validate_session()
        self.assertTrue(is_valid)
        self.assertEqual(msg, "Offline mode")


if __name__ == "__main__":
    unittest.main()