import os
os.chdir(os.path.join(os.environ['USERPROFILE'], 'Saved Games', 'NRA-Metadata'))

with open('apps/desktop/src/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Normalize to LF for patching
has_crlf = '\r\n' in content
content = content.replace('\r\n', '\n')

# 1. Add import for presets
old_import = "from packages.shared_utils.ftp_uploader import FTPClient"
new_import = """from packages.shared_utils.ftp_uploader import FTPClient
from packages.shared_utils.presets import (get_preset_names, get_preset, save_preset as save_kw_preset,
    delete_preset as delete_kw_preset, export_presets, import_presets)"""
assert old_import in content, "Import anchor not found"
content = content.replace(old_import, new_import, 1)
print("OK: import added")

# 2. Add Keyword Presets UI after kw_fmt_row Trim Spacing line
old_kw_fmt_end = """        _btn(kw_fmt_row, "Trim Spacing", C["surface2"], C["border"],
             height=22, width=80, font=ctk.CTkFont(family="Segoe UI", size=9),
             command=self._trim_all_keywords).pack(side="left")

        self.edit_title_var.trace_add("write", lambda *_: self._update_compliance())"""

new_kw_fmt_end = """        _btn(kw_fmt_row, "Trim Spacing", C["surface2"], C["border"],
             height=22, width=80, font=ctk.CTkFont(family="Segoe UI", size=9),
             command=self._trim_all_keywords).pack(side="left")

        # ── Keyword Presets ──
        preset_kw_row = ctk.CTkFrame(inspector, fg_color="transparent")
        preset_kw_row.pack(fill="x", padx=12, pady=(4, 2))
        _label(preset_kw_row, "Keyword Presets", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
               text_color=C["text3"]).pack(side="left")
        _btn(preset_kw_row, "Manage", C["surface2"], C["border"],
             height=22, width=60, font=ctk.CTkFont(family="Segoe UI", size=9),
             command=self._open_keyword_presets).pack(side="right")

        self.edit_title_var.trace_add("write", lambda *_: self._update_compliance())"""

assert old_kw_fmt_end in content, "kw_fmt_end anchor not found"
content = content.replace(old_kw_fmt_end, new_kw_fmt_end, 1)
print("OK: keyword presets UI added")

# 3. Add "Apply to Batch..." button in btn_row area
old_btn_row = """        btn_row = ctk.CTkFrame(inspector, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(4, 12))
        _btn(btn_row, "Dedup", C["surface2"], C["border"],
             height=28, width=80, command=self._dedup_keywords,
             font=ctk.CTkFont(family="Segoe UI", size=11)).pack(side="left", padx=(0, 4))
        _btn(btn_row, "Batch Replace", C["warn"], C["warn_h"],
             height=28, width=100, command=self.open_batch_replace,
             font=ctk.CTkFont(family="Segoe UI", size=11)).pack(side="left", padx=(0, 4))
        _btn(btn_row, "Save & Embed", C["success"], C["success_h"],
             height=28, command=self.save_manual,
             font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")).pack(side="right", expand=True, fill="x")"""

new_btn_row = """        btn_row = ctk.CTkFrame(inspector, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(4, 4))
        _btn(btn_row, "Dedup", C["surface2"], C["border"],
             height=28, width=80, command=self._dedup_keywords,
             font=ctk.CTkFont(family="Segoe UI", size=11)).pack(side="left", padx=(0, 4))
        _btn(btn_row, "Batch Replace", C["warn"], C["warn_h"],
             height=28, width=100, command=self.open_batch_replace,
             font=ctk.CTkFont(family="Segoe UI", size=11)).pack(side="left", padx=(0, 4))
        _btn(btn_row, "Save & Embed", C["success"], C["success_h"],
             height=28, command=self.save_manual,
             font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")).pack(side="right", expand=True, fill="x")

        btn_row2 = ctk.CTkFrame(inspector, fg_color="transparent")
        btn_row2.pack(fill="x", padx=12, pady=(0, 12))
        _btn(btn_row2, "Apply to Batch...", C["violet"], C["violet_h"],
             height=28, command=self._open_batch_apply,
             font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")).pack(fill="x")"""

assert old_btn_row in content, "btn_row anchor not found"
content = content.replace(old_btn_row, new_btn_row, 1)
print("OK: batch apply button added")

# 4. Add methods before the log method
old_log = """    # ── Logging ──────────────────────────────────────────────────────────
    # ── Blacklist Manager ───────────────────────────────────────────────"""

new_log = """    # ── Keyword Presets ──────────────────────────────────────────────────
    def _open_keyword_presets(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Keyword Presets")
        dialog.geometry("420x480")
        dialog.configure(fg_color=C["bg"])
        dialog.transient(self)
        dialog.grab_set()

        _label(dialog, "Save Current Keywords as Preset",
               font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")).pack(padx=12, pady=(12, 4), anchor="w")

        save_row = ctk.CTkFrame(dialog, fg_color="transparent")
        save_row.pack(fill="x", padx=12, pady=2)
        name_entry = _entry(save_row, placeholder_text="Preset name...")
        name_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))

        def do_save():
            n = name_entry.get().strip()
            if not n: return
            kws = self._get_kws_list()
            save_kw_preset(n, kws)
            name_entry.delete(0, "end")
            refresh()
            self.log(f"Saved keyword preset: {n} ({len(kws)} keywords)", "info")

        _btn(save_row, "Save", C["accent"], C["accent_h"], width=60, command=do_save).pack(side="right")

        _divider(dialog).pack(fill="x", padx=12, pady=(8, 4))
        _label(dialog, "Saved Presets",
               font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")).pack(padx=12, pady=(4, 4), anchor="w")

        list_frame = ctk.CTkScrollableFrame(dialog, fg_color=C["surface"], corner_radius=CR)
        list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        def refresh():
            for w in list_frame.winfo_children():
                w.destroy()
            for pname in get_preset_names():
                row = ctk.CTkFrame(list_frame, fg_color="transparent")
                row.pack(fill="x", pady=1)
                kws = get_preset(pname)
                ctk.CTkLabel(row, text=f"{pname}  ({len(kws)} kw)",
                             text_color=C["text"], font=ctk.CTkFont(size=11)).pack(side="left", padx=4)

                ctk.CTkButton(row, text="\\u00d7", width=20, height=20, fg_color="transparent",
                              text_color=C["error"], hover_color=C["surface2"],
                              command=lambda n=pname: [delete_kw_preset(n), refresh()]).pack(side="right", padx=2)

                ctk.CTkButton(row, text="+ Append", width=60, height=20,
                              fg_color=C["surface2"], hover_color=C["border"],
                              font=ctk.CTkFont(size=9),
                              command=lambda n=pname: self._apply_preset_kws(n, "append")).pack(side="right", padx=2)

                ctk.CTkButton(row, text="Replace", width=55, height=20,
                              fg_color=C["accent"], hover_color=C["accent_h"],
                              font=ctk.CTkFont(size=9),
                              command=lambda n=pname: self._apply_preset_kws(n, "replace")).pack(side="right", padx=2)

        refresh()

        io_row = ctk.CTkFrame(dialog, fg_color="transparent")
        io_row.pack(fill="x", padx=12, pady=(0, 12))

        def do_import():
            path = ctk.filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
            if path:
                count = import_presets(path)
                refresh()
                self.log(f"Imported {count} keyword presets.", "info")

        def do_export():
            path = ctk.filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
            if path:
                export_presets(path)
                self.log("Keyword presets exported.", "info")

        _btn(io_row, "Import .json", C["surface2"], C["border"], command=do_import).pack(side="left", expand=True, padx=(0, 4))
        _btn(io_row, "Export .json", C["surface2"], C["border"], command=do_export).pack(side="right", expand=True, padx=(4, 0))

    def _apply_preset_kws(self, name, mode):
        kws = get_preset(name)
        if not kws: return
        self._save_snapshot()
        if mode == "replace":
            self._set_kws_list(kws)
        else:
            existing = self._get_kws_list()
            existing_lower = {k.lower() for k in existing}
            merged = existing + [k for k in kws if k.lower() not in existing_lower]
            self._set_kws_list(merged)
        self.log(f"Applied preset '{name}' ({mode})", "info")

    # ── Batch Copy & Apply Metadata ──────────────────────────────────────
    def _open_batch_apply(self):
        target_dir = self.input_dir.get()
        if not target_dir or not os.path.isdir(target_dir):
            return self.log("Set Folder first to use Batch Apply.", "error")
        if not self.current_edit_file:
            return self.log("Select a file in the inspector first.", "error")

        dialog = ctk.CTkToplevel(self)
        dialog.title("Batch Copy & Apply Metadata")
        dialog.geometry("400x400")
        dialog.configure(fg_color=C["bg"])
        dialog.transient(self)
        dialog.grab_set()

        _label(dialog, "Copy metadata from current file to:",
               font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")).pack(padx=12, pady=(12, 8), anchor="w")

        # Fields to copy
        _label(dialog, "Fields to copy:").pack(padx=12, pady=(4, 2), anchor="w")
        copy_title = ctk.BooleanVar(value=True)
        copy_desc = ctk.BooleanVar(value=True)
        copy_kws = ctk.BooleanVar(value=True)

        fields_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        fields_frame.pack(fill="x", padx=12, pady=2)
        ctk.CTkCheckBox(fields_frame, text="Title", variable=copy_title,
                        fg_color=C["accent"]).pack(side="left", padx=(0, 8))
        ctk.CTkCheckBox(fields_frame, text="Description", variable=copy_desc,
                        fg_color=C["accent"]).pack(side="left", padx=(0, 8))
        ctk.CTkCheckBox(fields_frame, text="Keywords", variable=copy_kws,
                        fg_color=C["accent"]).pack(side="left")

        # Target scope
        _label(dialog, "Apply to:").pack(padx=12, pady=(10, 2), anchor="w")
        scope_var = ctk.StringVar(value="All files in folder")
        _combo(dialog, ["All files in folder", "Specific extension only", "Files without metadata only"],
               variable=scope_var).pack(fill="x", padx=12, pady=2)

        _label(dialog, "Extension filter (e.g. .svg .eps):").pack(padx=12, pady=(8, 2), anchor="w")
        ext_entry = _entry(dialog, placeholder_text=".svg .eps")
        ext_entry.pack(fill="x", padx=12, pady=2)

        status_lbl = ctk.CTkLabel(dialog, text="", text_color=C["warn"], font=ctk.CTkFont(size=11))
        status_lbl.pack(pady=8)

        def run_batch_apply():
            scope = scope_var.get()
            ct, cd, ck = copy_title.get(), copy_desc.get(), copy_kws.get()
            if not (ct or cd or ck):
                status_lbl.configure(text="Select at least one field.", text_color=C["error"])
                return

            src_title = self.edit_title_var.get()
            src_desc = self.edit_desc_var.get()
            src_kws = self._get_kws_list()

            ext_filter = None
            if scope == "Specific extension only":
                raw = ext_entry.get().strip()
                if not raw:
                    status_lbl.configure(text="Enter extensions to filter.", text_color=C["error"])
                    return
                ext_filter = {e.strip().lower() if e.strip().startswith('.') else '.' + e.strip().lower()
                              for e in raw.split()}

            status_lbl.configure(text="Applying...", text_color=C["warn"])
            dialog.update()

            applied = 0
            skipped = 0
            for root, _, files in os.walk(target_dir):
                for fname in files:
                    if not self._is_allowed_file(fname):
                        continue
                    fpath = os.path.join(root, fname)
                    if fpath == self.current_edit_file:
                        continue

                    # Extension filter
                    if ext_filter:
                        fext = os.path.splitext(fname)[1].lower()
                        if fext not in ext_filter:
                            continue

                    fhash = get_file_hash(fpath)
                    meta = get_cached_metadata(fhash) or {}

                    # Skip files that already have metadata
                    if scope == "Files without metadata only":
                        if meta.get("title") or meta.get("keywords"):
                            skipped += 1
                            continue

                    new_title = src_title if ct else meta.get("title", "")
                    new_desc = src_desc if cd else meta.get("description", "")
                    new_kws = list(src_kws) if ck else meta.get("keywords", [])

                    new_meta = {"title": new_title, "description": new_desc, "keywords": new_kws}
                    set_cached_metadata(fhash, new_meta)
                    self.processor.embed_metadata(fpath, new_title, new_desc, new_kws,
                                                  self._get_copyright_text(), self.author_entry.get().strip())
                    applied += 1

            if applied > 0:
                generate_microstock_csvs(target_dir, self._get_selected_csv_platforms())

            self.log(f"Batch Apply: {applied} files updated, {skipped} skipped.", "success")
            dialog.destroy()

        _btn(dialog, "Apply to Batch", C["accent"], C["accent_h"],
             command=run_batch_apply,
             font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")).pack(fill="x", padx=12, pady=(4, 12), side="bottom")

    # ── Logging ──────────────────────────────────────────────────────────
    # ── Blacklist Manager ───────────────────────────────────────────────"""

assert old_log in content, "log anchor not found"
content = content.replace(old_log, new_log, 1)
print("OK: methods added")

# Restore line endings
if has_crlf:
    content = content.replace('\n', '\r\n')

with open('apps/desktop/src/main.py', 'w', encoding='utf-8', newline='') as f:
    f.write(content)

print("ALL PATCHES APPLIED")
