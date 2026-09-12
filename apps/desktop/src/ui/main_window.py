import os
import shutil
import sys
import threading
import time
import tkinter as tk
from datetime import UTC, datetime

import customtkinter as ctk

from backend.core.config_manager import (
    get_cache_hits,
    get_cached_metadata,
    get_file_hash,
    load_config,
    save_config,
    set_cached_metadata,
)
from backend.core.worker_pool import (
    FileWorkerPool,
    find_companion_files,
    sync_companion_metadata,
)
from backend.processors.exiftool_client import ExifToolClient
from backend.processors.media_converter import extract_preview_image
from packages.shared_utils.csv_exporter import generate_microstock_csvs
from packages.shared_utils.tools_setup import ensure_tools_installed
from packages.shared_utils.env_check import run_environment_checks
from packages.shared_utils.filter import (
    add_to_blacklist,
    autofix_compliance,
    calculate_quality_score,
    clean_metadata,
    detect_redundant_keywords,
    get_blacklist,
    lowercase_keywords,
    remove_from_blacklist,
    remove_redundant_keywords,
    sanitize_keywords,
    to_lowercase,
    to_sentence_case,
    to_title_case,
    to_uppercase,
    trim_keywords,
    validate_compliance,
)
from packages.shared_utils.ftp_uploader import FTPClient
from packages.shared_utils.license_manager import AuthClient
from packages.shared_utils.logger import CSVLogger
from packages.shared_utils.presets import delete_preset as delete_kw_preset
from packages.shared_utils.presets import (
    export_presets,
    get_preset,
    get_preset_names,
    import_presets,
)
from packages.shared_utils.presets import save_preset as save_kw_preset
from packages.shared_utils.updater import check_github_release

from ui.theme import (
    C,
    CR,
    _btn,
    _combo,
    _divider,
    _entry,
    _frame,
    _label,
    _section_header,
    _slider,
)
from ui.widgets.inspector_panel import InspectorPanel
from ui.widgets.log_console import LogConsole
from ui.widgets.queue_view import QueueView
from ui.widgets.sidebar_panel import SidebarPanel

class AppWindow(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("NRA Metadata")
        self.geometry("1200x720")
        self.minsize(1060, 680)
        self.configure(fg_color=C["bg"])

        self.config = load_config()
        self.auth = AuthClient()
        self.input_dir = ctk.StringVar(value=self.config.get("last_folder", ""))
        self.input_dir.trace_add(
            "write", lambda *_: self.after(100, self._refresh_file_queue)
        )
        self.output_dir = ctk.StringVar()

        self.processor = MediaProcessor()
        self.stats = {"total": 0, "success": 0, "error": 0}
        self.current_preview_img = None
        self.processed_files = set()
        self.excluded_files = set()
        self.batch_session_stats = {
            "processed": 0,
            "skipped": 0,
            "cost": 0.0,
            "csvs": [],
            "tokens_est": 0,
        }
        self.is_running = False
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.cancel_flag = False

        self.current_edit_file = None
        self.current_edit_hash = None

        self.undo_stack = []
        self.redo_stack = []
        self._is_undoing = False

        self.log_buffer = []
        self.log_lock = threading.Lock()
        self.tools_ready = False

        self.MODEL_MAP = {
            "Gemini": [
                "gemini-2.5-flash-lite (Recommended)",
                "gemini-2.5-flash",
                "gemini-3.5-flash-lite",
                "gemini-3.6-flash",
                "gemini-3.7-flash",
                "gemini-3.8-flash",
                "gemini-3.1-flash-lite",
                "gemini-2.5-pro",
                "gemini-3.1-pro-preview",
            ],
            "Groq": [
                "llama-3.2-11b-vision-preview (Recommended)",
                "llama-3.2-90b-vision-preview",
            ],
            "Mistral": [
                "pixtral-12b-2409 (Cost Efficient)",
                "ministral-3-8b",
                "pixtral-large-2411",
                "mistral-large-latest",
            ],
            "OpenAI": ["gpt-4o-mini (Optimal)", "gpt-4o", "chatgpt-4o-latest"],
        }

        self._restore_geometry()
        self.build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Update initial key counter
        self.after(
            10, lambda: self._update_keys_counter(self.config.get("provider", "Gemini"))
        )

        # Initial Auth Check
        self.after(100, self._check_initial_auth)
        self.after(
            2000,
            lambda: check_github_release(
                callback=lambda info: self.after(
                    0, lambda: self._show_update_banner(info)
                )
            ),
        )

    def _show_update_banner(self, info: dict):
        import webbrowser

        self.update_banner.configure(
            text=f" [Update Available: v{info['version']}] ",
            text_color="#FFFFFF",
            fg_color=C["accent"],
            cursor="hand2",
        )
        self.update_banner.bind("<Button-1>", lambda e: webbrowser.open(info["url"]))

    def _check_initial_auth(self):
        # Run diagnostic checks silently, print to internal logs
        env_results = run_environment_checks()
        for name, ok, msg in env_results:
            if not ok:
                self.log(f"Diag Warning: {name} - {msg}", "error")

        def setup_tools():
            self.log("[INFO] Checking external media tools...", "info")
            ensure_tools_installed(progress_callback=lambda m: self.log(m, "info" if "SUCCESS" in m or "INFO" in m else "warn"))
            self.tools_ready = True
            self.log("[INFO] External tools ready.", "info")

        threading.Thread(target=setup_tools, daemon=True).start()

        is_valid, msg = self.auth.validate_session()
        if not is_valid:
            self.show_login_modal()

    def show_login_modal(self):
        from ui.dialogs.login_modal import show_login_modal as _show_login_modal

        _show_login_modal(self)

    def _refresh_file_queue(self):
        for w in self.queue_scroll.winfo_children():
            w.destroy()

        in_dir = self.input_dir.get()
        if not in_dir or not os.path.isdir(in_dir):
            self.queue_count_lbl.configure(text="0 files")
            return

        files = [
            f
            for f in os.listdir(in_dir)
            if os.path.isfile(os.path.join(in_dir, f)) and self._is_allowed_file(f)
        ]
        self.queue_count_lbl.configure(text=f"{len(files)} files found")

        # Cleanup excluded_files that are no longer present
        self.excluded_files = {f for f in self.excluded_files if f in files}
        self._queue_vars.clear()

        for i, f in enumerate(files):
            row = ctk.CTkFrame(
                self.queue_scroll,
                fg_color=C["surface2"] if i % 2 == 0 else C["surface"],
                corner_radius=0,
            )
            row.pack(fill="x")

            is_processed = f in self.processed_files

            # Badge
            badge_color = C["success"] if is_processed else C["text3"]
            badge_text = "Done" if is_processed else "Pending"

            # Use boolean var for exclude toggle
            var = ctk.BooleanVar(value=f in self.excluded_files)
            self._queue_vars[f] = var

            def on_toggle(filename=f, v=var):
                if v.get():
                    self.excluded_files.add(filename)
                else:
                    self.excluded_files.discard(filename)
                self._refresh_file_queue()  # re-render to show skipped style

            cb = ctk.CTkCheckBox(
                row,
                text="",
                variable=var,
                command=on_toggle,
                width=20,
                checkbox_width=18,
                checkbox_height=18,
                fg_color=C["warn"],
                hover_color=C["warn_h"],
                border_color=C["border"],
            )
            cb.pack(side="left", padx=(8, 4), pady=4)

            if var.get():
                badge_color = C["border"]
                badge_text = "Skipped"

            ctk.CTkLabel(
                row,
                text=badge_text,
                width=50,
                corner_radius=4,
                fg_color=badge_color,
                text_color=C["bg"] if badge_color != "transparent" else C["text"],
                font=ctk.CTkFont(size=9, weight="bold"),
            ).pack(side="left", padx=4, pady=4)

            lbl = ctk.CTkLabel(
                row,
                text=f,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=C["text3"] if var.get() else C["text"],
            )
            lbl.pack(side="left", padx=8, pady=4)

    def _toggle_all_exclusions(self, exclude: bool):
        in_dir = self.input_dir.get()
        if not in_dir or not os.path.isdir(in_dir):
            return
        files = [
            f
            for f in os.listdir(in_dir)
            if os.path.isfile(os.path.join(in_dir, f)) and self._is_allowed_file(f)
        ]
        if exclude:
            self.excluded_files.update(files)
        else:
            self.excluded_files.clear()
        self._refresh_file_queue()

    # ── History & Undo ───────────────────────────────────────────────────
    def _save_snapshot(self):
        if self._is_undoing:
            return
        self.redo_stack.clear()
        state = {
            "title": self.edit_title_var.get(),
            "desc": self.edit_desc_var.get(),
            "kws": self.edit_kws_var.get(),
        }
        if not self.undo_stack or self.undo_stack[-1] != state:
            self.undo_stack.append(state)
            if len(self.undo_stack) > 50:
                self.undo_stack.pop(0)

    def _restore_snapshot(self, state):
        self._is_undoing = True
        self.edit_title_var.set(state.get("title", ""))
        self.edit_desc_var.set(state.get("desc", ""))
        self.edit_kws_var.set(state.get("kws", ""))
        self._is_undoing = False
        self._update_kw_counter()
        self._update_compliance()

    def undo_metadata(self):
        if not self.undo_stack:
            return
        current_state = {
            "title": self.edit_title_var.get(),
            "desc": self.edit_desc_var.get(),
            "kws": self.edit_kws_var.get(),
        }
        if not self.redo_stack or self.redo_stack[-1] != current_state:
            self.redo_stack.append(current_state)
        state = self.undo_stack.pop()
        if state == current_state and self.undo_stack:
            state = self.undo_stack.pop()
        self._restore_snapshot(state)

    def redo_metadata(self):
        if not self.redo_stack:
            return
        current_state = {
            "title": self.edit_title_var.get(),
            "desc": self.edit_desc_var.get(),
            "kws": self.edit_kws_var.get(),
        }
        self.undo_stack.append(current_state)
        state = self.redo_stack.pop()
        self._restore_snapshot(state)
    def build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Header Bar ──────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0, height=42)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        header.grid_propagate(False)

        brand = ctk.CTkLabel(
            header,
            text="◆  NRA Metadata",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=C["text"],
        )
        brand.grid(row=0, column=0, padx=16, pady=8, sticky="w")

        self.header_status = ctk.CTkLabel(
            header,
            text="Ready",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C["text3"],
        )
        self.header_status.grid(row=0, column=1, sticky="e", padx=16)

        # ── Outer PanedWindow: Sidebar | Main ────────────────────────
        self.outer_paned = tk.PanedWindow(
            self,
            orient=tk.HORIZONTAL,
            sashwidth=5,
            bg=C["border"],
            borderwidth=0,
            opaqueresize=True,
            sashrelief=tk.FLAT,
        )
        self.outer_paned.grid(row=1, column=0, sticky="nsew", pady=(1, 0))

        # ── Sidebar ─────────────────────────────────────────────────────
        sidebar_panel = SidebarPanel(self.outer_paned, self)
        self.outer_paned.add(
            sidebar_panel,
            minsize=220,
            width=self.config.get("sidebar_width", 260),
        )

        # ── Main Content Area ─────────────────────────────────────────
        main = ctk.CTkFrame(self.outer_paned, fg_color=C["bg"], corner_radius=0)
        self.outer_paned.add(main, minsize=500)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(4, weight=1)

        # ── Update Banner ──
        self.update_banner = ctk.CTkLabel(
            main, text="", text_color=C["text3"], fg_color=C["bg"], height=0
        )
        self.update_banner.grid(row=0, column=0, sticky="ew", padx=15, pady=(0, 0))

        # ── Folder Bar ──
        folder_bar = _frame(main)
        folder_bar.grid(row=1, column=0, sticky="ew", padx=12, pady=(12, 0))
        folder_bar.grid_columnconfigure(1, weight=1)

        _label(
            folder_bar,
            "Folder",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=C["text"],
        ).grid(row=0, column=0, padx=12, pady=10, sticky="w")
        _entry(folder_bar, self.input_dir).grid(
            row=0, column=1, padx=0, pady=10, sticky="ew"
        )
        _btn(
            folder_bar,
            "Browse",
            C["surface2"],
            C["border"],
            command=self.browse_input,
            width=72,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11),
        ).grid(row=0, column=2, padx=(8, 12), pady=10)

        # ── File Queue Panel ──
        queue_view = QueueView(main, self)
        queue_view.grid(row=2, column=0, sticky="ew", padx=12, pady=(6, 0))

        # ── Stats & Progress Row ──
        stats_row = ctk.CTkFrame(main, fg_color=C["bg"])
        stats_row.grid(row=3, column=0, sticky="ew", padx=12, pady=(8, 0))
        stats_row.grid_columnconfigure(0, weight=1)
        stats_row.grid_columnconfigure(1, weight=1)

        self.stats_lbl = _label(
            stats_row,
            "Total: 0  ·  Success: 0  ·  Error: 0",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=C["text2"],
        )
        self.stats_lbl.grid(row=0, column=0, sticky="w")

        self.cost_lbl = _label(
            stats_row,
            "Cost: $0.000  ·  Cache: 0",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C["success"],
        )
        self.cost_lbl.grid(row=0, column=1, sticky="e")

        self.progress_bar = ctk.CTkProgressBar(
            stats_row,
            progress_color=C["accent"],
            fg_color=C["surface2"],
            height=4,
            corner_radius=2,
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        # ── Content: Log (left) + Inspector (right) via PanedWindow ──
        content_wrap = ctk.CTkFrame(main, fg_color=C["bg"])
        content_wrap.grid(row=4, column=0, sticky="nsew", padx=12, pady=(8, 12))
        content_wrap.grid_columnconfigure(0, weight=1)
        content_wrap.grid_rowconfigure(0, weight=1)

        self.content_paned = tk.PanedWindow(
            content_wrap,
            orient=tk.HORIZONTAL,
            sashwidth=5,
            bg=C["border"],
            borderwidth=0,
            opaqueresize=True,
            sashrelief=tk.FLAT,
        )
        self.content_paned.grid(row=0, column=0, sticky="nsew")

        # Console / Log
        log_frame = _frame(
            self.content_paned, border_width=1, border_color=C["border_sub"]
        )
        self.content_paned.add(
            log_frame, minsize=300, width=self.config.get("log_width", 500)
        )
        log_console = LogConsole(log_frame, self)
        log_console.pack(fill="both", expand=True)

        # Inspector
        inspector_container = _frame(
            self.content_paned, border_width=1, border_color=C["border_sub"]
        )
        self.content_paned.add(inspector_container, minsize=280)
        inspector_panel = InspectorPanel(inspector_container, self)
        inspector_panel.pack(fill="both", expand=True)
    def _flush_cache(self):
        import sqlite3
        from tkinter import messagebox

        db_path = os.path.join(os.getcwd(), "cache.db")
        if not os.path.exists(db_path):
            self.log("Cache DB not found.")
            return
        if not messagebox.askyesno(
            "Confirm",
            "Are you sure you want to completely clear the metadata cache? This will force AI regeneration for all files.",
        ):
            return
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("DELETE FROM metadata_cache")
            conn.commit()
            conn.close()
            self.log("Local cache completely cleared.")
            messagebox.showinfo("Success", "Cache cleared successfully.")
        except (OSError, sqlite3.Error) as e:
            self.log(f"Failed to clear cache: {e!s}", "error")

    # ── Keyword Presets ──────────────────────────────────────────────────
    def _open_keyword_presets(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Keyword Presets")
        dialog.geometry("420x480")
        dialog.configure(fg_color=C["bg"])
        dialog.transient(self)
        dialog.grab_set()

        _label(
            dialog,
            "Save Current Keywords as Preset",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        ).pack(padx=12, pady=(12, 4), anchor="w")

        save_row = ctk.CTkFrame(dialog, fg_color="transparent")
        save_row.pack(fill="x", padx=12, pady=2)
        name_entry = _entry(save_row, placeholder_text="Preset name...")
        name_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))

        def do_save():
            n = name_entry.get().strip()
            if not n:
                return
            kws = self._get_kws_list()
            save_kw_preset(n, kws)
            name_entry.delete(0, "end")
            refresh()
            self.log(f"Saved keyword preset: {n} ({len(kws)} keywords)", "info")

        _btn(
            save_row, "Save", C["accent"], C["accent_h"], width=60, command=do_save
        ).pack(side="right")

        _divider(dialog).pack(fill="x", padx=12, pady=(8, 4))
        _label(
            dialog,
            "Saved Presets",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        ).pack(padx=12, pady=(4, 4), anchor="w")

        list_frame = ctk.CTkScrollableFrame(
            dialog, fg_color=C["surface"], corner_radius=CR
        )
        list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        list_frame._parent_canvas.configure(bg=C["surface"], highlightthickness=0)

        def refresh():
            for w in list_frame.winfo_children():
                w.destroy()
            for pname in get_preset_names():
                row = ctk.CTkFrame(list_frame, fg_color="transparent")
                row.pack(fill="x", pady=1)
                kws = get_preset(pname)
                ctk.CTkLabel(
                    row,
                    text=f"{pname}  ({len(kws)} kw)",
                    text_color=C["text"],
                    font=ctk.CTkFont(size=11),
                ).pack(side="left", padx=4)

                ctk.CTkButton(
                    row,
                    text="\u00d7",
                    width=20,
                    height=20,
                    fg_color="transparent",
                    text_color=C["error"],
                    hover_color=C["surface2"],
                    command=lambda n=pname: [delete_kw_preset(n), refresh()],
                ).pack(side="right", padx=2)

                ctk.CTkButton(
                    row,
                    text="+ Append",
                    width=60,
                    height=20,
                    fg_color=C["surface2"],
                    hover_color=C["border"],
                    font=ctk.CTkFont(size=9),
                    command=lambda n=pname: self._apply_preset_kws(n, "append"),
                ).pack(side="right", padx=2)

                ctk.CTkButton(
                    row,
                    text="Replace",
                    width=55,
                    height=20,
                    fg_color=C["accent"],
                    hover_color=C["accent_h"],
                    font=ctk.CTkFont(size=9),
                    command=lambda n=pname: self._apply_preset_kws(n, "replace"),
                ).pack(side="right", padx=2)

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
            path = ctk.filedialog.asksaveasfilename(
                defaultextension=".json", filetypes=[("JSON", "*.json")]
            )
            if path:
                export_presets(path)
                self.log("Keyword presets exported.", "info")

        _btn(
            io_row, "Import .json", C["surface2"], C["border"], command=do_import
        ).pack(side="left", expand=True, padx=(0, 4))
        _btn(
            io_row, "Export .json", C["surface2"], C["border"], command=do_export
        ).pack(side="right", expand=True, padx=(4, 0))

    def _apply_preset_kws(self, name, mode):
        kws = get_preset(name)
        if not kws:
            return
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

            src_title = self.edit_title_var.get()
            src_desc = self.edit_desc_var.get()
            src_kws = self._get_kws_list()

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
                    self.processor.embed_metadata(
                        fpath,
                        new_title,
                        new_desc,
                        new_kws,
                        self._get_copyright_text(),
                        self.author_entry.get().strip(),
                    )
                    applied += 1

            if applied > 0:
                generate_microstock_csvs(target_dir, self._get_selected_csv_platforms())

            self.log(
                f"Batch Apply: {applied} files updated, {skipped} skipped.", "success"
            )
            dialog.destroy()

        _btn(
            dialog,
            "Apply to Batch",
            C["accent"],
            C["accent_h"],
            command=run_batch_apply,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        ).pack(fill="x", padx=12, pady=(4, 12), side="bottom")

    # ── Logging ──────────────────────────────────────────────────────────
    # ── Blacklist Manager ───────────────────────────────────────────────
    def open_blacklist_manager(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Blacklist Manager")
        dialog.geometry("400x500")
        dialog.configure(fg_color=C["bg"])
        dialog.transient(self)
        dialog.grab_set()

        _label(dialog, "Add New Word(s): (comma separated)").pack(
            padx=12, pady=(12, 2), anchor="w"
        )
        add_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        add_frame.pack(fill="x", padx=12, pady=2)
        add_entry = _entry(add_frame)
        add_entry.pack(side="left", expand=True, fill="x", padx=(0, 4))

        list_frame = ctk.CTkScrollableFrame(
            dialog, fg_color=C["surface"], corner_radius=CR
        )
        list_frame.pack(fill="both", expand=True, padx=12, pady=10)
        list_frame._parent_canvas.configure(bg=C["surface"], highlightthickness=0)

        def refresh_list():
            for w in list_frame.winfo_children():
                w.destroy()
            for word in sorted(get_blacklist()):
                row = ctk.CTkFrame(list_frame, fg_color="transparent")
                row.pack(fill="x", pady=1)
                ctk.CTkLabel(
                    row, text=word, text_color=C["text"], font=ctk.CTkFont(size=12)
                ).pack(side="left", padx=4)
                del_btn = ctk.CTkButton(
                    row,
                    text="×",
                    width=20,
                    height=20,
                    fg_color="transparent",
                    text_color=C["error"],
                    hover_color=C["surface2"],
                    command=lambda w=word: [remove_from_blacklist(w), refresh_list()],
                )
                del_btn.pack(side="right")

        def add_words():
            words = add_entry.get().split(",")
            add_to_blacklist(words)
            add_entry.delete(0, "end")
            refresh_list()

        _btn(
            add_frame, "Add", C["accent"], C["accent_h"], width=60, command=add_words
        ).pack(side="right")

        refresh_list()

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=10, side="bottom")

        def import_bl():
            path = ctk.filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
            if path:
                with open(path, "r", encoding="utf-8") as f:
                    words = [line.strip() for line in f if line.strip()]
                    add_to_blacklist(words)
                    refresh_list()
                    self.log(f"Imported {len(words)} words to blacklist.", "info")

        def export_bl():
            path = ctk.filedialog.asksaveasfilename(
                defaultextension=".txt", filetypes=[("Text files", "*.txt")]
            )
            if path:
                import shutil

                from packages.shared_utils.filter import BLACKLIST_FILE

                shutil.copy(BLACKLIST_FILE, path)
                self.log("Blacklist exported.", "info")

        _btn(
            btn_frame, "Import .txt", C["surface2"], C["border"], command=import_bl
        ).pack(side="left", expand=True, padx=(0, 4))
        _btn(
            btn_frame, "Export .txt", C["surface2"], C["border"], command=export_bl
        ).pack(side="right", expand=True, padx=(4, 0))

    # ── Batch Find & Replace ─────────────────────────────────────────────
    def open_batch_replace(self):
        target_dir = self.input_dir.get()
        if not target_dir or not os.path.isdir(target_dir):
            self.log("Set Folder first to run batch replace.", "error")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Batch Metadata Find & Replace")
        dialog.geometry("400x420")
        dialog.configure(fg_color=C["bg"])
        dialog.transient(self)
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
                    if self._is_allowed_file(fname):
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
                            self.processor.embed_metadata(
                                fpath,
                                meta["title"],
                                meta["description"],
                                meta["keywords"],
                                self._get_copyright_text(),
                                self.author_entry.get().strip(),
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
            if self.current_edit_hash:
                m = get_cached_metadata(self.current_edit_hash)
                if m:
                    self._save_snapshot()
                    self.edit_title_var.set(m.get("title", ""))
                    self.edit_desc_var.set(m.get("description", ""))
                    self.edit_kws_var.set(", ".join(m.get("keywords", [])))

            self.log(
                f"Batch Replace: Replaced {count} occurrences of '{f_text}'.", "success"
            )
            dialog.destroy()

        _btn(dialog, "Replace All", C["warn"], C["warn_h"], command=run_replace).pack(
            side="bottom", pady=16, padx=12, fill="x"
        )

    def log(self, message: str, level="info"):
        entry = {
            "ts": datetime.now(UTC).strftime("%H:%M:%S"),
            "level": level,
            "msg": message,
        }
        with self.log_lock:
            self.log_buffer.append(entry)
            if len(self.log_buffer) > 5000:
                self.log_buffer.pop(0)

        # Immediate append if filter matches (optimization to avoid full refresh on every log)
        def _append():
            q = self.log_search_var.get().lower()
            flt = self.log_level_var.get().lower()
            if (flt == "all" or flt == level) and (not q or q in message.lower()):
                self.console.configure(state="normal")
                tb = self.console._textbox
                tb.insert("end", f"[{entry['ts']}] ", "timestamp")
                tb.insert("end", f"[{level.upper()}] ", level)
                tb.insert("end", f"{message}\n", level)
                self.console.see("end")
                self.console.configure(state="disabled")

        self.after(0, _append)

    def _refresh_log(self, *_):
        q = self.log_search_var.get().lower()
        flt = self.log_level_var.get().lower()
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        tb = self.console._textbox
        with self.log_lock:
            buffer_copy = list(self.log_buffer)
        for entry in buffer_copy:
            lvl = entry["level"]
            msg = entry["msg"]
            if flt != "all" and flt != lvl:
                continue
            if q and q not in msg.lower():
                continue
            tb.insert("end", f"[{entry['ts']}] ", "timestamp")
            tb.insert("end", f"[{lvl.upper()}] ", lvl)
            tb.insert("end", f"{msg}\n", lvl)
        self.console.see("end")
        self.console.configure(state="disabled")

    def _clear_log(self):
        with self.log_lock:
            self.log_buffer.clear()
        self._refresh_log()

    def _export_log(self):
        with self.log_lock:
            if not self.log_buffer:
                return
            buffer_copy = list(self.log_buffer)
        path = ctk.filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text files", "*.txt")]
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(
                    f"[{entry['ts']}] [{entry['level'].upper()}] {entry['msg']}\n"
                    for entry in buffer_copy
                )

    # ── Presets ──────────────────────────────────────────────────────────
    def _load_custom_presets(self):
        self.presets = {
            "Default": {},
            "Adobe Stock Vector": {
                "min_kw": 15,
                "max_kw": 45,
                "formats": {
                    ".svg": True,
                    ".eps": True,
                    ".ai": False,
                    ".jpg": False,
                    ".png": False,
                    ".mp4": False,
                    ".mov": False,
                },
                "style_preset": "General Commercial",
            },
            "Shutterstock Photo": {
                "min_kw": 20,
                "max_kw": 50,
                "formats": {
                    ".svg": False,
                    ".eps": False,
                    ".ai": False,
                    ".jpg": True,
                    ".png": False,
                    ".mp4": False,
                    ".mov": False,
                },
                "style_preset": "Photo Realistic",
            },
            "Vecteezy Icon/Clipart": {
                "min_kw": 10,
                "max_kw": 30,
                "formats": {
                    ".svg": True,
                    ".eps": True,
                    ".ai": False,
                    ".jpg": False,
                    ".png": True,
                    ".mp4": False,
                    ".mov": False,
                },
                "style_preset": "Vector Clipart",
            },
        }
        custom = self.config.get("custom_presets", {})
        self.presets.update(custom)
        self.preset_cb.configure(values=list(self.presets.keys()))

    def _on_preset_change(self, choice):
        p = self.presets.get(choice)
        if not p:
            return
        if "min_kw" in p:
            self.min_kw_entry.delete(0, "end")
            self.min_kw_entry.insert(0, str(p["min_kw"]))
        if "max_kw" in p:
            self.max_kw_entry.delete(0, "end")
            self.max_kw_entry.insert(0, str(p["max_kw"]))
        if "style_preset" in p:
            # Need to ensure combo has it, though normally we'd dynamically add or rely on style mapping
            self.style_cb.set(p["style_preset"])
        if "formats" in p:
            for ext, val in p["formats"].items():
                if ext in self.fmt_vars:
                    self.fmt_vars[ext].set(val)

    def _save_preset(self):
        dialog = ctk.CTkInputDialog(text="Enter preset name:", title="Save Preset")
        name = dialog.get_input()
        if not name or name.strip() in ["", "Default"]:
            return
        name = name.strip()

        custom = self.config.get("custom_presets", {})
        custom[name] = {
            "min_kw": self._safe_int(self.min_kw_entry.get(), 10),
            "max_kw": self._safe_int(self.max_kw_entry.get(), 49),
            "custom_kw": self.custom_kw_entry.get(),
            "custom_kw_pos": self.custom_kw_pos.get(),
            "extra_prompt": self.extra_prompt_entry.get(),
            "style_preset": self.style_cb.get(),
            "formats": {ext: var.get() for ext, var in self.fmt_vars.items()},
        }
        self.config["custom_presets"] = custom
        save_config(self.config)
        self._load_custom_presets()
        self.preset_cb.set(name)

    def _delete_preset(self):
        name = self.preset_cb.get()
        if name in [
            "Default",
            "Adobe Stock Vector",
            "Shutterstock Photo",
            "Vecteezy Icon/Clipart",
        ]:
            return  # Can't delete built-in
        custom = self.config.get("custom_presets", {})
        if name in custom:
            del custom[name]
            self.config["custom_presets"] = custom
            save_config(self.config)
            self._load_custom_presets()
            self.preset_cb.set("Default")

    def update_stats(self, key):
        def _update():
            self.stats[key] += 1
            self.stats_lbl.configure(
                text=f"Total: {self.stats['total']}  ·  Success: {self.stats['success']}  ·  Error: {self.stats['error']}"
            )
            self.cost_lbl.configure(
                text=f"Tokens: ~{self.batch_session_stats.get('tokens_est', 0) // 1000}k | Est. Cost: ${self.batch_session_stats.get('cost', 0):.3f}  ·  Cache: {get_cache_hits()}"
            )

            # Update header status
            if self.is_running:
                done = self.stats["success"] + self.stats["error"]
                self.header_status.configure(
                    text=f"Processing {done}/{self.stats['total']}",
                    text_color=C["warn"],
                )
            else:
                self.header_status.configure(text="Ready", text_color=C["text3"])

        self.after(0, _update)

    def update_preview(
        self,
        img,
        status_text: str,
        status_color: str,
        meta: dict,
        out_path: str,
        file_hash: str,
    ):
        def _draw():
            try:
                img.thumbnail((180, 180))
                self.current_preview_img = ctk.CTkImage(
                    light_image=img, dark_image=img, size=img.size
                )
                self.preview_lbl.configure(image=self.current_preview_img, text="")
                self.status_badge.configure(text=status_text, fg_color=status_color)

                self.edit_title_var.set(meta.get("title", ""))
                self.edit_desc_var.set(meta.get("description", ""))
                self.edit_kws_var.set(", ".join(meta.get("keywords", [])))

                self.current_edit_file = out_path
                self.current_edit_hash = file_hash
                self.undo_stack.clear()
                self.redo_stack.clear()
                self._update_variant_badge()
                self._update_quality_score()
            except (tk.TclError, AttributeError):
                pass

        self.after(0, _draw)

    # ── Geometry & Sash Persistence ────────────────────────────────────
    def _restore_geometry(self):
        geo = self.config.get("window_geometry")
        if geo:
            try:
                self.geometry(geo)
            except (ValueError, tk.TclError):
                self.geometry("1200x720")
        else:
            self.geometry("1200x720")

    def _restore_sash_positions(self):
        try:
            sw = self.config.get("sidebar_width")
            if sw and self.outer_paned.winfo_ismapped():
                self.outer_paned.sash_place(0, int(sw), 0)
        except (ValueError, tk.TclError):
            pass
        try:
            lw = self.config.get("log_width")
            if lw and self.content_paned.winfo_ismapped():
                self.content_paned.sash_place(0, int(lw), 0)
        except (ValueError, tk.TclError):
            pass

    def _save_current_config(self):
        """Collect all widget values and persist to config.enc."""
        try:
            if not hasattr(self, "provider_cb"):
                return

            provider = self.provider_cb.get()

            # Ensure api_keys dict exists
            if "api_keys" not in self.config:
                self.config["api_keys"] = {}

            # Update the key for the CURRENT provider explicitly from the entry field
            if hasattr(self, "api_key_entry"):
                self.config["api_keys"][provider] = self.api_key_entry.get()

            # Clean old legacy key
            self.config.pop("api_key", None)

            self.config.update(
                {
                    "provider": provider,
                    "model": self.model_cb.get(),
                    "temperature": round(float(self.temp_slider.get()), 1),
                    "style_preset": self.style_cb.get(),
                    "min_kw": self._safe_int(self.min_kw_entry.get(), 10),
                    "max_kw": self._safe_int(self.max_kw_entry.get(), 49),
                    "custom_kw": self.custom_kw_entry.get(),
                    "custom_kw_pos": self.custom_kw_pos.get(),
                    "extra_prompt": self.extra_prompt_entry.get(),
                    "workers": int(self.workers_slider.get()),
                    "formats": {ext: var.get() for ext, var in self.fmt_vars.items()},
                    "author": self.author_entry.get().strip(),
                    "copyright": self.copyright_entry.get().strip(),
                    "csv_platforms": list(self._get_selected_csv_platforms()),
                    "auto_watch": self.auto_watch.get(),
                    "auto_zip_vector": self.auto_zip.get(),
                    "target_platform": self.target_plat_var.get(),
                    "sync_companion_files": self.sync_companions.get(),
                    "last_folder": self.input_dir.get(),
                    "active_profile": self.preset_var.get(),
                }
            )
            if self.outer_paned.winfo_ismapped():
                self.config["sidebar_width"] = self.outer_paned.sash_coord(0)[0]
            if self.content_paned.winfo_ismapped():
                self.config["log_width"] = self.content_paned.sash_coord(0)[0]
            self.config["window_geometry"] = self.geometry()
        except (tk.TclError, ValueError):
            pass
        from packages.shared_utils.config import save_config

        save_config(self.config)

    def _on_close(self):
        self.cancel_flag = True
        self._save_current_config()
        self.destroy()
        import os

        os._exit(0)

    def _load_keys_from_file(self):
        from tkinter import filedialog

        path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if not path:
            return

        provider = self.provider_cb.get()
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            keys = []
            for line in lines:
                k = line.strip()
                if k and k not in keys:
                    keys.append(k)

            if keys:
                if "api_keys_pool" not in self.config:
                    self.config["api_keys_pool"] = {}
                self.config["api_keys_pool"][provider] = keys

                # Update current entry to first key
                self.api_key_entry.delete(0, "end")
                self.api_key_entry.insert(0, keys[0])
                self._save_current_config()  # Save to old api_keys dict for backward compatibility

                self.keys_counter_lbl.configure(text=f"({len(keys)} keys loaded)")
                self._save_current_config()
                self.log(f"Loaded {len(keys)} API keys for {provider}", "success")
            else:
                self.log("File is empty or contains no valid keys.", "error")
        except OSError as e:
            self.log(f"Failed to read file: {e}", "error")

    def _update_keys_counter(self, provider):
        if hasattr(self, "keys_counter_lbl"):
            pool = self.config.get("api_keys_pool", {}).get(provider, [])
            # Also check old api_keys dict if pool is empty
            if not pool and self.config.get("api_keys", {}).get(provider):
                pool = [self.config["api_keys"][provider]]
            self.keys_counter_lbl.configure(text=f"({len(pool)} keys loaded)")

    def _fetch_models(self):
        provider = self.provider_cb.get()
        api_key = self.api_key_entry.get().strip()

        if not api_key:
            self.log(f"Please enter an API Key for {provider} first.", "error")
            return

        self.fetch_models_btn.configure(text="[ Mengambil... ]", state="disabled")
        self.update_idletasks()

        def _bg_fetch():
            from packages.ai_engine.service import AIService

            ai = AIService(provider, api_key)
            models = ai.fetch_available_models()
            self.after(0, lambda: self._fetch_models_done(provider, models))

        import threading

        threading.Thread(target=_bg_fetch, daemon=True).start()

    def _fetch_models_done(self, provider, models):
        self.fetch_models_btn.configure(text="🔄 Fetch Models", state="normal")
        if not models:
            self.log(
                f"Failed to fetch models for {provider} or API Key invalid.", "error"
            )
            return

        # Update MAP and UI
        self.MODEL_MAP[provider] = models
        current_provider = self.provider_cb.get()

        if current_provider == provider:
            self.model_cb.configure(values=models)
            if models:
                self.model_cb.set(models[0])
            self.log(f"Successfully updated models for {provider}.", "success")

    def _update_model_list(self, choice):
        models = self.MODEL_MAP.get(choice, [])
        self.model_cb.configure(values=models, state="readonly")
        if models:
            self.model_cb.set(models[0])
            self.config["model"] = models[0]
        else:
            self.model_cb.set("")
            self.config["model"] = ""

    def _on_provider_change(self, choice):
        if hasattr(self, "api_key_entry"):
            # 1. Simpan API Key yang sedang diketik ke provider sebelumnya
            current_key_input = self.api_key_entry.get().strip()
            prev_provider = getattr(
                self, "current_provider", self.config.get("provider", "Gemini")
            )

            if "api_keys" not in self.config:
                self.config["api_keys"] = {}
            if current_key_input:
                self.config["api_keys"][prev_provider] = current_key_input

            # 2. Update status provider aktif
            self.current_provider = choice
            self.config["provider"] = choice

            # 3. Muat API Key milik provider yang baru dipilih
            target_key = self.config["api_keys"].get(choice, "")
            self.api_key_entry.delete(0, "end")
            if target_key:
                self.api_key_entry.insert(0, target_key)

            self.api_key_entry.configure(placeholder_text="API Key")

        # Update counter
        if hasattr(self, "_update_keys_counter"):
            self._update_keys_counter(choice)

        # 4. Sinkronkan daftar Model di dropdown ComboBox
        if hasattr(self, "_update_model_list"):
            self._update_model_list(choice)

        # 5. Simpan state konfigurasi ke storage
        self._save_current_config()

    def _get_selected_csv_platforms(self) -> set:
        return {plat for plat, var in self.csv_vars.items() if var.get()}

    def _autofix_metadata(self):
        self._save_snapshot()
        title = self.edit_title_var.get()
        kws = [k.strip() for k in self.edit_kws_var.get().split(",") if k.strip()]
        plat = self.target_plat_var.get()

        fixed_title, fixed_kws = autofix_compliance(title, kws, plat)
        self.edit_title_var.set(fixed_title)
        self.edit_kws_var.set(", ".join(fixed_kws))
        self._update_compliance()

    def _update_compliance(self):
        title = self.edit_title_var.get()
        kws = [k.strip() for k in self.edit_kws_var.get().split(",") if k.strip()]
        plat = self.target_plat_var.get()

        res = validate_compliance(title, kws, plat)
        if res["valid"]:
            self.compliance_lbl.configure(
                text=f"● Compliant ({plat})", text_color=C["success"]
            )
        else:
            err_text = " | ".join(res["errors"])
            self.compliance_lbl.configure(text=f"● {err_text}", text_color=C["error"])

    def _get_copyright_text(self) -> str:
        cr = self.copyright_entry.get().strip()
        if cr:
            return cr
        author = self.author_entry.get().strip()
        if author:
            from datetime import UTC

            return (
                f"Copyright (c) {datetime.now(UTC).year} {author}. All rights reserved."
            )
        return ""

    def _safe_int(self, val, default=0):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def _update_kw_counter(self):
        raw = self.edit_kws_var.get()
        count = len([k for k in raw.split(",") if k.strip()])
        min_kw = self._safe_int(self.min_kw_entry.get(), 10)
        max_kw = self._safe_int(self.max_kw_entry.get(), 49)
        if min_kw <= count <= max_kw:
            color = C["success"]
        elif count < min_kw:
            color = C["warn"]
        else:
            color = C["error"]
        self.kw_counter_lbl.configure(
            text=f"Keywords ({count} / {max_kw})", text_color=color
        )
        self._check_redundancies()

    def _check_redundancies(self):
        kws = [k.strip() for k in self.edit_kws_var.get().split(",") if k.strip()]
        redundancies = detect_redundant_keywords(kws)
        if redundancies:
            total_dup = sum(len(v) for v in redundancies.values())
            self.redundancy_lbl.configure(
                text=f"⚠ {total_dup} similar keywords detected!"
            )
            self.redundancy_btn.pack(side="right")
        else:
            self.redundancy_lbl.configure(text="")
            self.redundancy_btn.pack_forget()

    def _remove_redundancies(self):
        self._save_snapshot()
        kws = [k.strip() for k in self.edit_kws_var.get().split(",") if k.strip()]
        cleaned = remove_redundant_keywords(kws)
        self.edit_kws_var.set(", ".join(cleaned))

    def _get_kws_list(self):
        return [k.strip() for k in self.edit_kws_var.get().split(",") if k.strip()]

    def _set_kws_list(self, kws):
        self.edit_kws_var.set(", ".join([k.strip() for k in kws if k.strip()]))

    def _add_keyword_chip(self):
        new_kw = self.kw_add_entry.get().strip()
        if not new_kw:
            return
        self._save_snapshot()
        kws = self._get_kws_list()
        # prevent exact duplicates locally
        if new_kw.lower() not in [k.lower() for k in kws]:
            kws.append(new_kw)
            self._set_kws_list(kws)
        self.kw_add_entry.delete(0, "end")

    def _remove_keyword_chip(self, idx):
        self._save_snapshot()
        kws = self._get_kws_list()
        if 0 <= idx < len(kws):
            kws.pop(idx)
            self._set_kws_list(kws)

    def _move_keyword_chip(self, idx, direction):
        kws = self._get_kws_list()
        if direction == "up" and idx > 0:
            self._save_snapshot()
            kws[idx], kws[idx - 1] = kws[idx - 1], kws[idx]
            self._set_kws_list(kws)
        elif direction == "down" and idx < len(kws) - 1:
            self._save_snapshot()
            kws[idx], kws[idx + 1] = kws[idx + 1], kws[idx]
            self._set_kws_list(kws)

    # Re-entry guard to prevent infinite update loop

    def _trigger_render_keyword_chips(self):
        if hasattr(self, "_kw_render_after_id") and self._kw_render_after_id:
            self.after_cancel(self._kw_render_after_id)
        self._kw_render_after_id = self.after(50, self._render_keyword_chips)

    _rendering_chips = False

    def _render_keyword_chips(self):
        if self._rendering_chips:
            return
        self._rendering_chips = True

        for widget in self._kw_chip_widgets:
            widget.destroy()
        self._kw_chip_widgets.clear()

        kws = self._get_kws_list()

        # Grid layout for chips
        row, col = 0, 0
        for i, kw in enumerate(kws):
            chip = ctk.CTkFrame(
                self.kw_chips_frame, fg_color=C["surface"], corner_radius=CR
            )
            chip.grid(row=row, column=col, padx=2, pady=2, sticky="w")
            self._kw_chip_widgets.append(chip)

            # Left arrow
            if i > 0:
                l_btn = ctk.CTkButton(
                    chip,
                    text="◀",
                    width=16,
                    height=20,
                    fg_color="transparent",
                    text_color=C["text3"],
                    hover_color=C["surface2"],
                    font=ctk.CTkFont(size=10),
                    command=lambda idx=i: self._move_keyword_chip(idx, "up"),
                )
                l_btn.pack(side="left", padx=(2, 0))

            lbl = ctk.CTkLabel(
                chip,
                text=kw,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=C["text"],
            )
            lbl.pack(side="left", padx=4, pady=2)

            # Right arrow
            if i < len(kws) - 1:
                r_btn = ctk.CTkButton(
                    chip,
                    text="▶",
                    width=16,
                    height=20,
                    fg_color="transparent",
                    text_color=C["text3"],
                    hover_color=C["surface2"],
                    font=ctk.CTkFont(size=10),
                    command=lambda idx=i: self._move_keyword_chip(idx, "down"),
                )
                r_btn.pack(side="left", padx=(0, 0))

            x_btn = ctk.CTkButton(
                chip,
                text="×",
                width=20,
                height=20,
                fg_color="transparent",
                text_color=C["error"],
                hover_color=C["surface2"],
                command=lambda idx=i: self._remove_keyword_chip(idx),
            )
            x_btn.pack(side="right", padx=(0, 2))

            col += 1
            if col > 1:  # 2 columns max
                col = 0
                row += 1

        self._rendering_chips = False

    def _update_quality_score(self):
        if not getattr(self, "current_edit_file", None):
            self.quality_score_lbl.configure(
                text="SEO & Quality: —", text_color=C["text3"]
            )
            self.quality_bar.configure(progress_color=C["surface2"])
            self.quality_bar.set(0)
            self.quality_issues_lbl.configure(text="")
            return

        title = self.edit_title_var.get()
        desc = self.edit_desc_var.get()
        kws = self._get_kws_list()
        result = calculate_quality_score(title, desc, kws)
        score = result["score"]
        issues = result["issues"]
        status = result.get("status", "")

        if score >= 85:
            color = C["success"]
        elif score >= 60:
            color = C["warn"]
        else:
            color = C["error"]

        self.quality_score_lbl.configure(
            text=f"SEO & Quality: {score}% — {status}", text_color=color
        )
        self.quality_bar.configure(progress_color=color)
        self.quality_bar.set(score / 100)

        if issues:
            self.quality_issues_lbl.configure(
                text="\u2022 " + "\n\u2022 ".join(issues[:4]), text_color=color
            )
        else:
            self.quality_issues_lbl.configure(
                text="\u2713 All checks passed", text_color=C["success"]
            )

    def _get_companion_files(self, file_path):
        """Find files with same base name but different extensions in the same folder."""
        if not file_path or not os.path.exists(file_path):
            return []
        folder = os.path.dirname(file_path)
        base = os.path.splitext(os.path.basename(file_path))[0]
        companions = []
        for f in os.listdir(folder):
            f_base = os.path.splitext(f)[0]
            f_path = os.path.join(folder, f)
            if f_base == base and f_path != file_path and os.path.isfile(f_path):
                companions.append(f_path)
        return companions

    def _sync_to_companions(self, file_path, title, desc, kws):
        """Embed metadata to all companion files with the same base name."""
        companions = self._get_companion_files(file_path)
        if not companions:
            return 0
        count = 0
        copyright_text = self._get_copyright_text()
        author = self.author_entry.get().strip()
        for comp in companions:
            comp_hash = get_file_hash(comp)
            meta = {"title": title, "description": desc, "keywords": kws}
            set_cached_metadata(comp_hash, meta)
            if self.processor.embed_metadata(
                comp, title, desc, kws, copyright_text, author
            ):
                count += 1
        return count

    def _update_variant_badge(self):
        """Update the variant badge showing companion file count."""
        if not self.current_edit_file:
            self.variant_badge.configure(text="")
            return
        companions = self._get_companion_files(self.current_edit_file)
        if companions:
            exts = [
                os.path.splitext(os.path.basename(c))[1].upper().lstrip(".")
                for c in companions
            ]
            own_ext = os.path.splitext(self.current_edit_file)[1].upper().lstrip(".")
            all_exts = [own_ext] + sorted(exts)
            self.variant_badge.configure(
                text=f"Companion Variants Detected: [{', '.join(all_exts)}]"
            )
        else:
            self.variant_badge.configure(text="")

    def _dedup_keywords(self):
        self._save_snapshot()
        raw = [k.strip() for k in self.edit_kws_var.get().split(",") if k.strip()]
        max_kw = self._safe_int(self.max_kw_entry.get(), 50)
        cleaned = sanitize_keywords(raw, max_kw)
        self.edit_kws_var.set(", ".join(cleaned))

    def _lowercase_all_keywords(self):
        self._save_snapshot()
        raw = [k.strip() for k in self.edit_kws_var.get().split(",") if k.strip()]
        self.edit_kws_var.set(", ".join(lowercase_keywords(raw)))

    def _trim_all_keywords(self):
        self._save_snapshot()
        raw = [k for k in self.edit_kws_var.get().split(",")]
        self.edit_kws_var.set(", ".join(trim_keywords(raw)))

    def save_manual(self):
        if not self.current_edit_file or not os.path.exists(self.current_edit_file):
            return
        self._save_snapshot()
        title = self.edit_title_var.get()
        desc = self.edit_desc_var.get()
        kws = [k.strip() for k in self.edit_kws_var.get().split(",") if k.strip()]

        name = os.path.basename(self.current_edit_file)
        if self.processor.embed_metadata(
            self.current_edit_file,
            title,
            desc,
            kws,
            self._get_copyright_text(),
            self.author_entry.get().strip(),
        ):
            meta = {"title": title, "description": desc, "keywords": kws}
            if self.current_edit_hash:
                set_cached_metadata(self.current_edit_hash, meta)
            self.log(f"{name} (Manual save OK)", "success")

            # Sync companion files if enabled
            if self.sync_companions.get():
                synced = self._sync_to_companions(
                    self.current_edit_file, title, desc, kws
                )
                if synced > 0:
                    self.log(
                        f"  └─ Synced metadata to {synced} companion file(s)", "info"
                    )

            sub_dir = os.path.dirname(self.current_edit_file)
            temp_master = os.path.join(sub_dir, "metadata_output.csv")
            import csv

            with open(temp_master, "w", newline="", encoding="utf-8") as tf:
                tw = csv.writer(tf)
                tw.writerow(["Filename", "Title", "Description", "Keywords"])
                tw.writerow([name, title, desc, ",".join(kws)])
            generate_microstock_csvs(sub_dir, self._get_selected_csv_platforms())
        else:
            self.log(f"{name} (Manual save fail)", "error")

    def browse_input(self):
        dir_path = ctk.filedialog.askdirectory()
        if dir_path:
            self.input_dir.set(dir_path)

    def open_ftp_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("FTP / SFTP Uploader")
        dialog.geometry("450x450")
        dialog.configure(fg_color=C["bg"])
        dialog.transient(self)
        dialog.grab_set()

        _label(dialog, "Preset").pack(padx=12, pady=(12, 2), anchor="w")
        preset_cb = _combo(
            dialog, ["Custom", "Adobe Stock", "Shutterstock", "Vecteezy", "Freepik"]
        )
        preset_cb.pack(padx=12, pady=2, fill="x")

        _label(dialog, "Host").pack(padx=12, pady=2, anchor="w")
        host_entry = _entry(dialog)
        host_entry.insert(0, self.config.get("ftp_host", ""))
        host_entry.pack(padx=12, pady=2, fill="x")

        _label(dialog, "Port").pack(padx=12, pady=2, anchor="w")
        port_entry = _entry(dialog)
        port_entry.insert(0, "21")
        port_entry.pack(padx=12, pady=2, fill="x")

        _label(dialog, "Username").pack(padx=12, pady=2, anchor="w")
        user_entry = _entry(dialog)
        user_entry.insert(0, self.config.get("ftp_user", ""))
        user_entry.pack(padx=12, pady=2, fill="x")

        _label(dialog, "Password").pack(padx=12, pady=2, anchor="w")
        pass_entry = _entry(dialog, show="*")
        pass_entry.pack(padx=12, pady=2, fill="x")

        zip_only = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            dialog,
            text="Upload .ZIP only",
            variable=zip_only,
            fg_color=C["accent"],
            hover_color=C["accent_h"],
            font=ctk.CTkFont(family="Segoe UI", size=12),
        ).pack(padx=12, pady=10, anchor="w")

        status_lbl = ctk.CTkLabel(
            dialog,
            text="",
            text_color=C["success"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
        )
        status_lbl.pack(pady=5)

        def apply_preset(choice):
            hosts = {
                "Adobe Stock": "ftp.contributor.adobestock.com",
                "Shutterstock": "ftp.shutterstock.com",
                "Vecteezy": "ftp.vecteezy.com",
                "Freepik": "ftp.freepik.com",
            }
            if choice in hosts:
                host_entry.delete(0, "end")
                host_entry.insert(0, hosts[choice])

        preset_cb.configure(command=apply_preset)

        def test_conn():
            status_lbl.configure(text="Testing...", text_color=C["warn"])
            dialog.update()
            h, p = host_entry.get(), int(port_entry.get() or 21)
            u, pw = user_entry.get(), pass_entry.get()

            client = FTPClient(h, p, u, pw)
            ok, msg = client.connect()
            if ok:
                status_lbl.configure(text="Connection OK", text_color=C["success"])
                client.disconnect()
            else:
                status_lbl.configure(text=f"Fail: {msg}", text_color=C["error"])

        def start_upload():
            h, p = host_entry.get(), int(port_entry.get() or 21)
            u, pw = user_entry.get(), pass_entry.get()
            self.config["ftp_host"] = h
            self.config["ftp_user"] = u
            save_config(self.config)

            target_dir = self.input_dir.get()
            if not target_dir or not os.path.isdir(target_dir):
                status_lbl.configure(
                    text="No folder selected in main window", text_color=C["error"]
                )
                return

            dialog.destroy()
            threading.Thread(
                target=self._run_ftp_upload,
                args=(h, p, u, pw, target_dir, zip_only.get()),
                daemon=True,
            ).start()

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=10, side="bottom")
        _btn(
            btn_frame, "Test Connection", C["surface2"], C["border"], command=test_conn
        ).pack(side="left", expand=True, padx=(0, 4))
        _btn(
            btn_frame, "Start Upload", C["violet"], C["violet_h"], command=start_upload
        ).pack(side="right", expand=True, padx=(4, 0))

    def _run_ftp_upload(self, host, port, user, passwd, folder, zip_only):
        self.log(f"Connecting to FTP {host}...", "info")
        client = FTPClient(host, port, user, passwd)
        ok, msg = client.connect()
        if not ok:
            return self.log(f"FTP Connect Error: {msg}", "error")

        files_to_upload = []
        valid_exts = (".zip",) if zip_only else (".zip", ".eps", ".jpg", ".svg", ".csv")
        for root, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(valid_exts):
                    files_to_upload.append(os.path.join(root, f))

        if not files_to_upload:
            client.disconnect()
            return self.log("No valid files to upload via FTP.", "error")

        self.log(f"FTP Uploading {len(files_to_upload)} files...", "info")
        self.progress_bar.set(0)

        success = 0
        total = len(files_to_upload)
        for i, fpath in enumerate(files_to_upload):
            fname = os.path.basename(fpath)
            self.log(f"FTP: uploading {fname}...", "processing")
            if client.upload_file(fpath):
                self.log(f"FTP: OK {fname}", "success")
                success += 1
            else:
                self.log(f"FTP: FAIL {fname}", "error")
            self.after(0, self.progress_bar.set, (i + 1) / total)

        client.disconnect()
        self.log(f"FTP Upload Complete: {success}/{total} successful.", "info")

    def _get_allowed_extensions(self) -> set:
        exts = {ext for ext, var in self.fmt_vars.items() if var.get()}
        if ".jpg" in exts:
            exts.add(".jpeg")
        return exts

    def _is_allowed_file(self, filename: str) -> bool:
        ext = os.path.splitext(filename)[1].lower()
        return ext in self._get_allowed_extensions()

    def _watcher_loop(self):
        while True:
            time.sleep(3)
            if self.auto_watch.get() and not self.is_running:
                in_dir = self.input_dir.get()
                if in_dir and os.path.isdir(in_dir):
                    files = [
                        f
                        for f in os.listdir(in_dir)
                        if os.path.isfile(os.path.join(in_dir, f))
                        and self._is_allowed_file(f)
                    ]
                    if any(f not in self.processed_files for f in files):
                        self.after(0, lambda: self.start_processing(new_only=True))

    def toggle_pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_btn.configure(
                text="Resume", fg_color=C["success"], hover_color=C["success_h"]
            )
            self.log("Batch PAUSED.", "info")
        else:
            self.pause_event.set()
            self.pause_btn.configure(
                text="Pause", fg_color=C["warn"], hover_color=C["warn_h"]
            )
            self.log("Batch RESUMED.", "info")

    def cancel_batch(self):
        if self.is_running:
            self.cancel_flag = True
            self.pause_event.set()
            self.log("Canceling batch... finishing current active files.", "error")
            self.pause_btn.configure(state="disabled")
            self.cancel_btn.configure(state="disabled")

    def process_file(
        self,
        file_path,
        out_dir,
        ai,
        min_kw,
        max_kw,
        style_preset,
        extra_prompt,
        csv_logger,
    ):
        self.pause_event.wait()
        if self.cancel_flag:
            return

        name = os.path.basename(file_path)
        name = os.path.basename(file_path)
        self.log(f"[{name}] Starting processing pipeline...", "processing")

        def log_cb(msg, lvl="info"):
            self.log(msg, lvl)

        preview = extract_preview_image(file_path, self.processor, progress_callback=log_cb)
        if not preview:
            self.update_stats("error")
            return

        file_hash = get_file_hash(preview)
        cached = get_cached_metadata(file_hash)

        if cached:
            self.log(f"[{name}] [CACHE HIT] Metadata loaded from cache.", "cache")
            meta = cached
            status, color = "CACHE", C["violet"]
        else:
            meta = ai.generate_metadata(
                preview,
                min_kw,
                max_kw,
                style_preset,
                extra_prompt,
                log_callback=log_cb
            )

            if meta.get("is_fallback") or meta.get("error"):
                err_detail = meta.get("error_details", "fallback rejected")
                self.log(
                    f"[{name}] AI generation failed: {err_detail}",
                    "error",
                )
                self.update_stats("error")
                # Clean up preview since we're aborting
                try:
                    os.remove(preview)
                except OSError:
                    pass
                return

            set_cached_metadata(file_hash, meta)
            self.log(f"[{name}] Generated: Title='{meta.get('title', '')[:30]}...' | {len(meta.get('keywords', []))} Keywords", "success")
            status, color = "API", C["warn"]

            # Inject mandatory custom keywords on first API generation
            custom_kws_raw = self.config.get("custom_kw", "")
            if custom_kws_raw.strip():
                custom_kws = [k.strip() for k in custom_kws_raw.split(",") if k.strip()]
                # remove any exact overlaps in AI response
                ai_kws = [
                    k
                    for k in meta.get("keywords", [])
                    if k.lower() not in [ck.lower() for ck in custom_kws]
                ]

                pos = self.config.get("custom_kw_pos", "Start (Priority)")
                if pos == "Start (Priority)":
                    merged_kws = custom_kws + ai_kws
                else:
                    merged_kws = ai_kws + custom_kws
                meta["keywords"] = merged_kws

        try:
            with Image.open(preview) as opened_img:
                img = opened_img.copy()
                img.thumbnail((300, 300), Image.Resampling.LANCZOS)
        except (OSError, ValueError):
            img = None

        try:
            os.remove(preview)
        except OSError:
            pass

        meta = clean_metadata(meta, max_kw)

        base_name = os.path.splitext(name)[0]
        final_path = os.path.join(out_dir, name)
        shutil.move(file_path, final_path)

        title, desc, keywords = (
            meta.get("title", ""),
            meta.get("description", ""),
            meta.get("keywords", []),
        )

        if img:
            self.update_preview(img, status, color, meta, final_path, file_hash)

        if self.processor.embed_metadata(
            final_path,
            title,
            desc,
            keywords,
            self._get_copyright_text(),
            self.author_entry.get().strip(),
        ):
            self.log(f"[{name}] File completed and saved. ({len(keywords)} kw)", "success")


            if self.sync_companions.get():
                synced = self._sync_to_companions(final_path, title, desc, keywords)
                if synced > 0:
                    self.log(
                        f"  └─ Synced metadata to {synced} companion file(s)", "info"
                    )

            csv_logger.log(name, title, desc, keywords)

            if (
                getattr(self, "auto_zip", None)
                and self.auto_zip.get()
                and name.lower().endswith((".svg", ".eps"))
            ):
                import zipfile

                jpg_path = os.path.join(out_dir, base_name + ".jpg")
                if img:
                    try:
                        img.convert("RGB").save(jpg_path, "JPEG", quality=95)
                    except OSError:
                        pass
                zip_path = os.path.join(out_dir, base_name + ".zip")
                try:
                    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                        zf.write(final_path, arcname=name)
                        if os.path.exists(jpg_path):
                            zf.write(jpg_path, arcname=base_name + ".jpg")
                except OSError:
                    pass

        else:
            self.log(f"[{name}] ExifTool metadata embedding failed.", "error")
            self.update_stats("error")

    def start_offline_retag(self):
        csv_path = ctk.filedialog.askopenfilename(
            title="Select metadata CSV", filetypes=[("CSV files", "*.csv")]
        )
        if not csv_path:
            return

        target_dir = self.input_dir.get()
        if not target_dir or not os.path.isdir(target_dir):
            self.log("Set Folder first.", "error")
            return

        self.retag_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        threading.Thread(
            target=self._run_offline_retag, args=(csv_path, target_dir), daemon=True
        ).start()

    def _find_asset(self, target_dir: str, filename: str) -> str | None:
        for root, _dirs, files in os.walk(target_dir):
            if filename in files:
                return os.path.join(root, filename)
        return None

    def _run_offline_retag(self, csv_path: str, target_dir: str):
        import csv as csv_mod

        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                rows = list(csv_mod.DictReader(f))
        except (OSError, KeyError, ValueError) as e:
            self.log(f"CSV read error: {e}", "error")
            self.after(0, lambda: self.retag_btn.configure(state="normal"))
            self.after(0, lambda: self.start_btn.configure(state="normal"))
            return

        if not rows:
            self.log("CSV empty.", "error")
            self.after(0, lambda: self.retag_btn.configure(state="normal"))
            self.after(0, lambda: self.start_btn.configure(state="normal"))
            return

        max_kw = self._safe_int(self.max_kw_entry.get(), 50)
        total = len(rows)
        success = 0
        self.log(
            f"Offline Re-Tag: {total} rows from {os.path.basename(csv_path)}", "info"
        )
        self.progress_bar.set(0)

        for i, row in enumerate(rows):
            filename = row.get("Filename", "").strip()
            if not filename:
                self.log(f"Row {i + 1}: missing Filename", "error")
                continue

            asset_path = self._find_asset(target_dir, filename)
            if not asset_path:
                self.log(f"{filename} not found in folder", "error")
                continue

            title = row.get("Title", "").strip()
            desc = row.get("Description", "").strip()
            raw_kws = [
                k.strip() for k in row.get("Keywords", "").split(",") if k.strip()
            ]
            keywords = sanitize_keywords(raw_kws, max_kw)

            if self.processor.embed_metadata(
                asset_path,
                title,
                desc,
                keywords,
                self._get_copyright_text(),
                self.author_entry.get().strip(),
            ):
                file_hash = get_file_hash(asset_path)
                meta = {"title": title, "description": desc, "keywords": keywords}
                if not meta.get("is_fallback"):
                    set_cached_metadata(file_hash, meta)
                self.log(f"[OFFLINE SUCCESS] {filename}", "success")
                success += 1

                # Sync UI with the imported metadata for the inspector
                preview_img = extract_preview_image(asset_path, self.processor)
                if preview_img:
                    self.update_preview(
                        preview_img,
                        "Imported CSV",
                        C["success"],
                        meta,
                        asset_path,
                        file_hash,
                    )
            else:
                self.log(f"[OFFLINE FAIL] {filename}", "error")

            self.after(0, self.progress_bar.set, (i + 1) / total)

        self.log(f"Successfully tagged {success}/{total} files from CSV.", "success")
        self.after(0, lambda: self.retag_btn.configure(state="normal"))
        self.after(0, lambda: self.start_btn.configure(state="normal"))

    def start_processing(self, new_only=False):
        if self.is_running:
            return

        if not self.tools_ready:
            self.log("[WARN] External tools are still downloading, please wait...", "warn")
            return

        # Security: Background Auth Check
        is_valid, msg = self.auth.validate_session()
        if not is_valid and msg == "KICKED":
            self.log("Sesi berakhir: Akun digunakan di perangkat lain.", "error")
            import tkinter.messagebox

            tkinter.messagebox.showerror(
                "Akses Ditolak",
                "Sesi Berakhir: Akun Anda telah login di perangkat lain",
            )
            self.show_login_modal()
            return
        elif not is_valid:
            self.show_login_modal()
            return

        self._save_current_config()

        in_dir = self.input_dir.get()
        out_dir = in_dir
        if not in_dir:
            return self.log("Path missing.", "error")

        all_files = [
            f
            for f in os.listdir(in_dir)
            if os.path.isfile(os.path.join(in_dir, f)) and self._is_allowed_file(f)
        ]
        files = [f for f in all_files if f not in self.excluded_files]
        skipped_count = len(all_files) - len(files)

        if skipped_count:
            self.log(f"Skipping {skipped_count} excluded file(s)", "info")

        if new_only:
            files = [f for f in files if f not in self.processed_files]

        if not files:
            return self.log("No new files." if new_only else "No files.", "error")
        self.processed_files.update(files)

        self.is_running = True
        self.batch_session_stats = {
            "processed": 0,
            "skipped": skipped_count,
            "cost": self.batch_session_stats.get("cost", 0),
            "tokens_est": 0,
            "csvs": [],
        }
        self.cancel_flag = False
        self.pause_event.set()
        self.pause_btn.configure(
            text="Pause", fg_color=C["warn"], hover_color=C["warn_h"], state="normal"
        )
        self.cancel_btn.configure(state="normal")

        self.start_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self.stats = {"total": len(files), "success": 0, "error": 0}
        self.update_stats("total")
        self.stats["total"] = len(files)

        self.header_status.configure(
            text=f"Processing 0/{len(files)}", text_color=C["warn"]
        )

        paths = [os.path.join(in_dir, f) for f in files]
        threading.Thread(
            target=self._run_batch, args=(paths, out_dir), daemon=True
        ).start()

    def _run_batch(self, paths, out_dir):
        provider = self.config.get("provider", "Gemini")
        api_keys_dict = self.config.get("api_keys", {})
        api_key = api_keys_dict.get(provider, "")
        # Build failover dict from other configured providers
        failover_providers = {
            p: k for p, k in api_keys_dict.items() if p != provider and k
        }
        raw_model = self.config.get("model") or "Gemini"
        ai = AIService(
            provider,
            api_key,
            raw_model.split(" ")[0],
            self.config.get("temperature", 0.3),
            failover_providers=failover_providers,
        )
        processed_dir = os.path.join(out_dir, "Processed Assets")
        csv_dir = os.path.join(out_dir, "Metadata CSV")
        os.makedirs(processed_dir, exist_ok=True)
        os.makedirs(csv_dir, exist_ok=True)

        csv_logger = CSVLogger(os.path.join(csv_dir, "metadata_output.csv"))

        max_w = max(1, int(self.workers_slider.get()))
        total = len(paths)
        with ThreadPoolExecutor(max_workers=max_w) as executor:
            futures = {
                executor.submit(
                    self.process_file,
                    f,
                    processed_dir,
                    ai,
                    self.config["min_kw"],
                    self.config["max_kw"],
                    self.config["style_preset"],
                    self.config.get("extra_prompt", ""),
                    csv_logger,
                ): f
                for f in paths
            }
            for i, future in enumerate(as_completed(futures), 1):
                future.result()
                if not self.cancel_flag:
                    self.after(0, self.progress_bar.set, i / total)

        if self.cancel_flag:
            self.log("Batch CANCELED.", "error")
        else:
            self.log("Batch complete. Generating exports...", "info")
            generate_microstock_csvs(csv_dir, self._get_selected_csv_platforms())

            # Collect generated CSV list
            csv_files = [
                f
                for f in os.listdir(csv_dir)
                if f.endswith("_export.csv") or f == "metadata_output.csv"
            ]
            cost_delta = (
                self.batch_session_stats.get("cost", 0)
                - self.batch_session_stats["cost"]
            )
            self.batch_session_stats.update(
                {
                    "processed": self.stats["success"],
                    "errors": self.stats["error"],
                    "cost": cost_delta,
                    "tokens_est": int(cost_delta / 0.002 * 1000)
                    if cost_delta > 0
                    else 0,
                    "csvs": csv_files,
                    "out_dir": csv_dir,
                }
            )
            self.after(0, lambda: self._show_batch_summary())

    def _show_batch_summary(self):
        """Show batch processing summary dialog."""
        s = self.batch_session_stats
        dialog = ctk.CTkToplevel(self)
        dialog.title("Processing Summary Report")
        dialog.geometry("480x420")
        dialog.configure(fg_color=C["bg"])
        dialog.transient(self)
        dialog.grab_set()

        # Header
        ctk.CTkLabel(
            dialog,
            text="\u2714  Batch Processing Complete",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=C["success"],
        ).pack(padx=20, pady=(20, 4), anchor="w")

        _divider(dialog).pack(fill="x", padx=20, pady=8)

        # Stats grid
        stats_frame = ctk.CTkFrame(dialog, fg_color=C["surface"], corner_radius=CR)
        stats_frame.pack(fill="x", padx=20, pady=(0, 8))

        rows = [
            ("Files Processed", str(s.get("processed", 0)), C["success"]),
            ("Files Skipped (Excluded)", str(s.get("skipped", 0)), C["text3"]),
            ("Errors (Embed or Fallback)", str(s.get("errors", 0)), C["error"]),
            ("Estimated Tokens Used", f"~{s.get('tokens_est', 0):,}", C["warn"]),
            ("Estimated API Cost", f"${s.get('cost', 0):.4f}", C["warn"]),
        ]

        for i, (label, value, color) in enumerate(rows):
            r = ctk.CTkFrame(stats_frame, fg_color=C["surface"])
            r.pack(fill="x", padx=12, pady=3)
            ctk.CTkLabel(
                r,
                text=label,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=C["text2"],
            ).pack(side="left")
            ctk.CTkLabel(
                r,
                text=value,
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color=color,
            ).pack(side="right")

        # CSV files generated
        csvs = s.get("csvs", [])
        if csvs:
            ctk.CTkLabel(
                dialog,
                text="Generated CSV Exports:",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=C["text3"],
            ).pack(padx=20, pady=(8, 2), anchor="w")

            csv_frame = ctk.CTkFrame(dialog, fg_color=C["surface"], corner_radius=CR)
            csv_frame.pack(fill="x", padx=20, pady=(0, 8))
            for csv_f in csvs:
                ctk.CTkLabel(
                    csv_frame,
                    text=f"  \u2022  {csv_f}",
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    text_color=C["accent"],
                ).pack(anchor="w", padx=8, pady=1)

        _divider(dialog).pack(fill="x", padx=20, pady=4)

        # Action buttons
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(4, 16))

        def open_folder():
            out = s.get("out_dir", "")
            if out and os.path.isdir(out):
                os.startfile(out)

        def copy_summary():
            lines = [
                "=== NRA Metadata - Batch Processing Summary ===",
                f"Files Processed: {s.get('processed', 0)}",
                f"Files Skipped: {s.get('skipped', 0)}",
                f"Errors: {s.get('errors', 0)}",
                f"Estimated Tokens: ~{s.get('tokens_est', 0):,}",
                f"Estimated Cost: ${s.get('cost', 0):.4f}",
                f"CSV Exports: {', '.join(csvs)}",
            ]
            self.clipboard_clear()
            self.clipboard_append("\n".join(lines))
            self.log("Summary copied to clipboard.", "info")

        _btn(
            btn_frame,
            "Open Output Folder",
            C["accent"],
            C["accent_h"],
            command=open_folder,
            height=32,
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))
        _btn(
            btn_frame,
            "Copy Summary to Clipboard",
            C["violet"],
            C["violet_h"],
            command=copy_summary,
            height=32,
        ).pack(side="left", expand=True, fill="x", padx=(4, 0))

        _btn(
            btn_frame,
            "Close",
            C["surface2"],
            C["border"],
            command=dialog.destroy,
            height=32,
            width=60,
        ).pack(side="right", padx=(8, 0))


