"""Batch Metadata Find & Replace dialog. Extracted from AppWindow.open_batch_replace."""

import os

import customtkinter as ctk

from backend.core.config_manager import get_file_hash, get_cached_metadata, set_cached_metadata
from packages.shared_utils.csv_exporter import generate_microstock_csvs
from ui.theme import C, _btn, _combo, _entry, _label


def show_batch_replace(app):
    target_dir = app.input_dir.get()
    if not target_dir or not os.path.isdir(target_dir):
        app.log("Set Folder first to run batch replace.", "error")
        return

    dialog = ctk.CTkToplevel(app)
    dialog.title("Batch Metadata Find & Replace")
    dialog.geometry("400x420")
    dialog.configure(fg_color=C["bg"])
    dialog.transient(app)
    dialog.grab_set()

    _label(dialog, "Target Field").pack(padx=12, pady=(12, 2), anchor="w")
    field_cb = _combo(dialog, ["All Fields", "Title", "Description", "Keywords"])
    field_cb.pack(fill="x", padx=12, pady=2)

    _label(dialog, "Find Text").pack(padx=12, pady=(10, 2), anchor="w")
    find_entry = _entry(dialog)
    find_entry.pack(fill="x", padx=12, pady=2)

    _label(dialog, "Replace With").pack(padx=12, pady=(10, 2), anchor="w")
    repl_entry = _entry(dialog)
    repl_entry.pack(fill="x", padx=12, pady=2)

    match_case = ctk.BooleanVar(value=False)
    whole_word = ctk.BooleanVar(value=False)

    opts_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    opts_frame.pack(fill="x", padx=12, pady=10)
    ctk.CTkCheckBox(
        opts_frame, text="Match Case", variable=match_case, fg_color=C["accent"]
    ).pack(side="left", padx=(0, 10))
    ctk.CTkCheckBox(
        opts_frame,
        text="Whole Word Only",
        variable=whole_word,
        fg_color=C["accent"],
    ).pack(side="left")

    status_lbl = ctk.CTkLabel(
        dialog, text="", text_color=C["warn"], font=ctk.CTkFont(size=11)
    )
    status_lbl.pack(pady=5)

    def run_replace():
        f_text = find_entry.get()
        if not f_text:
            return
        r_text = repl_entry.get()
        field = field_cb.get()
        mc = match_case.get()
        ww = whole_word.get()

        import re

        flags = 0 if mc else re.IGNORECASE
        pattern_str = rf"\b{re.escape(f_text)}\b" if ww else re.escape(f_text)
        try:
            regex = re.compile(pattern_str, flags)
        except re.error as e:
            status_lbl.configure(text=f"Invalid Regex: {e}", text_color=C["error"])
            return

        status_lbl.configure(text="Processing...", text_color=C["warn"])
        dialog.update()

        count = 0
        # Parse all output CSVs in subdirectories
        for root, _, files in os.walk(target_dir):
            for fname in files:
                # we modify cache AND embed via processor
                if app._is_allowed_file(fname):
                    fpath = os.path.join(root, fname)
                    fhash = get_file_hash(fpath)
                    meta = get_cached_metadata(fhash)
                    if not meta:
                        continue

                    changed = False

                    def _repl(text):
                        if not text:
                            return text
                        new_t, n = regex.subn(r_text, text)
                        nonlocal changed, count
                        if n > 0:
                            changed = True
                            count += n
                        return new_t

                    if field in ("All Fields", "Title"):
                        meta["title"] = _repl(meta.get("title", ""))
                    if field in ("All Fields", "Description"):
                        meta["description"] = _repl(meta.get("description", ""))
                    if field in ("All Fields", "Keywords"):
                        kws = meta.get("keywords", [])
                        new_kws = []
                        for k in kws:
                            replaced_k = _repl(k)
                            # if replaced to empty string, drop it
                            if replaced_k.strip():
                                new_kws.append(replaced_k)
                        meta["keywords"] = new_kws

                    if changed:
                        set_cached_metadata(fhash, meta)
                        app.processor.embed_metadata(
                            fpath,
                            meta["title"],
                            meta["description"],
                            meta["keywords"],
                            app._get_copyright_text(),
                            app.author_entry.get().strip(),
                        )

                        # update sub-dir csv
                        sub_dir = os.path.dirname(fpath)
                        temp_master = os.path.join(sub_dir, "metadata_output.csv")
                        import csv

                        try:
                            with open(
                                temp_master, "w", newline="", encoding="utf-8"
                            ) as tf:
                                tw = csv.writer(tf)
                                tw.writerow(
                                    ["Filename", "Title", "Description", "Keywords"]
                                )
                                tw.writerow(
                                    [
                                        fname,
                                        meta["title"],
                                        meta["description"],
                                        ",".join(meta["keywords"]),
                                    ]
                                )
                        except OSError:
                            pass

        generate_microstock_csvs(target_dir)

        # also update UI if current file is active
        if app.current_edit_hash:
            m = get_cached_metadata(app.current_edit_hash)
            if m:
                app._save_snapshot()
                app.edit_title_var.set(m.get("title", ""))
                app.edit_desc_var.set(m.get("description", ""))
                app.edit_kws_var.set(", ".join(m.get("keywords", [])))

        app.log(
            f"Batch Replace: Replaced {count} occurrences of '{f_text}'.", "success"
        )
        dialog.destroy()

    _btn(dialog, "Replace All", C["warn"], C["warn_h"], command=run_replace).pack(
        side="bottom", pady=16, padx=12, fill="x"
    )