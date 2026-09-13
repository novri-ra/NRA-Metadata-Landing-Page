"""Offline re-tag pipeline: CSV -> local asset -> embed metadata via ExifTool (no vision prompt).

Extracted from AppWindow.start_offline_retag / _find_asset / _run_offline_retag.
"""

import os
import threading

import customtkinter as ctk

from backend.core.config_manager import get_file_hash, set_cached_metadata
from backend.processors.media_converter import extract_preview_image
from packages.shared_utils.filter import sanitize_keywords
from ui.theme import C


def start_offline_retag(app):
    csv_path = ctk.filedialog.askopenfilename(
        title="Select metadata CSV", filetypes=[("CSV files", "*.csv")]
    )
    if not csv_path:
        return

    target_dir = app.input_dir.get()
    if not target_dir or not os.path.isdir(target_dir):
        app.log("Set Folder first.", "error")
        return

    app.retag_btn.configure(state="disabled")
    app.start_btn.configure(state="disabled")
    max_kw = app._safe_int(app.max_kw_entry.get(), 50)
    author = app.author_entry.get().strip()
    copyright_text = app._get_copyright_text()
    threading.Thread(
        target=_run_offline_retag,
        args=(app, csv_path, target_dir, max_kw, author, copyright_text),
        daemon=True,
    ).start()


def _run_offline_retag(
    app, csv_path: str, target_dir: str, max_kw: int, author: str, copyright_text: str
):
    import csv as csv_mod

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            rows = list(csv_mod.DictReader(f))
    except (OSError, KeyError, ValueError) as e:
        app.log(f"CSV read error: {e}", "error")
        app._call_main(app.retag_btn.configure, state="normal")
        app._call_main(app.start_btn.configure, state="normal")
        return

    if not rows:
        app.log("CSV empty.", "error")
        app._call_main(app.retag_btn.configure, state="normal")
        app._call_main(app.start_btn.configure, state="normal")
        return

    total = len(rows)
    success = 0
    app.log(
        f"Offline Re-Tag: {total} rows from {os.path.basename(csv_path)}", "info"
    )
    app._call_main(app.progress_bar.set, 0)

    for i, row in enumerate(rows):
        filename = row.get("Filename", "").strip()
        if not filename:
            app.log(f"Row {i + 1}: missing Filename", "error")
            continue

        asset_path = _find_asset(target_dir, filename)
        if not asset_path:
            app.log(f"{filename} not found in folder", "error")
            continue

        title = row.get("Title", "").strip()
        desc = row.get("Description", "").strip()
        raw_kws = [
            k.strip() for k in row.get("Keywords", "").split(",") if k.strip()
        ]
        keywords = sanitize_keywords(raw_kws, max_kw)

        if app.processor.embed_metadata(
            asset_path,
            title,
            desc,
            keywords,
            copyright_text,
            author,
        ):
            file_hash = get_file_hash(asset_path)
            meta = {"title": title, "description": desc, "keywords": keywords}
            if not meta.get("is_fallback"):
                set_cached_metadata(file_hash, meta)
            app.log(f"[OFFLINE SUCCESS] {filename}", "success")
            success += 1

            # Sync UI with the imported metadata for the inspector
            preview_img = extract_preview_image(asset_path)
            if preview_img:
                app.update_preview(
                    preview_img,
                    "Imported CSV",
                    C["success"],
                    meta,
                    asset_path,
                    file_hash,
                )
        else:
            app.log(f"[OFFLINE FAIL] {filename}", "error")

        app._call_main(app.progress_bar.set, (i + 1) / total)

    app.log(f"Successfully tagged {success}/{total} files from CSV.", "success")
    app._call_main(app.retag_btn.configure, state="normal")
    app._call_main(app.start_btn.configure, state="normal")


def _find_asset(target_dir: str, filename: str) -> str | None:
    for root, _dirs, files in os.walk(target_dir):
        if filename in files:
            return os.path.join(root, filename)
    return None