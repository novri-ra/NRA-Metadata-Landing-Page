import json
import os
import queue
import threading
import tkinter as tk
from datetime import UTC, datetime

import customtkinter as ctk
import requests
from controllers.offline_retag_controller import start_offline_retag

from backend.core.config_manager import (
    get_cache_hits,
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
from backend.services.folder_watcher import FolderWatcher
from backend.services.ftp_uploader import FTPUploader
from packages.shared_utils.csv_exporter import (
    build_editorial_caption,
    generate_microstock_csvs,
    upsert_editorial_csv,
    upsert_metadata_csv,
)
from packages.shared_utils.env_check import run_environment_checks
from packages.shared_utils.filter import (
    autofix_compliance,
    calculate_quality_score,
    clean_metadata,
    detect_redundant_keywords,
    is_placeholder_title,
    lowercase_keywords,
    remove_redundant_keywords,
    sanitize_keywords,
    trim_keywords,
    validate_compliance,
)
from packages.shared_utils.license_manager import AuthClient
from packages.shared_utils.presets import get_preset
from packages.shared_utils.tools_setup import ensure_tools_installed
from packages.shared_utils.updater import check_github_release
from ui.dialogs.batch_apply_dialog import show_batch_apply
from ui.dialogs.batch_replace_dialog import show_batch_replace
from ui.dialogs.batch_summary_dialog import show_batch_summary
from ui.dialogs.blacklist_dialog import show_blacklist_manager
from ui.dialogs.ftp_dialog import show_ftp_dialog
from ui.dialogs.keyword_presets_dialog import show_keyword_presets
from ui.theme import (
    CR,
    C,
    _btn,
    _entry,
    _frame,
    _label,
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

        self.processor = ExifToolClient()
        self.pool = FileWorkerPool(
            {
                "log": self.log,
                "stats": self._on_pool_stats,
                "progress": lambda v: self._call_main(self.progress_bar.set, v),
                "preview": self._on_pool_preview,
                "file_status": self._on_file_status,
                "batch_complete": self._on_batch_complete,
                "finished": self._on_pool_finished,
                "token_usage": self._on_token_usage,
            }
        )
        self.stats = {"total": 0, "success": 0, "error": 0}
        self.current_preview_img = None
        self.processed_files = set()
        self.excluded_files = set()
        self.queue_status = {}
        self._batch_files = set()
        self._total_tokens = 0
        self._total_cost = 0.0
        self.batch_session_stats = {
            "processed": 0,
            "skipped": 0,
            "cost": 0.0,
            "csvs": [],
            "tokens_est": 0,
        }

        self.current_edit_file = None
        self.current_edit_hash = None

        self.undo_stack = []
        self.redo_stack = []
        self._is_undoing = False

        self.log_buffer = []
        self.log_lock = threading.Lock()
        self._log_queue = queue.Queue()
        self._tk_queue = queue.Queue()
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
                "gemini-3.1-pro-preview",
                "gemini-2.0-flash",
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
            "Custom": ["gpt-4o-mini (Default)"],
        }

        # Restore previously fetched model lists
        for prov, cached in self.config.get("model_cache", {}).items():
            if cached:
                self.MODEL_MAP[prov] = cached

        self._restore_geometry()
        self.build_ui()
        self.after(100, self._flush_log_queue)
        self.after(100, self._flush_tk_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Keyboard shortcuts bound at startup, independent of the auth modal.
        self.bind("<Control-z>", lambda e: self.undo_metadata())
        self.bind("<Control-y>", lambda e: self.redo_metadata())

        # Auto-Watch switch drives the watcher without depending on the modal.
        self.after(100, self._apply_auto_watch_startup)

        # Update initial key counter
        self.after(
            10, lambda: self._update_keys_counter(self.config.get("provider", "Gemini"))
        )

        # Initial Auth Check
        self.after(100, self._check_initial_auth)
        self.after(
            2000,
            lambda: check_github_release(
                callback=lambda info: self._call_main(
                    self._show_update_banner, info
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

        def _bg_validate():
            try:
                is_valid, msg = self.auth.validate_session()
            except (requests.RequestException, json.JSONDecodeError, ValueError) as e:
                try:
                    self.log(f"[AUTH] Session check error: {type(e).__name__}: {e}", "error")
                except (tk.TclError, RuntimeError):
                    pass
                self._call_main(self.show_login_modal)
                return
            if not is_valid:
                self._call_main(self.show_login_modal)
                
        threading.Thread(target=_bg_validate, daemon=True).start()

    def show_login_modal(self):
        if getattr(self, "_auth_modal_open", False):
            return
        self._auth_modal_open = True
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

            is_excluded = f in self.excluded_files
            file_status = self.queue_status.get(f)

            # Determine badge color and text from live status
            if file_status == "processing":
                badge_color = C["cyan"]
                badge_text = "Processing"
            elif file_status == "done":
                badge_color = C["success"]
                badge_text = "\u2713 Done"
            elif file_status == "failed":
                badge_color = C["error"]
                badge_text = "Failed"
            elif f in self.processed_files and f not in self._batch_files:
                # A file finished in an earlier batch still shows Done; a file
                # that belongs to the current batch but never got a terminal
                # status (cancelled before start, crashed worker) must not be
                # green -- fall through to Pending instead.
                badge_color = C["success"]
                badge_text = "\u2713 Done"
            else:
                badge_color = C["text3"]
                badge_text = "Pending"

            # Use boolean var for exclude toggle
            var = ctk.BooleanVar(value=is_excluded)
            self._queue_vars[f] = var

            def on_toggle(filename=f, v=var):
                if v.get():
                    self.excluded_files.add(filename)
                else:
                    self.excluded_files.discard(filename)
                self._refresh_file_queue()

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

            if is_excluded:
                badge_color = C["border"]
                badge_text = "Skipped"

            ctk.CTkLabel(
                row,
                text=badge_text,
                width=70,
                corner_radius=4,
                fg_color=badge_color,
                text_color=C["bg"] if badge_color not in ("transparent", C["text3"]) else C["text"],
                font=ctk.CTkFont(size=9, weight="bold"),
            ).pack(side="left", padx=4, pady=4)

            lbl = ctk.CTkLabel(
                row,
                text=f,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=C["text3"] if is_excluded else C["text"],
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

    def _on_file_status(self, name, status):
        self.queue_status[name] = status
        self._call_main(self._refresh_file_queue)

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

        from backend.core.config_manager import DB_PATH as db_path

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
        show_keyword_presets(self)

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
        self._require_license(self._do_batch_apply, "Batch Apply Metadata...")

    def _do_batch_apply(self):
        show_batch_apply(self)

    # ── Logging ──────────────────────────────────────────────────────────
    # ── Blacklist Manager ───────────────────────────────────────────────
    def open_blacklist_manager(self):
        show_blacklist_manager(self)

    # ── Batch Find & Replace ─────────────────────────────────────────────
    def open_batch_replace(self):
        self._require_license(self._do_batch_replace, "Batch Find & Replace")

    def _do_batch_replace(self):
        show_batch_replace(self)

    def log(self, message: str, level="info"):
        self._log_queue.put((message, level))

    def _call_main(self, fn, *args, **kwargs):
        self._tk_queue.put((fn, args, kwargs))

    def _flush_log_queue(self):
        if not hasattr(self, "console"):
            self.after(100, self._flush_log_queue)
            return
        processed = 0
        edited = False
        try:
            while processed < 300:
                message, level = self._log_queue.get_nowait()
                entry = {
                    "ts": datetime.now(UTC).strftime("%H:%M:%S"),
                    "level": level,
                    "msg": message,
                }
                with self.log_lock:
                    self.log_buffer.append(entry)
                    if len(self.log_buffer) > 5000:
                        self.log_buffer.pop(0)

                q = self.log_search_var.get().lower()
                flt = self.log_level_var.get().lower()
                if (flt == "all" or flt == level) and (
                    not q or q in message.lower()
                ):
                    if not edited:
                        self.console.configure(state="normal")
                        edited = True
                    tb = self.console._textbox
                    tb.insert("end", f"[{entry['ts']}] ", "timestamp")
                    tb.insert("end", f"[{level.upper()}] ", level)
                    tb.insert("end", f"{message}\n", level)
                processed += 1
        except (queue.Empty, RuntimeError):
            pass
        if edited:
            self.console.see("end")
            self.console.configure(state="disabled")
        # Huge batches drain in bounded slices (300/tick) so the paint loop
        # stays responsive; scroll once per slice, not per line.
        interval = 25 if processed >= 300 else 100
        self.after(interval, self._flush_log_queue)

    def _flush_tk_queue(self):
        try:
            while True:
                fn, args, kwargs = self._tk_queue.get_nowait()
                try:
                    fn(*args, **kwargs)
                except tk.TclError:
                    pass
        except queue.Empty:
            pass
        self.after(100, self._flush_tk_queue)

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
                "target_kw": 45,
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
                "target_kw": 50,
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
                "target_kw": 30,
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
        if "target_kw" in p:
            self.target_kw_entry.delete(0, "end")
            self.target_kw_entry.insert(0, str(p["target_kw"]))
        if "style_preset" in p:
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
            "target_kw": self._safe_int(self.target_kw_entry.get(), 49),
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

    def _on_token_usage(self, data):
        def _update():
            self._total_tokens += data.get("tokens", 0)
            from packages.shared_utils.cost_tracker import cost_tracker
            total_cost = cost_tracker.estimated_cost_usd
            self.cost_lbl.configure(
                text=f"Tokens: ~{self._total_tokens / 1000:.1f}k | Est. Cost: ${total_cost:.3f}  ·  Cache: {get_cache_hits()}"
            )
        self._call_main(_update)

    def _on_pool_stats(self, stats, running):
        def _update():
            self.stats = dict(stats)
            self.stats_lbl.configure(
                text=f"Total: {self.stats['total']}  ·  Success: {self.stats['success']}  ·  Error: {self.stats['error']}"
            )
            from packages.shared_utils.cost_tracker import cost_tracker
            total_cost = cost_tracker.estimated_cost_usd
            self.cost_lbl.configure(
                text=f"Tokens: ~{self._total_tokens / 1000:.1f}k | Est. Cost: ${total_cost:.3f}  ·  Cache: {get_cache_hits()}"
            )

            # Update header status
            if running:
                done = self.stats["success"] + self.stats["error"]
                self.header_status.configure(
                    text=f"Processing {done}/{self.stats['total']}",
                    text_color=C["warn"],
                )
            else:
                self.header_status.configure(text="Ready", text_color=C["text3"])

        self._call_main(_update)

    def _on_pool_preview(self, img, status_text, status_tag, meta, out_path, file_hash):
        color_map = {"cache": C["violet"], "api": C["warn"], "success": C["success"]}
        status_color = color_map.get(status_tag, C["warn"])
        self.update_preview(
            img, status_text, status_color, meta, out_path, file_hash
        )

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

        self._call_main(_draw)

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

            # We DO NOT read from api_key_text here. 
            # sidebar_panel.py already updates self.config["api_keys"][provider] with raw text 
            # before it applies masking. Reading from widget here would save asterisks to disk.

            # Clean old legacy key
            self.config.pop("api_key", None)

            self.config.update(
                {
                    "provider": provider,
                    "model": self.model_cb.get(),
                    "temperature": round(self._safe_float(self.temp_slider.get(), 0.3), 1),
                    "style_preset": self.style_cb.get(),
                    "target_kw": self._safe_int(
                        self.target_kw_entry.get(), 49
                    ) if hasattr(self, "target_kw_entry") else 49,
                    "custom_kw": self.custom_kw_entry.get(),
                    "custom_kw_pos": self.custom_kw_pos.get(),
                    "extra_prompt": self.extra_prompt_entry.get(),
                    "workers": int(self.workers_slider.get()),
                    "delay": (
                        int(self.cooldown_delay_entry.get())
                        if hasattr(self, "cooldown_delay_entry")
                        else 10
                    ),
                    "custom_base_url": (
                        self.base_url_entry.get().strip()
                        if hasattr(self, "base_url_entry")
                        else ""
                    ),
                    "formats": {ext: var.get() for ext, var in self.fmt_vars.items()},
                    "author": self.author_entry.get().strip(),
                    "copyright": self.copyright_entry.get().strip(),
                    "csv_platforms": list(self._get_selected_csv_platforms()),
                    "custom_endpoint": {
                        "name": self.custom_name_entry.get().strip() if hasattr(self, "custom_name_entry") else "My Custom API",
                        "base_url": self.base_url_entry.get().strip() if hasattr(self, "base_url_entry") else "",
                        "package": self.custom_package_cb.get() if hasattr(self, "custom_package_cb") else "openai",
                    },
                    "auto_watch": self.auto_watch.get(),
                    "auto_zip_vector": self.auto_zip.get(),
                    "target_platform": self.target_plat_var.get(),
                    "sync_companion_files": self.sync_companions.get(),
                    "last_folder": self.input_dir.get(),
                    "active_profile": self.preset_var.get(),
                    "is_editorial": bool(self.config.get("editorial_enabled")),
                    "editorial_city": self.config.get("editorial_city", ""),
                    "editorial_country": self.config.get("editorial_country", ""),
                    "editorial_country_code": self.config.get(
                        "editorial_country_code", ""
                    ),
                    "editorial_date": self.config.get("editorial_date", ""),
                }
            )
            if self.outer_paned.winfo_ismapped():
                self.config["sidebar_width"] = self.outer_paned.sash_coord(0)[0]
            if self.content_paned.winfo_ismapped():
                self.config["log_width"] = self.content_paned.sash_coord(0)[0]
            self.config["window_geometry"] = self.geometry()
        except (tk.TclError, ValueError):
            pass
        from backend.core.config_manager import save_config

        save_config(self.config)

    def _on_close(self):
        self._stop_watcher()
        self.pool.cancel()
        self._save_current_config()
        self.destroy()

    def _load_keys_from_file(self):
        from tkinter import filedialog

        path = filedialog.askopenfilename(
            filetypes=[
                ("Supported Files", "*.txt;*.csv;*.json;*.env"),
                ("Text Files", "*.txt"),
                ("CSV Files", "*.csv"),
                ("All Files", "*.*"),
            ]
        )
        if not path:
            return

        provider = self.provider_cb.get()
        try:
            from backend.core.utils.key_manager import load_keys_from_file

            keys = load_keys_from_file(path)
            if keys:
                raw_text = "\n".join(keys)
                self.config["api_keys"][provider] = raw_text
                self.api_key_text.delete("1.0", "end")
                
                from backend.core.utils.key_manager import mask_api_key
                
                is_foc = getattr(self.sidebar, "_is_key_focused", False) if hasattr(self, "sidebar") else False
                if is_foc:
                    self.api_key_text.insert("1.0", raw_text)
                else:
                    self.api_key_text.insert("1.0", "\n".join(mask_api_key(line) for line in keys))
                    
                self._save_current_config()
                self.keys_counter_lbl.configure(text=f"({len(keys)} keys loaded)")
                self.log(f"Loaded {len(keys)} API key(s) for {provider} from file.", "success")
            else:
                self.log("File is empty or contains no valid keys.", "error")
        except OSError as e:
            self.log(f"Failed to read file: {e}", "error")

    def _update_keys_counter(self, provider):
        if hasattr(self, "keys_counter_lbl"):
            from backend.core.utils.key_manager import parse_api_keys
            raw = self.config.get("api_keys", {}).get(provider, "")
            keys = parse_api_keys(raw)
            self.keys_counter_lbl.configure(text=f"({len(keys)} keys loaded)")

    def _fetch_models(self):
        provider = self.provider_cb.get()
        from backend.core.utils.key_manager import parse_api_keys
        
        raw = self.config.get("api_keys", {}).get(provider, "")
        
        # If the user is currently typing in the box and hasn't blurred, we should try to use the box text
        # But wait, if it's focused, it shows raw text anyway.
        is_foc = getattr(self.sidebar, "_is_key_focused", False) if hasattr(self, "sidebar") else False
        if is_foc and hasattr(self, "api_key_text"):
            raw = self.api_key_text.get("1.0", "end-1c").strip()
            
        keys = parse_api_keys(raw)
        api_key = keys[0] if keys else ""

        if not api_key:
            self.log(f"Please enter an API Key for {provider} first.", "error")
            return

        self.fetch_models_btn.configure(text="[ Mengambil... ]", state="disabled")
        self.update_idletasks()

        def _bg_fetch():
            from backend.ai.provider_router import AIService

            ai = AIService(provider, api_key)
            models = ai.fetch_available_models()
            self._call_main(self._fetch_models_done, provider, models)

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
        self.config.setdefault("model_cache", {})[provider] = models
        current_provider = self.provider_cb.get()

        if current_provider == provider:
            self.model_cb.configure(values=models)
            saved_model = self.config.get("model", "")
            if saved_model and saved_model in models:
                self.model_cb.set(saved_model)
            elif models:
                self.model_cb.set(models[0])
            self.log(f"Successfully updated models for {provider}.", "success")
        self._save_current_config()

    def _update_model_list(self, choice):
        is_custom = choice == "Custom"
        models = self.MODEL_MAP.get(choice, [])
        self.model_cb.configure(values=models, state="normal" if is_custom else "readonly")
        saved = self.config.get("model", "")
        if saved and saved in models:
            self.model_cb.set(saved)
        elif models:
            self.model_cb.set(models[0])
            self.config["model"] = models[0]
        else:
            self.model_cb.set("")
            self.config["model"] = ""

    def _on_provider_change(self, choice):
        getattr(
            self, "current_provider", self.config.get("provider", "Gemini")
        )
        self._loading_provider = True

        if "api_keys" not in self.config:
            self.config["api_keys"] = {}

        # The raw keys are already saved on FocusOut or typing (if focused).
        # We don't read from api_key_text here because it might be masked.
        
        self.current_provider = choice
        self.config["provider"] = choice

        # Load new provider's keys
        if hasattr(self, "api_key_text"):
            self.api_key_text.delete("1.0", "end")
            target_key = self.config["api_keys"].get(choice, "")
            if target_key:
                from backend.core.utils.key_manager import mask_api_key
                
                # Check if it's focused right now
                is_foc = getattr(self.sidebar, "_is_key_focused", False) if hasattr(self, "sidebar") else False
                if is_foc:
                    self.api_key_text.insert("1.0", target_key)
                else:
                    self.api_key_text.insert("1.0", "\n".join(mask_api_key(line) for line in target_key.split("\n")))
            self._loading_provider = False

        # Update model list
        if hasattr(self, "_update_model_list"):
            self._update_model_list(choice)

        # Toggle custom endpoint fields visibility (Part 6)
        if hasattr(self, "custom_frame"):
            if choice == "Custom":
                self.custom_frame.pack(fill="x", padx=0, pady=0, after=self.fetch_models_btn)
                self.model_cb.configure(state="normal")
            else:
                self.custom_frame.pack_forget()
                self.model_cb.configure(state="readonly")

        # Update counter
        if hasattr(self, "_update_keys_counter"):
            self._update_keys_counter(choice)

        self._save_current_config()

    def _test_custom_connection(self):
        base_url = self.base_url_entry.get().strip()
        api_key = self.api_key_text.get("1.0", "end-1c").strip() if hasattr(self, "api_key_text") else ""
        model = self.model_cb.get().strip() if hasattr(self, "model_cb") else ""
        package = self.custom_package_cb.get() if hasattr(self, "custom_package_cb") else "openai"

        if not base_url:
            self.log("Please enter a Base URL first.", "error")
            return

        self.test_conn_btn.configure(text="Testing...", state="disabled")
        self.update_idletasks()

        def _bg_test():
            try:
                if package == "openai":
                    from backend.core.utils.key_manager import (
                        build_openai_compatible_client,
                    )
                    client = build_openai_compatible_client(base_url, api_key or "test", model)
                    models_list = client.models.list()
                    model_names = [m.id for m in models_list][:20]
                    self._call_main(self._test_conn_done, True, model_names)
                else:
                    import requests as _req
                    norm_url = base_url.rstrip("/")
                    if not norm_url.endswith("/v1"):
                        norm_url += "/v1"
                    resp = _req.get(
                        f"{norm_url}/models",
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=15,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    model_names = [m.get("id", "") for m in data.get("data", [])][:20]
                    self._call_main(self._test_conn_done, True, model_names)
            except (requests.RequestException, json.JSONDecodeError, ValueError) as e:
                self._call_main(self._test_conn_done, False, str(e))

        import threading
        threading.Thread(target=_bg_test, daemon=True).start()

    def _test_conn_done(self, ok, result):
        self.test_conn_btn.configure(text="Test Connection", state="normal")
        if ok:
            self.log(f"Connection successful! Found {len(result)} model(s).", "success")
            if result:
                self.MODEL_MAP["Custom"] = result
                self.model_cb.configure(values=result, state="normal")
                self.model_cb.set(result[0])
                self.config["model"] = result[0]
                self._save_current_config()
        else:
            self.log(f"Connection failed: {result}", "error")

    def _get_selected_csv_platforms(self) -> set:
        return {plat for plat, var in self.csv_vars.items() if var.get()}

    def _autofix_metadata(self):
        self._save_snapshot()
        title = self.edit_title_var.get()
        kws = [k.strip() for k in self.edit_kws_var.get().split(",") if k.strip()]
        plat = self.target_plat_var.get()

        fixed_title, fixed_kws = autofix_compliance(
            title,
            self.edit_desc_var.get(),
            kws,
            plat,
            os.path.basename(self.current_edit_file or ""),
        )
        self.edit_title_var.set(fixed_title)
        self.edit_kws_var.set(", ".join(fixed_kws))
        self._update_compliance()

    def _update_compliance(self):
        title = self.edit_title_var.get()
        kws = [k.strip() for k in self.edit_kws_var.get().split(",") if k.strip()]
        plat = self.target_plat_var.get()

        res = validate_compliance(title, self.edit_desc_var.get(), kws, plat)
        if res["valid"] and not res.get("warnings"):
            self.compliance_lbl.configure(
                text=f"● Compliant ({plat})", text_color=C["success"]
            )
        elif res["valid"]:
            warn_text = " | ".join(res["warnings"])
            self.compliance_lbl.configure(
                text=f"● {warn_text} ({plat})", text_color=C["warn_soft"]
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

    def _safe_float(self, val, default=0.0):
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    def _safe_int(self, val, default=0):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def _update_kw_counter(self):
        raw = self.edit_kws_var.get()
        count = len([k for k in raw.split(",") if k.strip()])
        target = self._safe_int(self.target_kw_entry.get(), 49) if hasattr(self, "target_kw_entry") else 49
        if count == target:
            color = C["success"]
        elif count < target:
            color = C["warn"]
        else:
            color = C["error"]
        self.kw_counter_lbl.configure(
            text=f"Keywords ({count} / {target})", text_color=color
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
        result = calculate_quality_score(
            title, desc, kws, self.target_plat_var.get()
        )
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

    def _sync_to_companions(self, file_path, title, desc, kws):
        """Embed metadata to all companion files with the same base name."""
        return sync_companion_metadata(
            file_path,
            title,
            desc,
            kws,
            self.processor,
            self._get_copyright_text(),
            self.author_entry.get().strip(),
        )

    def _update_variant_badge(self):
        """Update the variant badge showing companion file count."""
        if not self.current_edit_file:
            self.variant_badge.configure(text="")
            return
        companions = find_companion_files(self.current_edit_file)
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
        target_kw = self._safe_int(
            self.target_kw_entry.get(), 49
        ) if hasattr(self, "target_kw_entry") else 49
        cleaned = sanitize_keywords(raw, target_kw)
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
        self._require_license(self._save_manual_impl, "Save Metadata")

    def _save_manual_impl(self):
        if not self.current_edit_file or not os.path.exists(self.current_edit_file):
            return
        self._save_snapshot()
        target_kw = self._safe_int(
            self.target_kw_entry.get(), 49
        ) if hasattr(self, "target_kw_entry") else 49
        meta = clean_metadata(
            {
                "title": self.edit_title_var.get(),
                "description": self.edit_desc_var.get(),
                "keywords": [
                    k.strip()
                    for k in self.edit_kws_var.get().split(",")
                    if k.strip()
                ],
            },
            target_kw=target_kw,
        )
        title = meta["title"]
        desc = meta["description"]
        kws = meta["keywords"]

        name = os.path.basename(self.current_edit_file)
        if is_placeholder_title(title):
            self.log(
                f"{name} (Manual save blocked: title empty or still a fallback placeholder)",
                "error",
            )
            # Show a modal so fallback metadata can't silently slip into EXIF.
            try:
                import tkinter.messagebox

                tkinter.messagebox.showwarning(
                    "Metadata Tidak Valid",
                    "Title kosong atau masih berisi placeholder fallback AI.\n"
                    "Perbaiki title terlebih dahulu sebelum menyimpan.",
                )
            except (tk.TclError, RuntimeError) as e:
                self.log(f"UI Error suppressed: {e}", "error")
            return
        is_editorial = bool(self.config.get("editorial_enabled"))
        editorial_city = self.config.get("editorial_city", "")
        editorial_country = self.config.get("editorial_country", "")
        editorial_country_code = self.config.get("editorial_country_code", "")
        editorial_date = self.config.get("editorial_date", "")
        if is_editorial:
            desc = build_editorial_caption(
                desc, editorial_city, editorial_country, editorial_date
            )
        if self.processor.embed_metadata(
            self.current_edit_file,
            title,
            desc,
            kws,
            self._get_copyright_text(),
            self.author_entry.get().strip(),
            is_editorial=is_editorial,
            city=editorial_city,
            country=editorial_country,
            country_code=editorial_country_code,
            date_created=editorial_date,
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
            upsert_metadata_csv(temp_master, name, title, desc, kws)
            if is_editorial:
                upsert_editorial_csv(
                    temp_master,
                    name,
                    title,
                    desc,
                    kws,
                    is_editorial,
                    editorial_city,
                    editorial_country,
                    editorial_country_code,
                    editorial_date,
                )
            platforms = self._get_selected_csv_platforms()
            selected = self.target_plat_var.get()
            if selected and selected != "Generic":
                platforms.add(selected)
            generate_microstock_csvs(sub_dir, platforms)
        else:
            self.log(f"{name} (Manual save fail)", "error")

    def browse_input(self):
        dir_path = ctk.filedialog.askdirectory()
        if dir_path:
            self.input_dir.set(dir_path)

    def open_ftp_dialog(self):
        self._require_license(self._do_open_ftp, "FTP Upload")

    def _do_open_ftp(self):
        show_ftp_dialog(self)

    def _run_ftp_upload(self, host, port, user, passwd, folder, zip_only):
        uploader = FTPUploader(
            host,
            port,
            user,
            passwd,
            cancel_check=lambda: self.pool.cancel_flag,
        )
        uploader.upload_batch(
            folder,
            zip_only,
            log_cb=self.log,
            progress_cb=lambda frac: self._call_main(self.progress_bar.set, frac),
        )

    def _get_allowed_extensions(self) -> set:
        exts = {ext for ext, var in self.fmt_vars.items() if var.get()}
        if ".jpg" in exts:
            exts.add(".jpeg")
        return exts

    def _is_allowed_file(self, filename: str) -> bool:
        ext = os.path.splitext(filename)[1].lower()
        return ext in self._get_allowed_extensions()

    def _apply_auto_watch_startup(self):
        if self.auto_watch.get():
            self._start_watcher()

    def _start_watcher(self):
        if getattr(self, "_watcher", None) is None:
            self._watcher = FolderWatcher(
                get_directory=lambda: self.input_dir.get(),
                is_allowed=self._is_allowed_file,
                is_busy=lambda: self.pool.is_running,
                on_new_files=lambda files: self._call_main(self._on_watcher_files, files),
            )
        if not self._watcher.running:
            self._watcher.start()
            self.log("Auto-Watch aktif.", "info")

    def _stop_watcher(self):
        watcher = getattr(self, "_watcher", None)
        if watcher and watcher.running:
            watcher.stop()
            self.log("Auto-Watch dimatikan.", "info")

    def _toggle_auto_watch(self):
        if self.auto_watch.get():
            self._start_watcher()
        else:
            self._stop_watcher()
        self._save_current_config()

    def _on_watcher_files(self, files):
        if self.auto_watch.get() and not self.pool.is_running:
            if any(f not in self.processed_files for f in files):
                self.start_processing(new_only=True)

    def toggle_pause(self):
        if self.pool.toggle_pause():
            self.pause_btn.configure(
                text="Resume", fg_color=C["success"], hover_color=C["success_h"]
            )
            self.log("Batch PAUSED.", "info")
        else:
            self.pause_btn.configure(
                text="Pause", fg_color=C["warn"], hover_color=C["warn_h"]
            )
            self.log("Batch RESUMED.", "info")

    def cancel_batch(self):
        if not self.pool.is_running:
            return
        self.pool.cancel()
        self.log("Canceling batch... finishing current active files.", "error")
        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="disabled")
        self.cancel_btn.configure(state="disabled")
        self._call_main(self._refresh_file_queue)

    def start_offline_retag(self):
        self._require_license(self._do_offline_retag, "Import Metadata from CSV...")

    def _do_offline_retag(self):
        start_offline_retag(self)

    def _require_license(self, action, description, *args):
        import threading

        def _check():
            try:
                is_valid, msg = self.auth.validate_session()
            except (requests.RequestException, json.JSONDecodeError, ValueError) as e:
                self.log(
                    f"[AUTH] Session check error: {type(e).__name__}: {e}", "error"
                )
                self._call_main(
                    self._run_licensed_action, False, "ERROR", action, description, args
                )
                return
            self._call_main(
                self._run_licensed_action, is_valid, msg, action, description, args
            )

        threading.Thread(target=_check, daemon=True).start()

    def _run_licensed_action(self, is_valid, msg, action, description, args):
        if not is_valid:
            self.log(f"{description} dibatalkan: {msg}", "error")
            if msg == "KICKED":
                import tkinter.messagebox

                tkinter.messagebox.showerror(
                    "Akses Ditolak",
                    "Sesi Berakhir: Akun Anda telah login di perangkat lain",
                )
            self.show_login_modal()
            return
        action(*args)

    def start_processing(self, new_only=False):
        if self.pool.is_running and not self.pool.reap_stale():
            self.log("Batch masih menyelesaikan file aktif...", "warn")
            return

        if not self.tools_ready:
            self.log("[WARN] External tools are still downloading, please wait...", "warn")
            return

        self.start_btn.configure(state="disabled")

        def _auth_check():
            try:
                is_valid, msg = self.auth.validate_session()
            except (requests.RequestException, json.JSONDecodeError, ValueError) as e:
                try:
                    self.log(f"[AUTH] Session check error: {type(e).__name__}: {e}", "error")
                except (tk.TclError, RuntimeError) as e:
                    self.log(f"UI Error suppressed: {e}", "error")
                self._call_main(self._on_auth_checked, False, "ERROR", new_only)
                return
            self._call_main(self._on_auth_checked, is_valid, msg, new_only)
            
        import threading
        threading.Thread(target=_auth_check, daemon=True).start()

    def _on_auth_checked(self, is_valid, msg, new_only):
        if not is_valid and msg == "KICKED":
            self.start_btn.configure(state="normal")
            self.log("Sesi berakhir: Akun digunakan di perangkat lain.", "error")
            import tkinter.messagebox
            tkinter.messagebox.showerror(
                "Akses Ditolak",
                "Sesi Berakhir: Akun Anda telah login di perangkat lain",
            )
            self.show_login_modal()
            return
        elif not is_valid:
            self.start_btn.configure(state="normal")
            self.show_login_modal()
            return

        self._save_current_config()

        in_dir = self.input_dir.get()
        out_dir = in_dir
        if not in_dir:
            self.start_btn.configure(state="normal")
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
            self.start_btn.configure(state="normal")
            return self.log("No new files." if new_only else "No files.", "error")
        self.processed_files.update(files)
        self.queue_status.clear()
        self._batch_files = set(files)

        self.pause_btn.configure(
            text="Pause", fg_color=C["warn"], hover_color=C["warn_h"], state="normal"
        )
        self.cancel_btn.configure(state="normal")
        self.start_btn.configure(state="disabled")
        self.progress_bar.set(0)

        options = {
            "provider": self.config.get("provider", "Gemini"),
            "api_keys": self.config.get("api_keys", {}),
            "model": self.config.get("model", "") or "Gemini",
            "temperature": self.config.get("temperature", 0.3),
            "target_kw": self.config.get("target_kw", 49),
            "platform": self.target_plat_var.get(),
            "style_preset": self.config["style_preset"],
            "extra_prompt": self.config.get("extra_prompt", ""),
            "custom_kw": self.config.get("custom_kw", ""),
            "custom_kw_pos": self.config.get("custom_kw_pos", "Start (Priority)"),
            "copyright": self._get_copyright_text(),
            "author": self.author_entry.get().strip(),
            "sync_companions": self.sync_companions.get(),
            "auto_zip": bool(
                getattr(self, "auto_zip", None) and self.auto_zip.get()
            ),
            "csv_platforms": self._get_selected_csv_platforms(),
            "workers": max(1, int(self.workers_slider.get())),
            "custom_base_url": self.config.get("custom_base_url", ""),
            "delay": float(self.config.get("delay", 10)),
            "skipped_count": skipped_count,
        }
        paths = [os.path.join(in_dir, f) for f in files]
        self.pool.start(paths, out_dir, options)

    def _on_batch_complete(self, summary):
        self.batch_session_stats.update(summary)
        self._call_main(self._show_batch_summary)

    def _on_pool_finished(self):
        self._call_main(self._on_pool_finished_main)

    def _on_pool_finished_main(self):
        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="normal")
        self.cancel_btn.configure(state="normal")
        self._refresh_file_queue()
        self._show_batch_end_summary()

    def _show_batch_summary(self):
        show_batch_summary(self)

    def _show_batch_end_summary(self):
        s = self.stats
        success = s.get("success", 0)
        error = s.get("error", 0)
        skipped = self.pool.session_stats.get("skipped", 0)
        total = s.get("total", 0)

        if self.pool.cancel_flag:
            color = C["error"]
            label = f"Cancelled — {success} done, {error} failed, {skipped} skipped"
        elif error:
            color = C["error"]
            label = f"Done — {success}/{total} succeeded, {error} failed"
        else:
            color = C["success"]
            label = f"All done — {success} files processed"
            if skipped:
                label += f", {skipped} skipped"

        self.header_status.configure(text=label, text_color=color)
        self.after(8000, lambda: self.header_status.configure(
            text="Ready", text_color=C["text3"],
        ))


