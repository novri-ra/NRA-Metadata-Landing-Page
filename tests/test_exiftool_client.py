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


class StreamingWriteTest(unittest.TestCase):
    def test_streaming_rewrites_file_via_pipe(self):
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "img.jpg"
            _make_file(target, b"ORIGINAL-BYTES")

            ok = mock.Mock(
                returncode=0, stdout=b"NEW-STREAMED-BYTES", stderr=b"Warning: minor"
            )
            with mock.patch(
                "backend.processors.exiftool_client._run_exiftool_stream"
            ) as stream:
                stream.return_value = ok
                ec._run_metadata_write(
                    ["exiftool", "-overwrite_original_in_place", "-m", str(target)],
                    str(target),
                    timeout=30,
                )

            self.assertEqual(target.read_bytes(), b"NEW-STREAMED-BYTES")
            stream_cmd, _timeout, input_bytes = stream.call_args.args
            self.assertNotIn("-overwrite_original_in_place", stream_cmd)
            self.assertNotIn("-overwrite_original", stream_cmd)
            self.assertEqual(stream_cmd[-3:], ["-o", "-", "-"])
            self.assertEqual(input_bytes, b"ORIGINAL-BYTES")

    def test_streaming_empty_stdout_falls_back_to_in_place(self):
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "img.jpg"
            _make_file(target, b"ORIGINAL")

            empty = mock.Mock(returncode=0, stdout=b"", stderr=b"")
            with mock.patch(
                "backend.processors.exiftool_client._run_exiftool_stream"
            ) as stream, mock.patch(
                "backend.processors.exiftool_client._run_exiftool"
            ) as run:
                stream.return_value = empty
                run.return_value = mock.Mock(returncode=0, stdout="ok", stderr="")
                result = ec._run_metadata_write(
                    ["exiftool", "-overwrite_original_in_place", "-m", str(target)],
                    str(target),
                    timeout=30,
                )

            self.assertEqual(run.call_count, 1)
            self.assertEqual(result.returncode, 0)

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


if __name__ == "__main__":
    unittest.main()
