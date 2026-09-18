"""Batch Copy & Apply Metadata dialog. Extracted from AppWindow._open_batch_apply."""

import os

import customtkinter as ctk

from backend.core.config_manager import (
    get_cached_metadata,
    get_file_hash,
    set_cached_metadata,
)
from packages.shared_utils.csv_exporter import generate_microstock_csvs
from ui.theme import C, _btn, _combo, _entry, _label


def show_batch_apply(app):
    target_dir = app.output_dir.get()
    if not target_dir or not os.path.isdir(target_dir):
        return app.log("Set Output Folder first to use Batch Apply.", "error")
    if not app.current_edit_file:
        return app.log("Select a file in the inspector first.", "error")

    dialog = ctk.CTkToplevel(app)
    dialog.title("Batch Copy & Apply Metadata")
    dialog.geometry("400x400")
    dialog.configure(fg_color=C["bg"])
    dialog.transient(app)
    dialog.grab_set()
    dialog.bind("<Escape>", lambda e: dialog.destroy())

    _label(
        dialog,
        "Copy metadata from current file to:",
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
    ).pack(padx=12, pady=(12, 8), anchor="w")

    # Fields to copy
    _label(dialog, "Fields to copy:").pack(padx=12, pady=(4, 2), anchor="w")
    copy_title = ctk.BooleanVar(value=True)
    copy_desc = ctk.BooleanVar(value=True)
    copy_kws = ctk.BooleanVar(value=True)

    fields_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    fields_frame.pack(fill="x", padx=12, pady=2)
    ctk.CTkCheckBox(
        fields_frame, text="Title", variable=copy_title, fg_color=C["accent"]
    ).pack(side="left", padx=(0, 8))
    ctk.CTkCheckBox(
        fields_frame, text="Description", variable=copy_desc, fg_color=C["accent"]
    ).pack(side="left", padx=(0, 8))
    ctk.CTkCheckBox(
        fields_frame, text="Keywords", variable=copy_kws, fg_color=C["accent"]
    ).pack(side="left")

    # Target scope
    _label(dialog, "Apply to:").pack(padx=12, pady=(10, 2), anchor="w")
    scope_var = ctk.StringVar(value="All files in folder")
    _combo(
        dialog,
        [
            "All files in folder",
            "Specific extension only",
            "Files without metadata only",
        ],
        variable=scope_var,
    ).pack(fill="x", padx=12, pady=2)

    _label(dialog, "Extension filter (e.g. .svg .eps):").pack(
        padx=12, pady=(8, 2), anchor="w"
    )
    ext_entry = _entry(dialog, placeholder_text=".svg .eps")
    ext_entry.pack(fill="x", padx=12, pady=2)

    status_lbl = ctk.CTkLabel(
        dialog, text="", text_color=C["warn"], font=ctk.CTkFont(size=11)
    )
    status_lbl.pack(pady=8)

    def run_batch_apply():
        scope = scope_var.get()
        ct, cd, ck = copy_title.get(), copy_desc.get(), copy_kws.get()
        if not (ct or cd or ck):
            status_lbl.configure(
                text="Select at least one field.", text_color=C["error"]
            )
            return

        src_title = app.edit_title_var.get()
        src_desc = app.edit_desc_var.get()
        src_kws = app._get_kws_list()

        ext_filter = None
        if scope == "Specific extension only":
            raw = ext_entry.get().strip()
            if not raw:
                status_lbl.configure(
                    text="Enter extensions to filter.", text_color=C["error"]
                )
                return
            ext_filter = {
                e.strip().lower()
                if e.strip().startswith(".")
                else "." + e.strip().lower()
                for e in raw.split()
            }

        status_lbl.configure(text="Applying...", text_color=C["warn"])

        apply_btn.configure(state="disabled", text="Processing...")
        def _do_apply():
            applied = 0
            skipped = 0
            for root, _, files in os.walk(target_dir):
                for fname in files:
                    if not app._is_allowed_file(fname):
                        continue
                    fpath = os.path.join(root, fname)
                    if fpath == app.current_edit_file:
                        continue

                    # Extension filter
                    if ext_filter:
                        fext = os.path.splitext(fname)[1].lower()
                        if fext not in ext_filter:
                            continue

                    fhash = get_file_hash(fpath)
                    meta = get_cached_metadata(fhash) or {}

                    # Skip files that already have metadata
                    if scope == "Files without metadata only" and (
                        meta.get("title") or meta.get("keywords")
                    ):
                        skipped += 1
                        continue

                    new_title = src_title if ct else meta.get("title", "")
                    new_desc = src_desc if cd else meta.get("description", "")
                    new_kws = list(src_kws) if ck else meta.get("keywords", [])

                    new_meta = {
                        "title": new_title,
                        "description": new_desc,
                        "keywords": new_kws,
                    }
                    set_cached_metadata(fhash, new_meta)
                    app.processor.embed_metadata(
                        fpath,
                        new_title,
                        new_desc,
                        new_kws,
                        app._get_copyright_text(),
                        app.author_entry.get().strip(),
                    )
                    applied += 1

            if applied > 0:
                generate_microstock_csvs(target_dir, app._get_selected_csv_platforms())

            def _update_ui():
                app.log(
                    f"Batch Apply: {applied} files updated, {skipped} skipped.", "success"
                )
                dialog.destroy()
                
            dialog.after(0, _update_ui)

        import threading
        threading.Thread(target=_do_apply, daemon=True).start()

    apply_btn = _btn(
        dialog,
        "Apply to Batch",
        C["accent"],
        C["accent_h"],
        command=run_batch_apply,
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
    )
    apply_btn.pack(fill="x", padx=12, pady=(4, 12), side="bottom")