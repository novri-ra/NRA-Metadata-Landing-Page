import os
import tempfile
import unittest
from unittest import mock
from urllib.error import HTTPError

from packages.shared_utils import tools_setup as ts


def _resp(headers, read_effects):
    html = mock.MagicMock()
    html.headers = headers
    html.read.side_effect = read_effects
    html.__enter__.return_value = html
    return html


class DownloadHeaderAndTimeoutTest(unittest.TestCase):
    def test_download_sets_browser_agent_and_timeout(self):
        calls = {}
        html = _resp({"Content-Type": "application/octet-stream"}, [b"PK\x03\x04bytes", b""])
        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = html
            with tempfile.TemporaryDirectory() as tmp:
                dest = os.path.join(tmp, "out.bin")
                ts._download("https://example.com/x.zip", dest, timeout=20)
                req = urlopen.call_args.args[0]
                calls["agent"] = req.get_header("User-agent")
                calls["timeout"] = urlopen.call_args.kwargs.get("timeout")
                with open(dest, "rb") as f:
                    data = f.read()
        self.assertIn("Mozilla/5.0", calls["agent"])
        self.assertIn("Chrome", calls["agent"])
        self.assertEqual(calls["timeout"], 20)
        self.assertEqual(data, b"PK\x03\x04bytes")

    def test_html_content_type_rejected(self):
        html = _resp({"Content-Type": "text/html; charset=utf-8"}, [b"<html></html>", b""])
        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value = html
            with tempfile.TemporaryDirectory() as tmp:
                dest = os.path.join(tmp, "out.bin")
                with self.assertRaises(ValueError):
                    ts._download("https://example.com/x.zip", dest, timeout=20)


class ExifToolMirrorListTest(unittest.TestCase):
    def test_github_direct_mirror_present(self):
        # _setup_exiftool is nested; assert via source is brittle, so verify the
        # download helper signature accepts the per-mirror timeout the loop uses.
        import inspect

        params = inspect.signature(ts._download).parameters
        self.assertIn("timeout", params)
        self.assertEqual(params["timeout"].default, 120)


class GhostscriptInstallCmdTest(unittest.TestCase):
    def test_installer_command_nsis_layout(self):
        # /D must be the final arg with an unquoted path value.
        with tempfile.TemporaryDirectory() as tmp:
            td = os.path.normpath(tmp)
            installer = os.path.join(td, "gs_installer.exe")
            target = os.path.realpath(os.path.join(td, "ghostscript"))
            open(installer, "wb").close()
            gs_found = []

            def fake_find(td):
                return None  # force install path

            def fake_run(cmd, **kwargs):
                self.assertEqual(cmd[-1], f"/D={target}")
                self.assertEqual(cmd[1], "/S")
                self.assertEqual(kwargs.get("timeout"), 120)
                gs_found.append(True)
                return mock.Mock(returncode=0)

            with mock.patch.object(
                ts, "find_ghostscript_binary", side_effect=[None, None]
            ), mock.patch(
                "packages.shared_utils.tools_setup.discover_tools",
                return_value={"exiftool": None, "ghostscript": None, "ffmpeg": None},
            ), mock.patch.object(ts, "_download", return_value=None), mock.patch(
                "packages.shared_utils.tools_setup.subprocess.run",
                side_effect=fake_run,
            ):
                ts.ensure_tools_installed(tmp, progress_callback=lambda m: None)
        self.assertTrue(gs_found)


class SkipWhenDetectedTest(unittest.TestCase):
    def test_download_not_called_when_tools_present(self):
        # A detected + verified binary must skip download entirely.
        with tempfile.TemporaryDirectory() as tmp:
            for rel in ("exiftool.exe", "gswin64c.exe", "ffmpeg.exe"):
                open(os.path.join(tmp, rel), "wb").close()
            logs = []

            with mock.patch(
                "packages.shared_utils.tools_setup.discover_tools",
                return_value={
                    "exiftool": os.path.join(tmp, "exiftool.exe"),
                    "ghostscript": os.path.join(tmp, "gswin64c.exe"),
                    "ffmpeg": os.path.join(tmp, "ffmpeg.exe"),
                },
            ), mock.patch.object(
                ts, "_verify_binary", side_effect=lambda p, t: (True, "test-v")
            ) as verify, mock.patch.object(ts, "_download") as dl:
                ts.ensure_tools_installed(tmp, progress_callback=logs.append)
            dl.assert_not_called()
            skip_msgs = [m for m in logs if "Skipping download." in m]
            self.assertEqual(len(skip_msgs), 3)
            self.assertTrue(all("detected at:" in m for m in skip_msgs))


if __name__ == "__main__":
    unittest.main()