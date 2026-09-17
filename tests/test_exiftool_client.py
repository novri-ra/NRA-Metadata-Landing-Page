import os
import stat
import tempfile
import unittest
import xml.etree.ElementTree as ET
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
                "-overwrite_original",
                "-m",
                "-charset",
                "filename=utf8",
            ],
        )

    def test_non_exe_skips_windows_api_only(self):
        self.assertEqual(
            exiftool_flags("exiftool"),
            ["-overwrite_original", "-m", "-charset", "filename=utf8"],
        )

    def test_sanitize_command_targets_in_place_overwrite(self):
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            fake_exe = Path(tmp) / "exiftool.exe"
            fake_exe.write_bytes(b"MZ")

            captured = {}
            proc = mock.Mock(returncode=0, stdout="", stderr="")
            with (
                mock.patch("backend.processors.exiftool_client._run_exiftool") as run,
                mock.patch(
                    "backend.processors.exiftool_client.get_exiftool_path",
                    return_value=str(fake_exe),
                ),
            ):
                run.return_value = proc
                client = ec.ExifToolClient()
                client.sanitize_ai_metadata("sub/dir/test_image.png")
                cmd = run.call_args[0][0]
                joined = " ".join(cmd)
                self.assertIn("-overwrite_original", joined)
            self.assertNotIn("-overwrite_original_in_place", joined)
            self.assertIn("test_image.png", joined)


class SubprocessInvocationTest(unittest.TestCase):
    def test_run_exiftool_uses_binary_dir_as_cwd_and_suppresses_console(self):
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            fake_exe = Path(tmp) / "exiftool.exe"
            fake_exe.write_bytes(b"MZ")

            proc = mock.Mock(returncode=0, stdout="13.26\n", stderr="")
            with (
                mock.patch("backend.processors.exiftool_client.subprocess.run", return_value=proc) as run,
                mock.patch("backend.processors.exiftool_client.ExifToolDaemon.execute_command", side_effect=Exception("mock fail to force fallback"))
            ):
                ec._run_exiftool([str(fake_exe), "-ver"], timeout=30)

            kwargs = run.call_args.kwargs
            self.assertEqual(kwargs["cwd"], tmp)
            if os.name == "nt":
                self.assertIn("creationflags", kwargs)
                self.assertTrue(kwargs["creationflags"] & 0x08000000, "no console window")

    def test_run_exiftool_stream_uses_binary_dir_as_cwd(self):
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            fake_exe = Path(tmp) / "exiftool.exe"
            fake_exe.write_bytes(b"MZ")

            with mock.patch("subprocess.Popen") as mock_popen:
                mock_proc = mock.MagicMock()
                mock_proc.stdin = mock.Mock()
                mock_proc.communicate.return_value = (b"data", b"")
                mock_proc.returncode = 0
                mock_proc.__enter__.return_value = mock_proc
                mock_popen.return_value = mock_proc
                
                ec._run_exiftool_stream([str(fake_exe), "-o", "-", "-"], timeout=30, input_bytes=b"x")

                self.assertEqual(mock_popen.call_args.kwargs["cwd"], tmp)


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


class StreamingWriteTest(unittest.TestCase):
    def test_streaming_disabled_for_robustness(self):
        # Streaming via Popen STDIN/STDOUT was disabled to prevent deadlocks.
        # Ensure _run_metadata_write calls _run_exiftool_resilient directly.
        from unittest import mock
        with mock.patch("backend.processors.exiftool_client._run_exiftool_resilient") as resilient:
            ec._run_metadata_write(["cmd"], "file", timeout=15)
            resilient.assert_called_once_with(["cmd"], timeout=15, file_path="file")

    def test_pre_cleanup_removes_leftover_tmp(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "img.jpg"
            _make_file(target, b"ORIGINAL")
            leftover = Path(tmp) / "img.jpg_exiftool_tmp"
            leftover.write_bytes(b"junk")
            ec._pre_cleanup_temp(str(target))
            self.assertFalse(leftover.exists())


class SvgMetadataTest(unittest.TestCase):
    def _write_svg(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><g/></svg>', encoding="utf-8"
        )

    def test_svg_keywords_written_as_dc_subject_bag(self):
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "icon.svg"
            self._write_svg(target)
            with mock.patch("backend.processors.exiftool_client.log_failed_file"):
                result = ec.ExifToolClient()._embed_svg_metadata(
                    str(target),
                    "Red Ball Icon",
                    "A red ball vector",
                    ["red", "ball", "icon"],
                    "c",
                    "author",
                )
            self.assertTrue(result)
            tree = ET.parse(str(target))
            root = tree.getroot()
            li_texts = [el.text for el in root.iter() if el.tag.endswith("}li")]
            self.assertEqual(li_texts, ["red", "ball", "icon"])
            bag = [
                el for el in root.iter() if el.tag.endswith("}Bag")
            ]
            self.assertEqual(len(bag), 1)

    def test_svg_keyword_escaping_round_trips(self):
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "icon.svg"
            self._write_svg(target)
            with mock.patch("backend.processors.exiftool_client.log_failed_file"):
                result = ec.ExifToolClient()._embed_svg_metadata(
                    str(target),
                    "T",
                    "D",
                    ["A & B", "3 < 4", 'q " quote'],
                    "",
                    "",
                )
            self.assertTrue(result)
            raw = target.read_text(encoding="utf-8")
            self.assertIn("&amp;", raw)
            self.assertIn("&lt;", raw)
            self.assertNotIn("<A & B>", raw)
            tree = ET.parse(str(target))
            li_texts = [el.text for el in tree.getroot().iter() if el.tag.endswith("}li")]
            self.assertEqual(li_texts, ["A & B", "3 < 4", 'q " quote'])


class EpsDscTitleTest(unittest.TestCase):
    def test_patch_eps_dsc_title_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "img.eps"
            target.write_bytes(b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 100 100\n%%Title: Old Name\n%%EndComments")
            ec._patch_eps_dsc_title(str(target), "New Beautiful Title ")
            content = target.read_bytes()
            self.assertIn(b"%%Title: New Beautiful Title", content)
            self.assertNotIn(b"Old Name", content)

    def test_patch_eps_dsc_title_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "img.eps"
            target.write_bytes(b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 100 100\n%%EndComments")
            ec._patch_eps_dsc_title(str(target), "Injected Title")
            content = target.read_bytes()
            self.assertIn(b"%%Title: Injected Title\n", content)

class IptcAiFieldsTest(unittest.TestCase):
    def test_ai_generated_with_model_writes_system_used(self):
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            fake_exe = Path(tmp) / "exiftool.exe"
            fake_exe.write_bytes(b"MZ")
            proc = mock.Mock(returncode=0, stdout="", stderr="")
            with (
                mock.patch("backend.processors.exiftool_client._run_exiftool") as run,
                mock.patch(
                    "backend.processors.exiftool_client.get_exiftool_path",
                    return_value=str(fake_exe),
                ),
            ):
                run.return_value = proc
                ec.ExifToolClient().sanitize_ai_metadata(
                    "img.png",
                    is_ai_generated=True,
                    ai_system_name="Gemini",
                    ai_system_version="2.5-flash",
                )
                cmd = " ".join(run.call_args.args[0])
            self.assertIn("trainedAlgorithmicMedia", cmd)
            self.assertIn("-XMP-iptcExt:AISystemUsed=Gemini", cmd)
            self.assertIn("-XMP-iptcExt:AISystemVersionUsed=2.5-flash", cmd)

    def test_ai_generated_without_model_skips_system_used(self):
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            fake_exe = Path(tmp) / "exiftool.exe"
            fake_exe.write_bytes(b"MZ")
            proc = mock.Mock(returncode=0, stdout="", stderr="")
            with (
                mock.patch("backend.processors.exiftool_client._run_exiftool") as run,
                mock.patch(
                    "backend.processors.exiftool_client.get_exiftool_path",
                    return_value=str(fake_exe),
                ),
            ):
                run.return_value = proc
                ec.ExifToolClient().sanitize_ai_metadata(
                    "img.png",
                    is_ai_generated=True,
                )
                cmd = " ".join(run.call_args.args[0])
            self.assertIn("trainedAlgorithmicMedia", cmd)
            self.assertNotIn("AISystemUsed", cmd)
            self.assertNotIn("AISystemVersionUsed", cmd)

    def test_non_ai_does_not_write_ai_fields(self):
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            fake_exe = Path(tmp) / "exiftool.exe"
            fake_exe.write_bytes(b"MZ")
            proc = mock.Mock(returncode=0, stdout="", stderr="")
            with (
                mock.patch("backend.processors.exiftool_client._run_exiftool") as run,
                mock.patch(
                    "backend.processors.exiftool_client.get_exiftool_path",
                    return_value=str(fake_exe),
                ),
            ):
                run.return_value = proc
                ec.ExifToolClient().sanitize_ai_metadata(
                    "img.png",
                    is_ai_generated=False,
                    ai_system_name="Gemini",
                )
                cmd = " ".join(run.call_args.args[0])
            self.assertNotIn("trainedAlgorithmicMedia", cmd)
            self.assertNotIn("AISystemUsed", cmd)


if __name__ == "__main__":
    unittest.main()
import unittest

class TestExifToolDaemon(unittest.TestCase):
    def test_daemon_lifecycle_and_auto_recovery(self):
        from unittest import mock
        from backend.processors.exiftool_client import ExifToolDaemon

        daemon = ExifToolDaemon()
        daemon.shutdown() # Reset state
        
        with mock.patch("backend.processors.exiftool_client.subprocess.Popen") as mock_popen, \
             mock.patch("backend.processors.exiftool_client.get_exiftool_path", return_value="fake_exiftool"):
            
            mock_proc = mock.MagicMock()
            mock_proc.poll.return_value = None
            mock_proc.stdout.readline.side_effect = ["1 image files updated\n", "{ready1}\n"]
            mock_popen.return_value = mock_proc
            
            res = daemon.execute_command(["fake_exiftool", "-ver"])
            
            # Verify basic protocol write
            mock_proc.stdin.write.assert_any_call("-ver\n")
            mock_proc.stdin.write.assert_any_call("-execute1\n")
            mock_proc.stdin.flush.assert_called()
            self.assertIn("1 image files updated", res.stdout)
            self.assertEqual(res.returncode, 0)
            
            # Simulate crash and auto-recovery
            mock_proc.poll.return_value = 1 # Dead
            mock_proc2 = mock.MagicMock()
            mock_proc2.poll.return_value = None
            mock_proc2.stdout.readline.side_effect = ["Error: Something\n", "{ready2}\n"]
            mock_popen.return_value = mock_proc2
            
            res2 = daemon.execute_command(["fake_exiftool", "-m"])
            
            # Verified daemon restarted and executed
            mock_proc2.stdin.write.assert_any_call("-execute2\n")
            self.assertIn("Error:", res2.stdout)
            self.assertEqual(res2.returncode, 1)
