"""ExifTool client for embedding IPTC/XMP metadata and stripping AI provenance.

Extracted from ``packages/media_processor/embedder.py``; the class was renamed
``MediaProcessor`` -> ``ExifToolClient``. Tool resolution lives in
``backend.processors._tools``.
"""

import logging
import os
import shutil
import stat
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from backend.processors._tools import (
    exiftool_flags,
    format_tool_failure,
    get_tool_path,
    log_failed_file,
)

logger = logging.getLogger(__name__)


def get_exiftool_path() -> str | None:
    """Resolve the ExifTool binary; ``None`` when it cannot be found."""
    return get_tool_path("exiftool")


def _prepare_target(file_path: str) -> None:
    """Clear read-only flags so ExifTool can overwrite the file in place.

    Stock-downloaded files often carry a read-only attribute; the in-place
    overwrite then fails on Windows if the file (or its parent) is locked.
    """
    # Parent directory first: a read-only parent blocks chmod on the file
    # itself (EACCES), so it must be unlocked before touching the file.
    parent = os.path.dirname(file_path)
    if parent:
        try:
            os.chmod(parent, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
        except OSError:
            pass
    try:
        os.chmod(file_path, stat.S_IREAD | stat.S_IWRITE)
    except OSError:
        pass


def _to_cli_path(path: str, is_exe: bool) -> str:
    """Convert WSL /mnt/<drive>/ paths to Windows format if running a Windows .exe."""
    if is_exe and os.name != "nt" and path.startswith("/mnt/") and len(path) > 6 and path[6] == "/":
        drive = path[5].upper()
        rest = path[7:].replace("/", "\\")
        return f"{drive}:\\{rest}"
    return path


def _run_exiftool(cmd: list, timeout: int) -> subprocess.CompletedProcess:
    """Run ExifTool with fully visible text output.

    The cwd is pinned to the ExifTool directory so the bundled Perl wrapper
    can always find its ``exiftool_files`` support modules, and stderr is
    decoded with ``errors="replace"`` so a non-UTF8 native message can never
    be swallowed by a decode exception while surfacing hidden command-line
    errors.
    """
    exiftool_path = cmd[0]
    cwd = os.path.dirname(os.path.abspath(exiftool_path))
    is_exe = str(exiftool_path).lower().endswith(".exe")
    converted_cmd = [cmd[0]] + [_to_cli_path(arg, is_exe) for arg in cmd[1:]]
    return subprocess.run(
        converted_cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=cwd,
    )


def _looks_like_write_blocked(result: subprocess.CompletedProcess) -> bool:
    """True when ExifTool failed because it could not create/overwrite a file.

    The in-place overwrite path makes ExifTool create ``<file>_exiftool_tmp``
    next to the target; when the folder is protected (e.g. Windows Links /
    Favorites), that creation fails and ExifTool exits 1. Native messages may
    surface on either stream, so both are scanned.
    """
    text = ((result.stderr or "") + " " + (result.stdout or "")).lower()
    return "error creating file" in text or (
        "permission denied" in text or "access is denied" in text
    )


class ToolExecutionError(RuntimeError):
    """ExifTool failed against the temp-staged copy too.

    Carries the staged ``CompletedProcess`` so callers can keep reporting the
    real tool stderr through their existing failure-logging path.
    """

    def __init__(self, message: str, result: subprocess.CompletedProcess):
        super().__init__(message)
        self.result = result


def _run_exiftool_resilient(
    cmd: list, timeout: int, file_path: str
) -> subprocess.CompletedProcess:
    """Run ExifTool; if the target folder blocks in-place writes, retry on a
    copy staged in a dedicated temp working directory, copy the result back
    onto the original, then clean up. Raises ``ToolExecutionError`` when the
    staged run fails as well.
    """
    result = _run_exiftool(cmd, timeout=timeout)
    if result.returncode == 0 or not _looks_like_write_blocked(result):
        return result

    # Target folder won't take the _exiftool_tmp file. Stage in system temp.
    staged_dir = None
    try:
        staged_dir = tempfile.mkdtemp(prefix="nra_exiftool_")
        staged_path = os.path.join(staged_dir, os.path.basename(file_path))
        shutil.copy2(file_path, staged_path)
        _prepare_target(staged_path)
        staged_cmd = list(cmd)
        staged_cmd[-1] = staged_path
        staged = _run_exiftool(staged_cmd, timeout=timeout)
        if staged.returncode == 0:
            _prepare_target(file_path)
            shutil.copy2(staged_path, file_path)
            print(
                f"[TEMP-STAGED] {os.path.basename(file_path)}: ExifTool ditulis "
                f"via temp folder ({tempfile.gettempdir()}) lalu disalin balik."
            )
            return staged
        raise ToolExecutionError(
            f"ExifTool masih gagal pada salinan temp {os.path.basename(file_path)}",
            staged,
        )
    except (OSError, ValueError) as e:
        print(f"[WARN] Temp staging fallback gagal untuk {os.path.basename(file_path)}: {e}")
        return result
    finally:
        if staged_dir and os.path.isdir(staged_dir):
            shutil.rmtree(staged_dir, ignore_errors=True)


def _log_exiftool_failure(
    file_path: str, cmd: list, result: subprocess.CompletedProcess
) -> None:
    """Print a structured, word-wrapped failure block for ExifTool.

    The command and stderr can be very long (hundreds of keyword arguments);
    rendering them as one giant line made real errors unreadable. Wrap output
    into a boxed block instead.
    """
    rows = [
        ("File", os.path.basename(file_path)),
        ("ExitCode", str(result.returncode)),
        ("Command", " ".join(cmd)),
        ("Error", (result.stderr or "").strip()),
    ]
    if result.stdout and result.stdout.strip():
        rows.append(("Stdout", result.stdout.strip()))
    block = format_tool_failure("[EXIFTOOL FAILURE]", rows)
    print(block, flush=True)
    logger.error("%s failed on %s:\n%s", "ExifTool", file_path, block)


class ExifToolClient:
    def sanitize_ai_metadata(self, file_path: str) -> bool:
        """Strip AI provenance and generation tags while preserving Adobe/creative app metadata."""
        file_path = os.path.normpath(os.path.abspath(file_path))
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        _prepare_target(file_path)
        exiftool_path = get_exiftool_path()
        if not exiftool_path or not os.path.isfile(exiftool_path):
            print(f"[EXIFTOOL ERROR] Binary tidak ditemukan di: {exiftool_path}")
            return False
        is_png = os.path.splitext(file_path)[1].lower() == ".png"
        cmd = [exiftool_path]
        cmd.extend(exiftool_flags(exiftool_path))
        if is_png:
            cmd.extend(
                [
                    "-PNG:parameters=",
                    "-PNG:prompt=",
                    "-PNG:workflow=",
                    "-PNG:negative_prompt=",
                    "-PNG:Generation time=",
                ]
            )
        cmd.extend(
            [
                "-XMP-c2pa:all=",
                "-XMP-xmpGImg:all=",
                "-XMP:DigitalSourceType=",
                file_path,
            ]
        )
        try:
            result = _run_exiftool_resilient(cmd, timeout=30, file_path=file_path)
        except subprocess.TimeoutExpired:
            print(f"[WARN] Sanitizer timeout on {os.path.basename(file_path)}")
            return False
        except ToolExecutionError as e:
            _log_exiftool_failure(file_path, cmd, e.result)
            return False
        except (OSError, ValueError) as e:
            # We don't hard fail if sanitization fails (e.g. exiftool error on a specific file type)
            print(f"[WARN] Sanitizer error on {os.path.basename(file_path)}: {e}")
            return False
        if result.returncode != 0:
            _log_exiftool_failure(file_path, cmd, result)
            return False
        return True

    def embed_metadata(
        self,
        file_path: str,
        title: str,
        description: str,
        keywords: list[str],
        copyright_text: str,
        author: str = "",
    ) -> bool:
        file_path = os.path.normpath(os.path.abspath(file_path))
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        ext = file_path.lower().split(".")[-1]
        if ext == "svg":
            return self._embed_svg_metadata(
                file_path, title, description, keywords, copyright_text, author
            )

        if not os.path.isfile(file_path):
            print(
                f"[SKIP ERROR] {os.path.basename(file_path)}: target file does not exist"
            )
            log_failed_file(
                os.path.dirname(file_path),
                os.path.basename(file_path),
                "ExifTool: target file missing",
            )
            return False
        _prepare_target(file_path)

        # 1. Sanitize AI metadata first
        self.sanitize_ai_metadata(file_path)

        # 2. Embed new metadata
        exiftool_path = get_exiftool_path()
        if not exiftool_path or not os.path.isfile(exiftool_path):
            err_msg = f"[EXIFTOOL ERROR] Binary tidak ditemukan di: {exiftool_path}"
            print(err_msg)
            log_failed_file(
                os.path.dirname(file_path),
                os.path.basename(file_path),
                err_msg,
            )
            return False

        is_eps = ext == "eps"
        # Every argument must be a separate list item; no shell=True, no
        # hand-glued "-key=value" pairs.
        cmd = [exiftool_path]
        cmd.extend(exiftool_flags(exiftool_path))
        if is_eps:
            cmd.extend(["-charset", "iptc=UTF8"])
            # EPS (PostScript) carries XMP, so write the industry-standard
            # microstock tags (Adobe Stock / Shutterstock / Freepik) with
            # explicit XMP:/IPTC: group prefixes.
            cmd.extend(
                [
                    f"-XMP:Title={title}",
                    f"-IPTC:ObjectName={title}",
                    f"-XMP:Description={description}",
                    f"-IPTC:Caption-Abstract={description}",
                    f"-XMP:Rights={copyright_text}",
                    f"-IPTC:CopyrightNotice={copyright_text}",
                ]
            )
        else:
            cmd.extend(
                [
                    f"-Title={title}",
                    f"-ObjectName={title}",
                    f"-Description={description}",
                    f"-Caption-Abstract={description}",
                    f"-ImageDescription={description}",
                    f"-Copyright={copyright_text}",
                    f"-Rights={copyright_text}",
                ]
            )
        if author:
            if is_eps:
                cmd.extend([f"-XMP:Creator={author}", f"-IPTC:By-line={author}"])
            else:
                cmd.extend(
                    [
                        f"-By-line={author}",
                        f"-Creator={author}",
                        f"-Credit={author}",
                        f"-Artist={author}",
                    ]
                )
        for kw in keywords:
            if is_eps:
                cmd.extend([f"-IPTC:Keywords={kw}", f"-XMP:Subject={kw}"])
            else:
                cmd.extend([f"-Keywords={kw}", f"-Subject={kw}"])
        cmd.append(file_path)

        try:
            result = _run_exiftool_resilient(cmd, timeout=60, file_path=file_path)
        except subprocess.TimeoutExpired:
            print(f"[SKIP ERROR] {os.path.basename(file_path)}: ExifTool Timeout")
            log_failed_file(
                os.path.dirname(file_path),
                os.path.basename(file_path),
                "ExifTool: Timeout",
            )
            return False
        except ToolExecutionError as e:
            _log_exiftool_failure(file_path, cmd, e.result)
            log_failed_file(
                os.path.dirname(file_path),
                os.path.basename(file_path),
                f"ExifTool: {(e.result.stderr or '').strip()}",
            )
            return False
        except (OSError, ValueError) as e:
            print(f"[SKIP ERROR] {os.path.basename(file_path)}: ExifTool - {e}")
            log_failed_file(
                os.path.dirname(file_path),
                os.path.basename(file_path),
                f"ExifTool: {e}",
            )
            return False
        if result.returncode != 0:
            _log_exiftool_failure(file_path, cmd, result)
            log_failed_file(
                os.path.dirname(file_path),
                os.path.basename(file_path),
                f"ExifTool: {result.stderr.strip()} | Stdout: {result.stdout}",
            )
            return False
        return True

    def _embed_svg_metadata(
        self,
        file_path: str,
        title: str,
        description: str,
        keywords: list[str],
        copyright_text: str,
        author: str = "",
    ) -> bool:
        try:
            ET.register_namespace("", "http://www.w3.org/2000/svg")
            ET.register_namespace("dc", "http://purl.org/dc/elements/1.1/")
            tree = ET.parse(file_path)
            root = tree.getroot()
            title_el = ET.Element("{http://www.w3.org/2000/svg}title")
            title_el.text = title
            desc_el = ET.Element("{http://www.w3.org/2000/svg}desc")
            desc_el.text = description
            root.insert(0, desc_el)
            root.insert(0, title_el)

            if author or copyright_text:
                metadata_el = ET.Element("{http://www.w3.org/2000/svg}metadata")
                rdf_el = ET.Element("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF")
                work_el = ET.Element("{http://purl.org/dc/elements/1.1/}Work")
                if author:
                    creator_el = ET.Element("{http://purl.org/dc/elements/1.1/}creator")
                    creator_el.text = author
                    work_el.append(creator_el)
                if copyright_text:
                    rights_el = ET.Element("{http://purl.org/dc/elements/1.1/}rights")
                    rights_el.text = copyright_text
                    work_el.append(rights_el)
                rdf_el.append(work_el)
                metadata_el.append(rdf_el)
                root.insert(0, metadata_el)

            tree.write(file_path, encoding="utf-8", xml_declaration=True)
            return True
        except (OSError, ValueError) as e:
            print(f"[SKIP ERROR] {os.path.basename(file_path)}: SVG metadata - {e}")
            log_failed_file(
                os.path.dirname(file_path), os.path.basename(file_path), f"SVG: {e}"
            )
            return False