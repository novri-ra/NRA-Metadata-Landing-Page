"""Assemble the portable release zip: built app + tools setup helpers.

Kept intentionally small: copy the PyInstaller onedir output next to the
setup scripts and the tools skeleton, then zip the whole root.

Usage:
    python scripts/build_portable.py <dist_dir> <out_zip>

Example:
    python scripts/build_portable.py dist/AutoMetadata-GUI dist/NRA-Metadata-portable.zip
"""

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETUP_HELPERS = ("setup_tools.bat", "setup_tools.ps1")
TOOLS_SKELETON = (
    "exiftool/.gitkeep",
    "ghostscript/bin/.gitkeep",
    "ffmpeg/bin/.gitkeep",
)


def collect_tools_root() -> list[tuple[Path, str]]:
    """Return real tool binaries bundled in tools/ (portable), if any."""
    entries: list[tuple[Path, str]] = []
    tools_root = ROOT / "tools"
    if not tools_root.is_dir():
        return entries
    for rel in TOOLS_SKELETON:
        p = tools_root / rel
        if p.is_file():
            entries.append((p, f"tools/{rel}"))
    return entries


def build(dist_dir: Path, out_zip: Path) -> None:
    if not dist_dir.is_dir():
        raise SystemExit(f"dist dir not found: {dist_dir}")
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for src in sorted(dist_dir.rglob("*")):
            if src.is_file():
                zf.write(src, src.relative_to(dist_dir).as_posix())
        for name in SETUP_HELPERS:
            src = ROOT / "scripts" / name
            if src.is_file():
                zf.write(src, name)
        for src, arc in collect_tools_root():
            zf.write(src, arc)
    print(f"Portable package written: {out_zip} ({out_zip.stat().st_size} bytes)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(1)
    build(Path(sys.argv[1]), Path(sys.argv[2]))