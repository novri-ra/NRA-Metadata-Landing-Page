import os
import stat
import tempfile
import unittest
from pathlib import Path

from backend.processors import exiftool_client as ec
from backend.processors._tools import exiftool_flags


def _make_file(path: Path, content: bytes = b"ORIG") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


class PrepareTargetTest(unittest.TestCase):
    def test_clears_read_only_on_file_and_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sub" / "img.jpg"
            _make_file(target)
            os.chmod(target, stat.S_IREAD)
            os.chmod(target.parent, stat.S_IREAD)
            ec._prepare_target(str(target))
            self.assertTrue(os.access(target, os.W_OK))
            self.assertTrue(os.access(target.parent, os.W_OK))


class EssentialFlagsTest(unittest.TestCase):
    def test_exe_carries_in_place_overwrite_flag(self):
        self.assertEqual(
            exiftool_flags(r"C:\tools\exiftool.exe"),
            [
                "-api",
                "Windows=1",
                "-overwrite_original_in_place",
                "-m",
                "-charset",
                "filename=utf8",
            ],
        )

    def test_non_exe_skips_windows_api_only(self):
        self.assertEqual(
            exiftool_flags("exiftool"),
            ["-overwrite_original_in_place", "-m", "-charset", "filename=utf8"],
        )

    def test_sanitize_command_targets_in_place_overwrite(self):
        from unittest import mock

        captured = {}
        proc = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch("backend.processors.exiftool_client._run_exiftool") as run:
            run.return_value = proc
            ec.ExifToolClient().sanitize_ai_metadata("sub/dir/test_image.png")
            captured = run.call_args.args[0]
        joined = " ".join(captured)
        self.assertIn("-overwrite_original_in_place", joined)
        self.assertNotIn("-overwrite_original ", joined + " ")
        self.assertIn("\\test_image.png", captured[-1])


class StagingFallbackTest(unittest.TestCase):
    def test_write_blocked_retries_on_temp_copy_and_restores(self):
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "img.eps"
            _make_file(target, b"EPS")

            blocked = mock.Mock(
                returncode=1,
                stdout="",
                stderr="Error creating file: .../img.eps_exiftool_tmp - permission denied",
            )
            ok = mock.Mock(returncode=0, stdout="1 image files updated", stderr="")

            with mock.patch("backend.processors.exiftool_client._run_exiftool") as run:
                run.side_effect = [blocked, ok]
                result = ec._run_exiftool_resilient(
                    ["exiftool", "-m", str(target)], timeout=30, file_path=str(target)
                )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(run.call_count, 2)
            retried_target = run.call_args.args[0][-1]
            self.assertNotEqual(retried_target, str(target))
            self.assertTrue(
                os.path.normpath(retried_target).startswith(
                    os.path.normpath(tempfile.gettempdir())
                )
            )
            self.assertFalse(os.path.exists(retried_target), "temp copy must be cleaned up")

    def test_staged_cmd_uses_plain_overwrite_and_temp_cwd(self):
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "img.eps"
            _make_file(target, b"EPS")

            blocked = mock.Mock(
                returncode=1,
                stdout="",
                stderr="Error creating file: .../img.eps_exiftool_tmp - permission denied",
            )
            ok = mock.Mock(returncode=0, stdout="1 image files updated", stderr="")

            with mock.patch("backend.processors.exiftool_client._run_exiftool") as run:
                run.side_effect = [blocked, ok]
                ec._run_exiftool_resilient(
                    ["exiftool", "-overwrite_original_in_place", "-m", str(target)],
                    timeout=30,
                    file_path=str(target),
                )

            staged_cmd = run.call_args.args[0]
            self.assertNotIn("-overwrite_original_in_place", staged_cmd)
            self.assertIn("-overwrite_original", staged_cmd)
            self.assertNotEqual(staged_cmd[-1], str(target))
            self.assertEqual(
                os.path.dirname(staged_cmd[-1]), run.call_args.kwargs["cwd"]
            )
            if os.name == "nt":
                self.assertIn("-api", staged_cmd)
                self.assertIn("Windows=1", staged_cmd)

    def test_non_write_error_does_not_restage(self):
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "img.eps"
            _make_file(target, b"EPS")

            broken = mock.Mock(
                returncode=1, stdout="", stderr="File is corrupted"
            )
            with mock.patch("backend.processors.exiftool_client._run_exiftool") as run:
                run.return_value = broken
                result = ec._run_exiftool_resilient(
                    ["exiftool", "-m", str(target)], timeout=30, file_path=str(target)
                )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(run.call_count, 1)

    def test_temp_staging_fail_raises_tool_execution_error(self):
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "img.eps"
            _make_file(target, b"EPS")

            blocked = mock.Mock(
                returncode=1,
                stdout="",
                stderr="Error creating file: .../img.eps_exiftool_tmp - permission denied",
            )
            with mock.patch("backend.processors.exiftool_client._run_exiftool") as run:
                run.return_value = blocked
                with self.assertRaises(ec.ToolExecutionError) as ctx:
                    ec._run_exiftool_resilient(
                        ["exiftool", "-m", str(target)], timeout=30, file_path=str(target)
                    )

            self.assertEqual(run.call_count, 2)
            self.assertEqual(ctx.exception.result.returncode, 1)


if __name__ == "__main__":
    unittest.main()