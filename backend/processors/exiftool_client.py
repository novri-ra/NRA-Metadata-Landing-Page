"""ExifTool client for embedding IPTC/XMP metadata and stripping AI provenance.

Extracted from ``packages/media_processor/embedder.py``; the class was renamed
``MediaProcessor`` -> ``ExifToolClient``. Tool resolution lives in
``backend.processors._tools``.
"""

import atexit
import logging
import os
import re
import shutil
import stat
import subprocess
import tempfile
import threading
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


def _patch_eps_dsc_title(file_path: str, title: str) -> None:
    """Ensure the PostScript header %%Title: matches the real title for Adobe Stock parser."""
    if not title:
        return
    try:
        # Clean title for PostScript ASCII line safety
        safe_title = re.sub(r"[^\x20-\x7E]", "", title).strip()
        with open(file_path, "rb") as f:
            content = f.read()

        pattern = re.compile(rb"^%%Title:\s*.*$", re.MULTILINE)
        replacement = f"%%Title: {safe_title}".encode("ascii", "ignore")

        if pattern.search(content):
            new_content = pattern.sub(replacement, content, count=1)
        else:
            first_line_end = content.find(b"\n")
            if first_line_end != -1:
                new_content = (
                    content[: first_line_end + 1]
                    + replacement
                    + b"\n"
                    + content[first_line_end + 1 :]
                )
            else:
                new_content = content

        if new_content != content:
            with open(file_path, "wb") as f:
                f.write(new_content)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to patch EPS DSC Title: {e}")


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


class ExifToolDaemon:
    """Persistent ExifTool process engine using -stay_open for 3x-5x speedup."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._proc = None
        self._cmd_lock = threading.Lock()
        self._req_counter = 0
        atexit.register(self.shutdown)

    def _is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> bool:
        """Spawn the background ExifTool process."""
        if self._is_alive():
            return True
        exe = get_exiftool_path()
        if not exe:
            return False
        try:
            cwd = os.path.dirname(os.path.abspath(exe))
            # Base persistent flags
            base_cmd = [
                exe,
                "-stay_open", "True",
                "-@", "-",
                "-common_args",
                "-charset", "filename=utf8",
                "-m",
                "-overwrite_original",
            ]
            if os.name == "nt":
                base_cmd.insert(1, "-api")
                base_cmd.insert(2, "Windows=1")
                
            self._proc = subprocess.Popen(
                base_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                cwd=cwd,
                **no_window_kwargs(),
            )
            return True
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to start ExifTool daemon: {e}")
            self._proc = None
            return False

    def shutdown(self):
        """Gracefully terminate persistent ExifTool daemon."""
        with self._cmd_lock:
            if self._proc and self._proc.poll() is None:
                try:
                    self._proc.stdin.write("-stay_open\nFalse\n")
                    self._proc.stdin.flush()
                    self._proc.wait(timeout=2)
                except Exception:  # noqa: BLE001
                    try:
                        self._proc.kill()
                    except Exception:  # noqa: BLE001
                        pass
                finally:
                    self._proc = None

    def execute_command(self, cmd_args: list, timeout: int = 30, cwd: str | None = None) -> subprocess.CompletedProcess:
        """Send command to persistent daemon and await response."""
        with self._cmd_lock:
            # Auto-healing / crash recovery: revive if dead
            if not self._is_alive():
                if not self.start():
                    raise RuntimeError("ExifTool daemon is not running and failed to start.")

            self._req_counter += 1
            seq = self._req_counter
            ready_marker = f"{{ready{seq}}}"

            # Filter out command binary and standard common_args already wired
            filtered_args = []
            is_exe = str(cmd_args[0]).lower().endswith(".exe")
            for i, arg in enumerate(cmd_args[1:]):
                clean_arg = _to_cli_path(arg, is_exe)
                # Skip duplicate common args to keep payload lean
                if clean_arg in ("-overwrite_original", "-overwrite_original_in_place", "-m", "-charset", "filename=utf8"):
                    continue
                if clean_arg == "-api" and i+2 < len(cmd_args) and cmd_args[i+2] == "Windows=1":
                    continue
                if clean_arg == "Windows=1" and i > 0 and cmd_args[i] == "-api":
                    continue
                
                # Make target path absolute relative to cwd if needed
                if i == len(cmd_args) - 2 and not clean_arg.startswith("-"):
                    if cwd and not os.path.isabs(clean_arg):
                        clean_arg = os.path.join(cwd, clean_arg)
                    clean_arg = os.path.abspath(clean_arg)
                
                filtered_args.append(clean_arg)

            def _write_args():
                for arg in filtered_args:
                    self._proc.stdin.write(f"{arg}\n")
                self._proc.stdin.write(f"-execute{seq}\n")
                self._proc.stdin.flush()

            try:
                _write_args()
            except (BrokenPipeError, OSError) as e:
                # Handle crash during write -> restart once
                logger.warning(f"ExifTool daemon broken pipe detected: {e}. Restarting...")
                self.start()
                if not self._is_alive():
                    raise RuntimeError(f"ExifTool daemon crash recovery failed: {e}")
                _write_args()

            # Read stdout line by line until {readySEQ} is encountered
            output_lines = []
            import time
            start_time = time.time()
            
            while True:
                if time.time() - start_time > timeout:
                    self.shutdown()
                    raise subprocess.TimeoutExpired(cmd_args, timeout)
                    
                line = self._proc.stdout.readline()
                if not line:
                    break
                if ready_marker in line:
                    break
                output_lines.append(line)

            stdout_text = "".join(output_lines)
            
            # Detect errors in output for returncode approximation
            lowered = stdout_text.lower()
            returncode = 0
            if "error:" in lowered or "error creating file" in lowered or "permission denied" in lowered or "access is denied" in lowered:
                returncode = 1

            return subprocess.CompletedProcess(
                args=cmd_args,
                returncode=returncode,
                stdout=stdout_text,
                stderr="",
            )

def _run_exiftool(
    cmd: list, timeout: int, cwd: str | None = None
) -> subprocess.CompletedProcess:
    """Run ExifTool using the persistent daemon. Falls back to subprocess."""
    exiftool_path = cmd[0]
    if cwd is None:
        cwd = os.path.dirname(os.path.abspath(exiftool_path))
    
    file_name = os.path.basename(cmd[-1]) if cmd else ""
    logger.info(f"[{file_name}] [DEBUG] Executing ExifTool daemon command...")
    
    daemon = ExifToolDaemon()
    try:
        res = daemon.execute_command(cmd, timeout=timeout, cwd=cwd)
        logger.info(f"[{file_name}] [DEBUG] ExifTool daemon completed with code {res.returncode}")
        return res
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Daemon execution failed: {e}, falling back to subprocess.")
        is_exe = str(exiftool_path).lower().endswith(".exe")
        converted_cmd = [cmd[0]] + [_to_cli_path(arg, is_exe) for arg in cmd[1:]]
        res = subprocess.run(
            converted_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            **no_window_kwargs(), check=False,
        )
        logger.info(f"[{file_name}] [DEBUG] ExifTool fallback completed with code {res.returncode}")
        return res


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
    cmd: list, timeout: int, input_source: str | bytes | None = None, input_bytes: bytes | None = None
) -> subprocess.CompletedProcess:
    """Run ExifTool over a binary pipe: target bytes in on STDIN, the rewritten
    file comes back on STDOUT (bytes), so nothing is written to the filesystem."""
    exiftool_path = cmd[0]
    cwd = os.path.dirname(os.path.abspath(exiftool_path))
    is_exe = str(exiftool_path).lower().endswith(".exe")
    converted_cmd = [cmd[0]] + [_to_cli_path(arg, is_exe) for arg in cmd[1:]]
    
    source = input_bytes if input_bytes is not None else input_source
    file_obj = None
    input_data = None
    
    if isinstance(source, bytes):
        stdin_arg = subprocess.PIPE
        input_data = source
    elif isinstance(source, (str, os.PathLike)) and os.path.isfile(source):
        file_obj = open(source, "rb")
        stdin_arg = file_obj
    else:
        stdin_arg = subprocess.PIPE

    try:
        with subprocess.Popen(
            converted_cmd,
            stdin=stdin_arg,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            text=False,
            **no_window_kwargs(),
        ) as proc:
            try:
                out_b, err_b = proc.communicate(input=input_data, timeout=timeout)  # type: ignore
                if isinstance(out_b, str): out_b = out_b.encode()
                if isinstance(err_b, str): err_b = err_b.encode()
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                raise
            except OSError:
                proc.kill()
                out_b, err_b = b"", b""
                
            return subprocess.CompletedProcess(
                args=converted_cmd, returncode=proc.returncode, stdout=out_b, stderr=err_b
            )
    finally:
        if file_obj:
            file_obj.close()


def _run_metadata_write(cmd: list, file_path: str, timeout: int):
    """Write metadata with zero disk-temp usage: stream the file through
    ExifTool's STDIN/STDOUT and write the returned binary back to the target.

    When the stream yields nothing (some formats reject ``-o -``) or errors, a
    controlled fallback runs the classic direct write (with temp-staging if the
    target folder blocks in-place writes).
    """
    # Disable streaming fallback entirely to prevent subprocess deadlock on Windows
    # Stream method was freezing on EPS files when ExifTool was blocked or piped buffers filled up.
    # Now defaults strictly to the direct robust subprocess run.
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
            logger.info(
                f"[TEMP-STAGED] {os.path.basename(file_path)}: ExifTool ditulis "
                f"via temp folder ({tempfile.gettempdir()}) lalu disalin balik."
            )
            return staged
        raise ToolExecutionError(
            f"ExifTool masih gagal pada salinan temp {os.path.basename(file_path)}",
            staged,
        )
    except (OSError, ValueError) as e:
        logger.warning(f"[WARN] Temp staging fallback gagal untuk {os.path.basename(file_path)}: {e}")
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
    logger.debug(block)
    logger.error("%s failed on %s:\n%s", "ExifTool", file_path, block)


class ExifToolClient:
    def sanitize_ai_metadata(
        self,
        file_path: str,
        is_ai_generated: bool = False,
        ai_system_name: str = "",
        ai_system_version: str = "",
    ) -> bool:
        """Strip AI generator junk and provenance tags before injection."""
        file_path = os.path.normpath(os.path.abspath(file_path))
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        _prepare_target(file_path)
        exiftool_path = get_exiftool_path()
        if not exiftool_path or not os.path.isfile(exiftool_path):
            logger.error(f"[EXIFTOOL ERROR] Binary tidak ditemukan di: {exiftool_path}")
            return False
            
        cmd = [exiftool_path]
        cmd.extend(exiftool_flags(exiftool_path))
        
        # Unconditionally strip AI metadata and generation parameters
        cmd.extend([
            "-XMP-c2pa:all=",
            "-XMP-iptcExt:DigitalSourceType=",
            "-XMP:Credit=",
            "-PNG:Parameters=",
            "-PNG:Prompt=",
            "-PNG:Workflow=",
            "-PNG:Software=",
            "-EXIF:Software=",
            "-XMP:History=",
            "-XMP:SoftwareAgent=",
            "-XMP:Description=",
            "-UserComment=",
            "-XMP-xmpGImg:all=",
        ])
        
        # If it is officially declared as AI generated by the user, we rewrite the IPTC standard
        if is_ai_generated:
            cmd.extend([
                "-XMP-iptcExt:DigitalSourceType=http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
                "-XMP:DigitalSourceType=trainedAlgorithmicMedia",
            ])
            if ai_system_name:
                cmd.append(f"-XMP-iptcExt:AISystemUsed={ai_system_name}")
            if ai_system_version:
                cmd.append(f"-XMP-iptcExt:AISystemVersionUsed={ai_system_version}")
                
        cmd.append(file_path)
        try:
            result = _run_metadata_write(cmd, file_path, timeout=15)
        except subprocess.TimeoutExpired:
            logger.warning(f"[WARN] Sanitizer timeout on {os.path.basename(file_path)}")
            return False
        except ToolExecutionError as e:
            _log_exiftool_failure(file_path, cmd, e.result)
            return False
        except (OSError, ValueError) as e:
            # We don't hard fail if sanitization fails (e.g. exiftool error on a specific file type)
            logger.warning(f"[WARN] Sanitizer error on {os.path.basename(file_path)}: {e}")
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
        ai_system_name: str = "",
        ai_system_version: str = "",
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
        self.sanitize_ai_metadata(
            file_path, is_ai_generated, ai_system_name, ai_system_version
        )

        # 2. Embed new metadata
        exiftool_path = get_exiftool_path()
        if not exiftool_path or not os.path.isfile(exiftool_path):
            err_msg = f"[EXIFTOOL ERROR] Binary tidak ditemukan di: {exiftool_path}"
            logger.error(err_msg)
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
                    f"-Title={title}",
                    f"-XMP-dc:Title={title}",
                    f"-IPTC:ObjectName={title}",
                    f"-IPTC:Headline={title}",
                    f"-XMP-photoshop:Headline={title}",
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
            result = _run_metadata_write(cmd, file_path, timeout=15)
        except subprocess.TimeoutExpired:
            logger.error(f"[SKIP ERROR] {os.path.basename(file_path)}: ExifTool Timeout")
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
            logger.error(f"[SKIP ERROR] {os.path.basename(file_path)}: ExifTool - {e}")
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
            
        if is_eps:
            _patch_eps_dsc_title(file_path, title)
            
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
            logger.error(f"[SKIP ERROR] {os.path.basename(file_path)}: SVG metadata - {e}")
            log_failed_file(
                os.path.dirname(file_path), os.path.basename(file_path), f"SVG: {e}"
            )
            return False