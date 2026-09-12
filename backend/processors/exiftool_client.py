"""ExifTool client for embedding IPTC/XMP metadata and stripping AI provenance.

Extracted from ``packages/media_processor/embedder.py``; the class was renamed
``MediaProcessor`` -> ``ExifToolClient``. Tool resolution lives in
``backend.processors._tools``.
"""

import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from backend.processors._tools import get_tool_path, log_failed_file


class ExifToolClient:
    def sanitize_ai_metadata(self, file_path: str) -> bool:
        """Strip AI provenance and generation tags while preserving Adobe/creative app metadata."""
        exiftool_path = get_tool_path("exiftool")
        is_png = os.path.splitext(file_path)[1].lower() == ".png"
        cmd = [
            exiftool_path,
            "-overwrite_original",
            "-m",
        ]
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
                "-XMP:AIContentGenerator=",
                "-XMP:DigitalSourceType=",
                file_path,
            ]
        )
        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(cmd, check=True, capture_output=True, timeout=30)
            return True
        except subprocess.TimeoutExpired:
            print(f"[WARN] Sanitizer timeout on {os.path.basename(file_path)}")
            return False
        except subprocess.CalledProcessError as e:
            err_msg = (
                e.stderr.decode(errors="replace")
                if isinstance(e.stderr, bytes)
                else str(e.stderr)
            )
            print(f"[WARN] Sanitizer error on {os.path.basename(file_path)}: {err_msg}")
            return False
        except (OSError, ValueError) as e:
            # We don't hard fail if sanitization fails (e.g. exiftool error on a specific file type)
            print(f"[WARN] Sanitizer error on {os.path.basename(file_path)}: {e}")
            return False

    def embed_metadata(
        self,
        file_path: str,
        title: str,
        description: str,
        keywords: list[str],
        copyright_text: str,
        author: str = "",
    ) -> bool:
        file_path = os.path.abspath(file_path)
        ext = file_path.lower().split(".")[-1]
        if ext == "svg":
            return self._embed_svg_metadata(
                file_path, title, description, keywords, copyright_text, author
            )

        # 1. Sanitize AI metadata first
        self.sanitize_ai_metadata(file_path)

        # 2. Embed new metadata
        exiftool_path = get_tool_path("exiftool")
        cmd = [
            exiftool_path,
            "-overwrite_original",
            f"-Title={title}",
            f"-ObjectName={title}",
            f"-Description={description}",
            f"-Caption-Abstract={description}",
            f"-ImageDescription={description}",
            f"-Copyright={copyright_text}",
            f"-Rights={copyright_text}",
        ]
        if author:
            cmd.extend(
                [
                    f"-By-line={author}",
                    f"-Creator={author}",
                    f"-Credit={author}",
                    f"-Artist={author}",
                ]
            )
        for kw in keywords:
            cmd.extend([f"-Keywords={kw}", f"-Subject={kw}"])
        cmd.append(file_path)

        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=60)
            return True
        except subprocess.TimeoutExpired:
            print(f"[SKIP ERROR] {os.path.basename(file_path)}: ExifTool Timeout")
            log_failed_file(
                os.path.dirname(file_path),
                os.path.basename(file_path),
                "ExifTool: Timeout",
            )
            return False
        except subprocess.CalledProcessError as e:
            err_msg = (
                e.stderr.decode(errors="replace")
                if isinstance(e.stderr, bytes)
                else str(e.stderr)
            )
            print(f"[SKIP ERROR] {os.path.basename(file_path)}: ExifTool - {err_msg}")
            log_failed_file(
                os.path.dirname(file_path),
                os.path.basename(file_path),
                f"ExifTool: {err_msg}",
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