"""ExifTool client for embedding IPTC/XMP metadata and stripping AI provenance.

Extracted from ``packages/media_processor/embedder.py``; the class was renamed
``MediaProcessor`` -> ``ExifToolClient``. Tool resolution lives in
``backend.processors._tools``.
"""

import logging
import os
import re
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
    no_window_kwargs,
)

logger = logging.getLogger(__name__)


def get_exiftool_path() -> str | None:
    """Resolve the ExifTool binary; ``None`` when it cannot be found."""
    return get_tool_path("exiftool")


def _normalize_date_created(date_created: str) -> str:
    """Normalize ``YYYY-MM-DD`` / ``YYYY/MM/DD`` / ``YYYYMMDD`` -> ``YYYYMMDD``."""
    raw = (date_created or "").strip()
    m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", raw)
    if m and re.match(r"^(\d{4})(\d{2})(\d{2})$", raw):
        return raw
    if m:
        return f"{int(m.group(1)):04d}{int(m.group(2)):02d}{int(m.group(3)):02d}"
    m8 = re.match(r"^(\d{4})(\d{2})(\d{2})$", raw)
    return m8.group(0) if m8 else raw


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


def _run_exiftool(
    cmd: list, timeout: int, cwd: str | None = None
) -> subprocess.CompletedProcess:
    """Run ExifTool with fully visible text output.

    The cwd defaults to the ExifTool directory so the bundled Perl wrapper can
    always find its ``exiftool_files`` support modules; an isolated staging run
    pins it to the temp working directory instead. stderr is decoded with
    ``errors="replace"`` so a non-UTF8 native message can never be swallowed by
    a decode exception while surfacing hidden command-line errors.
    """
    exiftool_path = cmd[0]
    if cwd is None:
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
        **no_window_kwargs(),
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


def _build_staged_cmd(cmd: list, staged_path: str) -> list:
    """Rebuild the ExifTool command for an isolated temp copy.

    ``-overwrite_original_in_place`` writes ``<file>_exiftool_tmp`` next to the
    target, which is what the caller's directory blocked. Inside an isolated
    staging dir a plain ``-overwrite_original`` on the copy is what we want,
    and the Windows API mode keeps long-path I/O enabled unconditionally.
    """
    staged_cmd = [
        "-overwrite_original" if arg == "-overwrite_original_in_place" else arg
        for arg in cmd
    ]
    if "-api" not in staged_cmd and os.name == "nt":
        staged_cmd = [staged_cmd[0], "-api", "Windows=1", *staged_cmd[1:]]
    staged_cmd[-1] = staged_path
    return staged_cmd


def _pre_cleanup_temp(file_path: str) -> None:
    """Remove a leftover ``<target>_exiftool_tmp`` from an earlier run."""
    parent = os.path.dirname(file_path) or "."
    tmp = os.path.join(parent, os.path.basename(file_path) + "_exiftool_tmp")
    try:
        if os.path.isfile(tmp):
            os.chmod(tmp, stat.S_IREAD | stat.S_IWRITE)
            os.remove(tmp)
    except OSError:
        pass


def _build_stream_cmd(cmd: list) -> list:
    """Turn a metadata command into a pure STDIN→STDOUT stream.

    The overwrite flags (which force ``<file>_exiftool_tmp`` next to the
    target) are dropped, the trailing file argument is replaced by ``-`` (read
    binary input from STDIN), and ``-o -`` redirects the rewritten binary to
    STDOUT so ExifTool never touches the target directory.
    """
    cleaned = [
        arg
        for arg in cmd
        if arg not in ("-overwrite_original", "-overwrite_original_in_place")
    ]
    return cleaned[:-1] + ["-o", "-", "-"]


def _run_exiftool_stream(
    cmd: list, timeout: int, input_bytes: bytes
) -> subprocess.CompletedProcess:
    """Run ExifTool over a binary pipe: target bytes in on STDIN, the rewritten
    file comes back on STDOUT (bytes), so nothing is written to the filesystem."""
    exiftool_path = cmd[0]
    cwd = os.path.dirname(os.path.abspath(exiftool_path))
    is_exe = str(exiftool_path).lower().endswith(".exe")
    converted_cmd = [cmd[0]] + [_to_cli_path(arg, is_exe) for arg in cmd[1:]]
    return subprocess.run(
        converted_cmd,
        input=input_bytes,
        capture_output=True,
        timeout=timeout,
        cwd=cwd,
        **no_window_kwargs(),
    )


def _run_metadata_write(cmd: list, file_path: str, timeout: int):
    """Write metadata with zero disk-temp usage: stream the file through
    ExifTool's STDIN/STDOUT and write the returned binary back to the target.

    When the stream yields nothing (some formats reject ``-o -``) or errors, a
    controlled fallback runs the classic direct write (with temp-staging if the
    target folder blocks in-place writes).
    """
    _pre_cleanup_temp(file_path)
    try:
        with open(file_path, "rb") as f_in:
            input_bytes = f_in.read()
    except OSError:
        input_bytes = None
    if input_bytes is not None:
        stream_cmd = _build_stream_cmd(cmd)
        try:
            stream = _run_exiftool_stream(stream_cmd, timeout, input_bytes)
            if stream.returncode == 0 and len(stream.stdout or b"") > 0:
                _prepare_target(file_path)
                try:
                    os.chmod(file_path, stat.S_IREAD | stat.S_IWRITE)
                except OSError:
                    pass
                with open(file_path, "wb") as f_out:
                    f_out.write(stream.stdout)
                return stream
        except subprocess.TimeoutExpired:
            raise
        except OSError:
            pass
    return _run_exiftool_resilient(cmd, timeout=timeout, file_path=file_path)


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
        staged_cmd = _build_staged_cmd(cmd, staged_path)
        staged = _run_exiftool(staged_cmd, timeout=timeout, cwd=staged_dir)
        if staged.returncode == 0:
            _prepare_target(staged_path)
            _prepare_target(file_path)
            shutil.copyfile(staged_path, file_path)
            _prepare_target(file_path)
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
    def sanitize_ai_metadata(
        self, file_path: str, is_ai_generated: bool = False
    ) -> bool:
        """Manage AI provenance tags.

        ``is_ai_generated=False`` (human-made): strip internal generator junk
        (PNG prompt/workflow) only; official C2PA manifests and IPTC
        ``DigitalSourceType`` are preserved. ``is_ai_generated=True``: no
        removal args at all, and the IPTC ``trainedAlgorithmicMedia``
        declaration is written explicitly.
        """
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
        if is_ai_generated:
            cmd.extend(
                [
                    "-XMP-iptcExt:DigitalSourceType=http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
                    "-XMP:DigitalSourceType=trainedAlgorithmicMedia",
                ]
            )
        else:
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
            cmd.extend(["-XMP-xmpGImg:all="])
        cmd.append(file_path)
        try:
            result = _run_metadata_write(cmd, file_path, timeout=30)
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
        is_ai_generated: bool = False,
        is_editorial: bool = False,
        city: str = "",
        country: str = "",
        country_code: str = "",
        date_created: str = "",
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

        # 1. Manage AI provenance tags
        self.sanitize_ai_metadata(file_path, is_ai_generated)

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
        if is_editorial:
            exif_date = _normalize_date_created(date_created)
            if is_eps:
                if city:
                    cmd.extend(
                        [f"-XMP-photoshop:City={city}", f"-IPTC:City={city}"]
                    )
                if country:
                    cmd.extend(
                        [
                            f"-XMP-photoshop:Country={country}",
                            f"-IPTC:Country-PrimaryLocationName={country}",
                        ]
                    )
                if country_code:
                    cmd.extend(
                        [
                            f"-XMP-iptcExt:CountryCode={country_code}",
                            f"-IPTC:Country-PrimaryLocationCode={country_code}",
                        ]
                    )
                if exif_date:
                    cmd.extend(
                        [
                            f"-XMP-photoshop:DateCreated={exif_date}",
                            f"-IPTC:DateCreated={exif_date}",
                        ]
                    )
            else:
                if city:
                    cmd.append(f"-City={city}")
                if country:
                    cmd.append(f"-Country={country}")
                if country_code:
                    cmd.append(f"-Country-PrimaryLocationCode={country_code}")
                if exif_date:
                    cmd.append(f"-DateCreated={exif_date}")
        for kw in keywords:
            if is_eps:
                cmd.extend([f"-IPTC:Keywords={kw}", f"-XMP:Subject={kw}"])
            else:
                cmd.extend([f"-Keywords={kw}", f"-Subject={kw}"])
        cmd.append(file_path)

        try:
            result = _run_metadata_write(cmd, file_path, timeout=60)
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
            ET.register_namespace(
                "rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
            )
            tree = ET.parse(file_path)
            root = tree.getroot()
            title_el = ET.Element("{http://www.w3.org/2000/svg}title")
            title_el.text = title
            desc_el = ET.Element("{http://www.w3.org/2000/svg}desc")
            desc_el.text = description
            root.insert(0, desc_el)
            root.insert(0, title_el)

            if author or copyright_text or keywords:
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
                if keywords:
                    subject_el = ET.Element("{http://purl.org/dc/elements/1.1/}subject")
                    bag_el = ET.SubElement(
                        subject_el, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Bag"
                    )
                    for kw in keywords:
                        li_el = ET.SubElement(
                            bag_el, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li"
                        )
                        li_el.text = kw
                    work_el.append(subject_el)
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