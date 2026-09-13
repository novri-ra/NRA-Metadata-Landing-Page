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
from pathlib import Path

from backend.processors._tools import (  # noqa: F401 (re-exported)
    exiftool_flags,
    get_base_path,
    get_tool_path,
    log_failed_file,
)

logger = logging.getLogger(__name__)


def get_exiftool_path() -> str | None:
    """Resolve the ExifTool binary; ``None`` when it cannot be found."""
    return get_tool_path("exiftool")


def _prepare_target(file_path: str) -> None:
    """Make the target writable and free it from stale ExifTool temp files.

    Stock-downloaded files often carry a read-only attribute that survives
    ``shutil.move``; ``-overwrite_original`` then fails to rename the temp
    file over the original on Windows. A failed rename also leaves a stale
    ``<file>_exiftool_tmp`` behind, and ExifTool refuses to proceed while it
    exists -- so both must be cleared before every run.
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
    try:
        stale = file_path + "_exiftool_tmp"
        if os.path.exists(stale):
            os.chmod(stale, stat.S_IREAD | stat.S_IWRITE)
            os.remove(stale)
    except OSError:
        pass


def _staging_root() -> str | None:
    """Writable root for staging copies, on the local/system drive.

    Windows temp is preferred on native builds; under WSL the temp dir is not
    reachable by the Windows exe, so the project cache (on ``/mnt/<drive>``) is
    used instead so ``_to_cli_path`` can translate it back to a Windows path.
    """
    tmp = Path(tempfile.gettempdir())
    candidates: list[Path] = []
    if os.name == "nt" or str(tmp).startswith("/mnt/"):
        candidates.append(tmp / "nra_exiftool_staging")
    candidates.append(Path(get_base_path()) / "cache" / "exiftool_staging")
    for c in candidates:
        try:
            c.mkdir(parents=True, exist_ok=True)
            return str(c)
        except OSError:
            continue
    return None


def _stage_copy(file_path: str) -> str | None:
    """Copy the target into a writable staging area so ExifTool can create its
    ``_exiftool_tmp`` there even when the destination folder rejects writes."""
    root = _staging_root()
    if not root:
        return None
    p = Path(file_path)
    staged = Path(root) / f"{p.stem}.{os.getpid()}{p.suffix}"
    try:
        if staged.exists():
            os.chmod(staged, stat.S_IREAD | stat.S_IWRITE)
            os.remove(staged)
        shutil.copy2(file_path, staged)
        os.chmod(staged, stat.S_IREAD | stat.S_IWRITE)
        return str(staged)
    except OSError:
        return None


def _replace_original(original: str, staged: str) -> None:
    """Move the metadata-embedded staged copy back over the original."""
    parent = os.path.dirname(original)
    if parent:
        try:
            os.chmod(parent, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
        except OSError:
            pass
    try:
        os.chmod(original, stat.S_IREAD | stat.S_IWRITE)
    except OSError:
        pass
    stale = original + "_exiftool_tmp"
    try:
        if os.path.exists(stale):
            os.chmod(stale, stat.S_IREAD | stat.S_IWRITE)
            os.remove(stale)
    except OSError:
        pass
    try:
        os.remove(original)
    except OSError:
        pass
    shutil.move(staged, original)


def _run_with_staging_fallback(
    file_path: str, cmd: list, timeout: int
) -> subprocess.CompletedProcess:
    """Run ExifTool in place, retrying through a local staging copy when the
    target directory rejects ``_exiftool_tmp`` creation (read-only / external
    drive permission issues). ExifTool always creates its temp file in the
    same directory as the target, so when that fails the only reliable path is
    to write in a writable directory and move the result back."""
    result = _run_exiftool(cmd, timeout)
    if result.returncode == 0:
        return result
    err = result.stderr or ""
    if "Error creating file" not in err and "_exiftool_tmp" not in err:
        return result
    staged = _stage_copy(file_path)
    if not staged:
        print(
            f"[EXIFTOOL] {os.path.basename(file_path)}: in-place temp denied "
            "and staging fallback unavailable"
        )
        return result
    print(
        f"[EXIFTOOL] {os.path.basename(file_path)}: in-place temp denied, "
        "embedding via local staging copy"
    )
    staged_cmd = cmd[:-1] + [staged]
    staged_result = _run_exiftool(staged_cmd, timeout)
    if staged_result.returncode != 0 or not os.path.isfile(staged):
        return staged_result
    try:
        _replace_original(file_path, staged)
        print(
            f"[EXIFTOOL] {os.path.basename(file_path)}: "
            "staged result moved back to original"
        )
    except OSError as e:
        print(f"[EXIFTOOL] {os.path.basename(file_path)}: move-back failed: {e}")
        try:
            os.remove(staged)
        except OSError:
            pass
    return staged_result


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


def _log_exiftool_failure(
    file_path: str, cmd: list, result: subprocess.CompletedProcess
) -> None:
    """Expose the raw ExifTool failure to the console and logger.

    stderr was previously swallowed by a ``CalledProcessError`` decode path,
    so every EPS embed failed silently. Dump exit code, full command, stderr
    and stdout verbatim.
    """
    print(f"\n[EXIFTOOL ERROR DETAIL] Exit Code: {result.returncode}", flush=True)
    print(f"[EXIFTOOL CMD] {' '.join(cmd)}", flush=True)
    print(f"[EXIFTOOL STDERR] {result.stderr}", flush=True)
    print(f"[EXIFTOOL STDOUT] {result.stdout}\n", flush=True)
    logger.error(f"[EXIFTOOL] Failed on {file_path}: {result.stderr.strip()}")


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
            result = _run_with_staging_fallback(file_path, cmd, timeout=30)
        except subprocess.TimeoutExpired:
            print(f"[WARN] Sanitizer timeout on {os.path.basename(file_path)}")
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
            result = _run_with_staging_fallback(file_path, cmd, timeout=60)
        except subprocess.TimeoutExpired:
            print(f"[SKIP ERROR] {os.path.basename(file_path)}: ExifTool Timeout")
            log_failed_file(
                os.path.dirname(file_path),
                os.path.basename(file_path),
                "ExifTool: Timeout",
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