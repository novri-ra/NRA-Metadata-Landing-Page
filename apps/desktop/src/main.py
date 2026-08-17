import os
import shutil
import threading
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import customtkinter as ctk

from packages.media_processor.embedder import MediaProcessor
from packages.media_processor.previews import extract_preview_image
from packages.ai_engine.service import AIService
from packages.shared_utils.config import load_config, save_config
from packages.shared_utils.logger import CSVLogger
from packages.shared_utils.cache import get_file_hash, get_cached_metadata, set_cached_metadata
from packages.shared_utils.filter import clean_metadata, sanitize_keywords
from packages.shared_utils.csv_exporter import generate_microstock_csvs
from packages.shared_utils.tracker import tracker
from packages.shared_utils.cache import get_cache_hits
from packages.shared_utils.ftp_uploader import FTPClient

# ── Design System (Zinc + Indigo, inspired by Linear/Raycast) ────────────
C = {
    "bg":           "#09090b",   # zinc-950 — app canvas
    "surface":      "#18181b",   # zinc-900 — cards, sidebar
    "surface2":     "#27272a",   # zinc-800 — inputs, secondary
    "border":       "#3f3f46",   # zinc-700 — borders
    "border_sub":   "#27272a",   # zinc-800 — subtle dividers
    "text":         "#f4f4f5",   # zinc-100 — primary text
    "text2":        "#a1a1aa",   # zinc-400 — secondary text
    "text3":        "#71717a",   # zinc-500 — muted text
    "accent":       "#6366f1",   # indigo-500 — primary accent
    "accent_h":     "#4f46e5",   # indigo-600 — hover
    "success":      "#10b981",   # emerald-500
    "success_h":    "#059669",   # emerald-600
    "warn":         "#f59e0b",   # amber-500
    "warn_h":       "#d97706",   # amber-600
    "error":        "#ef4444",   # red-500
    "error_h":      "#dc2626",   # red-600
    "violet":       "#8b5cf6",   # violet-500
    "violet_h":     "#7c3aed",   # violet-600
}

FONT_BRAND  = ("Segoe UI", 16, "bold")
FONT_SEC    = ("Segoe UI", 11, "bold")   # section header
FONT_LBL    = ("Segoe UI", 12)           # labels
FONT_SM     = ("Segoe UI", 11)           # small text
FONT_XS     = ("Segoe UI", 10)           # extra small
FONT_BTN    = ("Segoe UI", 12, "bold")   # buttons
CR = 6  # corner radius

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ── Helpers ──────────────────────────────────────────────────────────────
def _frame(parent, **kw):
    kw.setdefault("fg_color", C["surface"])
    kw.setdefault("corner_radius", CR)
    return ctk.CTkFrame(parent, **kw)

def _label(parent, text, **kw):
    kw.setdefault("font", ctk.CTkFont(family="Segoe UI", size=12))
    kw.setdefault("text_color", C["text2"])
    return ctk.CTkLabel(parent, text=text, **kw)

def _entry(parent, text_var=None, **kw):
    kw.setdefault("fg_color", C["surface2"])
    kw.setdefault("border_color", C["border"])
    kw.setdefault("corner_radius", CR)
    kw.setdefault("font", ctk.CTkFont(family="Segoe UI", size=12))
    kw.setdefault("text_color", C["text"])
    return ctk.CTkEntry(parent, textvariable=text_var, **kw)

def _btn(parent, text, color=None, hover=None, **kw):
    kw.setdefault("fg_color", color or C["accent"])
    kw.setdefault("hover_color", hover or C["accent_h"])
    kw.setdefault("corner_radius", CR)
    kw.setdefault("font", ctk.CTkFont(family="Segoe UI", size=12, weight="bold"))
    kw.setdefault("height", 32)
    return ctk.CTkButton(parent, text=text, **kw)

def _combo(parent, values, **kw):
    kw.setdefault("fg_color", C["surface2"])
    kw.setdefault("border_color", C["border"])
    kw.setdefault("button_color", C["accent"])
    kw.setdefault("button_hover_color", C["accent_h"])
    kw.setdefault("dropdown_fg_color", C["surface"])
    kw.setdefault("dropdown_hover_color", C["surface2"])
    kw.setdefault("font", ctk.CTkFont(family="Segoe UI", size=12))
    kw.setdefault("dropdown_font", ctk.CTkFont(family="Segoe UI", size=12))
    kw.setdefault("corner_radius", CR)
    return ctk.CTkComboBox(parent, values=values, **kw)

def _slider(parent, **kw):
    kw.setdefault("button_color", C["accent"])
    kw.setdefault("button_hover_color", C["accent_h"])
    kw.setdefault("fg_color", C["surface2"])
    return ctk.CTkSlider(parent, **kw)

def _section_header(parent, text):
    """Render a muted uppercase section header with a thin line after it."""
    f = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(f, text=text.upper(), font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                 text_color=C["text3"]).pack(side="left")
    ctk.CTkFrame(f, height=1, fg_color=C["border_sub"]).pack(side="left", fill="x", expand=True, padx=(8, 0), pady=1)
    return f

def _divider(parent):
    return ctk.CTkFrame(parent, height=1, fg_color=C["border_sub"])


# ═══════════════════════════════════════════════════════════════════════════
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NRA Metadata")
        self.geometry("1200x720")
        self.minsize(1060, 680)
        self.configure(fg_color=C["bg"])

        self.input_dir = ctk.StringVar()
        self.output_dir = ctk.StringVar()

        self.config = load_config()
        self.processor = MediaProcessor()
        self.stats = {"total": 0, "success": 0, "error": 0}
        self.current_preview_img = None
        self.processed_files = set()
        self.is_running = False
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.cancel_flag = False

        self.current_edit_file = None
        self.current_edit_hash = None

        self.MODEL_MAP = {
            "Gemini": ["gemini-1.5-flash", "gemini-1.5-pro"],
            "OpenAI": ["gpt-4o-mini", "gpt-4o"],
            "Mistral": ["mistral-small-latest", "mistral-large-latest"],
            "Groq": ["llama-3.2-11b-vision-preview", "llama-3.2-90b-vision-preview"],
        }

        self.build_ui()
        threading.Thread(target=self._watcher_loop, daemon=True).start()

    # ── UI Construction ──────────────────────────────────────────────────
    def build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Header Bar ──────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0, height=42)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        header.grid_propagate(False)

        brand = ctk.CTkLabel(header, text="◆  NRA Metadata",
                             font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                             text_color=C["text"])
        brand.grid(row=0, column=0, padx=16, pady=8, sticky="w")

        self.header_status = ctk.CTkLabel(header, text="Ready",
                                          font=ctk.CTkFont(family="Segoe UI", size=11),
                                          text_color=C["text3"])
        self.header_status.grid(row=0, column=1, sticky="e", padx=16)

        # ── Sidebar ─────────────────────────────────────────────────────
        sidebar = ctk.CTkScrollableFrame(self, fg_color=C["surface"], corner_radius=0,
                                         width=250, scrollbar_button_color=C["surface2"],
                                         scrollbar_button_hover_color=C["border"])
        sidebar.grid(row=1, column=0, sticky="nsew", padx=(0, 0), pady=(1, 0))
        sidebar.grid_columnconfigure(0, weight=1)

        PAD = {"padx": 12, "pady": (0, 4)}
        LPAD = {"padx": 12, "pady": (0, 1)}

        # ── Section: AI Engine ──
        _section_header(sidebar, "AI Engine").pack(fill="x", **{**PAD, "pady": (12, 6)})

        _label(sidebar, "Provider").pack(fill="x", anchor="w", **LPAD)
        self.provider_cb = _combo(sidebar, ["Gemini", "OpenAI", "Mistral", "Groq"],
                                  command=self._on_provider_change)
        self.provider_cb.set(self.config.get("provider", "Gemini"))
        self.provider_cb.pack(fill="x", **PAD)

        _label(sidebar, "Model").pack(fill="x", anchor="w", **LPAD)
        provider = self.config.get("provider", "Gemini")
        self.model_cb = _combo(sidebar, self.MODEL_MAP.get(provider, []))
        saved_model = self.config.get("model", "")
        if saved_model and saved_model in self.MODEL_MAP.get(provider, []):
            self.model_cb.set(saved_model)
        elif self.MODEL_MAP.get(provider):
            self.model_cb.set(self.MODEL_MAP[provider][0])
        self.model_cb.pack(fill="x", **PAD)

        _label(sidebar, "API Key").pack(fill="x", anchor="w", **LPAD)
        self.api_key_entry = _entry(sidebar, show="*")
        self.api_key_entry.insert(0, self.config.get("api_key", ""))
        self.api_key_entry.pack(fill="x", **PAD)

        # Temperature
        temp_row = ctk.CTkFrame(sidebar, fg_color="transparent")
        temp_row.pack(fill="x", **LPAD)
        _label(temp_row, "Temperature").pack(side="left")
        self.temp_val = ctk.StringVar(value=f"{self.config.get('temperature', 0.3):.1f}")
        ctk.CTkLabel(temp_row, textvariable=self.temp_val,
                     font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=C["warn"]).pack(side="right")

        def update_temp_lbl(val):
            v = round(float(val), 1)
            tag = "Deterministic" if v <= 0.3 else "Creative" if v <= 0.7 else "Experimental"
            self.temp_val.set(f"{v:.1f} {tag}")
        self.temp_slider = _slider(sidebar, from_=0.0, to=1.0, number_of_steps=10,
                                   command=update_temp_lbl, progress_color=C["warn"])
        self.temp_slider.set(self.config.get("temperature", 0.3))
        self.temp_slider.pack(fill="x", **PAD)
        update_temp_lbl(self.config.get("temperature", 0.3))

        # ── Section: Keywords & Style ──
        _section_header(sidebar, "Keywords & Style").pack(fill="x", **{**PAD, "pady": (10, 6)})

        _label(sidebar, "Asset Style").pack(fill="x", anchor="w", **LPAD)
        self.style_cb = _combo(sidebar, ["General Commercial", "Icons & Clipart",
                                         "Backgrounds & Patterns", "Characters & Mascot"])
        self.style_cb.set(self.config.get("style_preset", "General Commercial"))
        self.style_cb.pack(fill="x", **PAD)

        kw_row = ctk.CTkFrame(sidebar, fg_color="transparent")
        kw_row.pack(fill="x", padx=12, pady=(0, 4))
        kw_row.grid_columnconfigure(0, weight=1)
        kw_row.grid_columnconfigure(1, weight=1)

        lf = ctk.CTkFrame(kw_row, fg_color="transparent")
        lf.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        _label(lf, "Min KW").pack(anchor="w")
        self.min_kw_entry = _entry(lf, width=60)
        self.min_kw_entry.insert(0, str(self.config.get("min_kw", 5)))
        self.min_kw_entry.pack(fill="x")

        rf = ctk.CTkFrame(kw_row, fg_color="transparent")
        rf.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        _label(rf, "Max KW").pack(anchor="w")
        self.max_kw_entry = _entry(rf, width=60)
        self.max_kw_entry.insert(0, str(self.config.get("max_kw", 20)))
        self.max_kw_entry.pack(fill="x")

        # ── Section: Processing ──
        _section_header(sidebar, "Processing").pack(fill="x", **{**PAD, "pady": (10, 6)})

        # Workers
        workers_row = ctk.CTkFrame(sidebar, fg_color="transparent")
        workers_row.pack(fill="x", **LPAD)
        _label(workers_row, "Workers").pack(side="left")
        self.workers_val = ctk.StringVar(value=str(self.config.get("workers", 2)))
        ctk.CTkLabel(workers_row, textvariable=self.workers_val,
                     font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                     text_color=C["accent"]).pack(side="right")

        def update_worker_lbl(val): self.workers_val.set(str(int(val)))
        self.workers_slider = _slider(sidebar, from_=1, to=8, number_of_steps=7,
                                      command=update_worker_lbl, progress_color=C["accent"])
        self.workers_slider.set(self.config.get("workers", 2))
        self.workers_slider.pack(fill="x", **PAD)

        # Format chips
        _label(sidebar, "Formats").pack(fill="x", anchor="w", **LPAD)
        fmt_saved = self.config.get("formats", {})
        self.fmt_vars = {}
        fmt_defs = [
            ("SVG", ".svg", True), ("EPS", ".eps", True), ("AI", ".ai", False),
            ("JPG", ".jpg", True), ("PNG", ".png", True),
            ("MP4", ".mp4", False), ("MOV", ".mov", False),
        ]
        fmt_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        fmt_frame.pack(fill="x", padx=12, pady=(0, 6))
        for i, (label, ext, default) in enumerate(fmt_defs):
            var = ctk.BooleanVar(value=fmt_saved.get(ext, default))
            self.fmt_vars[ext] = var
            ctk.CTkCheckBox(fmt_frame, text=label, variable=var, width=65, height=22,
                            checkbox_width=16, checkbox_height=16,
                            fg_color=C["accent"], hover_color=C["accent_h"],
                            border_color=C["border"],
                            font=ctk.CTkFont(family="Segoe UI", size=11)
                            ).grid(row=i // 4, column=i % 4, sticky="w", padx=1, pady=1)

        # Toggles
        toggle_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        toggle_frame.pack(fill="x", padx=12, pady=(0, 6))
        self.auto_watch = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(toggle_frame, text="Auto-Watch", variable=self.auto_watch,
                       progress_color=C["success"], button_color=C["text3"],
                       button_hover_color=C["text2"],
                       font=ctk.CTkFont(family="Segoe UI", size=11)).pack(anchor="w", pady=1)
        self.auto_zip = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(toggle_frame, text="Auto-Zip Vector", variable=self.auto_zip,
                       progress_color=C["success"], button_color=C["text3"],
                       button_hover_color=C["text2"],
                       font=ctk.CTkFont(family="Segoe UI", size=11)).pack(anchor="w", pady=1)

        # ── Section: Output & Export ──
        _section_header(sidebar, "Output & Export").pack(fill="x", **{**PAD, "pady": (10, 6)})

        _label(sidebar, "Author").pack(fill="x", anchor="w", **LPAD)
        self.author_entry = _entry(sidebar)
        self.author_entry.insert(0, self.config.get("author", ""))
        self.author_entry.pack(fill="x", **PAD)

        _label(sidebar, "Copyright").pack(fill="x", anchor="w", **LPAD)
        self.copyright_entry = _entry(sidebar)
        self.copyright_entry.insert(0, self.config.get("copyright", ""))
        self.copyright_entry.pack(fill="x", **PAD)

        # ── Action Buttons ──
        _divider(sidebar).pack(fill="x", padx=12, pady=(8, 8))

        self.start_btn = _btn(sidebar, "▶  Start Processing", C["accent"], C["accent_h"],
                              command=self.start_processing)
        self.start_btn.pack(fill="x", padx=12, pady=(0, 4))

        ctrl_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        ctrl_frame.pack(fill="x", padx=12, pady=(0, 4))

        self.pause_btn = _btn(ctrl_frame, "Pause", C["warn"], C["warn_h"],
                              command=self.toggle_pause, width=90)
        self.pause_btn.pack(side="left", padx=(0, 4), expand=True, fill="x")
        self.pause_btn.configure(state="disabled")

        self.cancel_btn = _btn(ctrl_frame, "Cancel", C["error"], C["error_h"],
                               command=self.cancel_batch, width=90)
        self.cancel_btn.pack(side="right", padx=(4, 0), expand=True, fill="x")
        self.cancel_btn.configure(state="disabled")

        self.retag_btn = _btn(sidebar, "Offline Re-Tag from CSV", C["surface2"], C["border"],
                              command=self.start_offline_retag)
        self.retag_btn.pack(fill="x", padx=12, pady=(4, 2))

        self.ftp_btn = _btn(sidebar, "FTP / SFTP Upload", C["violet"], C["violet_h"],
                            command=self.open_ftp_dialog)
        self.ftp_btn.pack(fill="x", padx=12, pady=(2, 16))

        # ═══════════════════════════════════════════════════════════════
        # ── Main Content Area ─────────────────────────────────────────
        # ═══════════════════════════════════════════════════════════════
        main = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        main.grid(row=1, column=1, sticky="nsew", padx=0, pady=(1, 0))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        # ── Folder Bar ──
        folder_bar = _frame(main)
        folder_bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 0))
        folder_bar.grid_columnconfigure(1, weight=1)

        _label(folder_bar, "Folder", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
               text_color=C["text"]).grid(row=0, column=0, padx=12, pady=10, sticky="w")
        _entry(folder_bar, self.input_dir).grid(row=0, column=1, padx=0, pady=10, sticky="ew")
        _btn(folder_bar, "Browse", C["surface2"], C["border"],
             command=self.browse_input, width=72, height=28,
             font=ctk.CTkFont(family="Segoe UI", size=11)).grid(row=0, column=2, padx=(8, 12), pady=10)

        # ── Stats & Progress Row ──
        stats_row = ctk.CTkFrame(main, fg_color="transparent")
        stats_row.grid(row=1, column=0, sticky="ew", padx=12, pady=(8, 0))
        stats_row.grid_columnconfigure(0, weight=1)
        stats_row.grid_columnconfigure(1, weight=1)

        self.stats_lbl = _label(stats_row, "Total: 0  ·  Success: 0  ·  Error: 0",
                                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                                text_color=C["text2"])
        self.stats_lbl.grid(row=0, column=0, sticky="w")

        self.cost_lbl = _label(stats_row, "Cost: $0.000  ·  Cache: 0",
                               font=ctk.CTkFont(family="Segoe UI", size=11),
                               text_color=C["success"])
        self.cost_lbl.grid(row=0, column=1, sticky="e")

        self.progress_bar = ctk.CTkProgressBar(stats_row, progress_color=C["accent"],
                                               fg_color=C["surface2"], height=4, corner_radius=2)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        # ── Content: Log (left) + Inspector (right) ──
        content = ctk.CTkFrame(main, fg_color="transparent")
        content.grid(row=2, column=0, sticky="nsew", padx=12, pady=(8, 12))
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)
        content.grid_rowconfigure(0, weight=1)

        # Console / Log
        log_frame = _frame(content, border_width=1, border_color=C["border_sub"])
        log_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        _label(log_frame, "Processing Log",
               font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
               text_color=C["text3"]).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 4))

        self.console = ctk.CTkTextbox(log_frame, fg_color=C["surface"], corner_radius=0,
                                      border_width=0,
                                      font=ctk.CTkFont(family="Consolas", size=11))
        self.console.grid(row=1, column=0, sticky="nsew", padx=0, pady=(0, 0))

        tb = self.console._textbox
        tb.tag_config("success",    foreground=C["success"])
        tb.tag_config("processing", foreground=C["warn"])
        tb.tag_config("error",      foreground=C["error"])
        tb.tag_config("info",       foreground=C["text2"])
        tb.tag_config("cache",      foreground=C["violet"])
        tb.tag_config("timestamp",  foreground=C["text3"])
        self.console.configure(state="disabled")

        # ── Inspector Panel ──
        inspector = _frame(content, border_width=1, border_color=C["border_sub"])
        inspector.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        _label(inspector, "Inspector",
               font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
               text_color=C["text3"]).pack(anchor="w", padx=12, pady=(8, 4))

        # Preview canvas
        preview_frame = ctk.CTkFrame(inspector, fg_color=C["surface2"], corner_radius=CR,
                                     height=180)
        preview_frame.pack(fill="x", padx=12, pady=(0, 6))
        preview_frame.pack_propagate(False)

        self.preview_lbl = ctk.CTkLabel(preview_frame, text="No Preview",
                                        width=180, height=170,
                                        fg_color="transparent", corner_radius=CR,
                                        font=ctk.CTkFont(family="Segoe UI", size=11),
                                        text_color=C["text3"])
        self.preview_lbl.pack(expand=True)

        self.status_badge = ctk.CTkLabel(preview_frame, text="", fg_color="transparent",
                                         corner_radius=4, padx=6,
                                         font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"))
        self.status_badge.place(relx=0.03, rely=0.05, anchor="nw")

        self.edit_frame = inspector  # reference for edit vars

        self.edit_title_var = ctk.StringVar()
        self.edit_desc_var = ctk.StringVar()
        self.edit_kws_var = ctk.StringVar()

        _label(inspector, "Title").pack(fill="x", padx=12, pady=(2, 0))
        _entry(inspector, text_var=self.edit_title_var, placeholder_text="Title").pack(fill="x", padx=12, pady=2)

        _label(inspector, "Description").pack(fill="x", padx=12, pady=(4, 0))
        _entry(inspector, text_var=self.edit_desc_var, placeholder_text="Description").pack(fill="x", padx=12, pady=2)

        self.kw_counter_lbl = _label(inspector, "Keywords (0 / 20)", text_color=C["success"])
        self.kw_counter_lbl.pack(fill="x", padx=12, pady=(4, 0))
        _entry(inspector, text_var=self.edit_kws_var,
               placeholder_text="Keywords (comma separated)").pack(fill="x", padx=12, pady=2)
        self.edit_kws_var.trace_add("write", lambda *_: self._update_kw_counter())

        btn_row = ctk.CTkFrame(inspector, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(4, 12))
        _btn(btn_row, "Dedup", C["surface2"], C["border"],
             height=28, width=80, command=self._dedup_keywords,
             font=ctk.CTkFont(family="Segoe UI", size=11)).pack(side="left", padx=(0, 4))
        _btn(btn_row, "Save & Embed", C["success"], C["success_h"],
             height=28, command=self.save_manual,
             font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")).pack(side="right", expand=True, fill="x")

    # ── Logging ──────────────────────────────────────────────────────────
    def log(self, message: str, level="info"):
        def _append():
            self.console.configure(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            tb = self.console._textbox
            tb.insert("end", f"[{ts}] ", "timestamp")
            tb.insert("end", f"[{level.upper()}] ", level)
            tb.insert("end", f"{message}\n", level)
            self.console.see("end")
            self.console.configure(state="disabled")
        self.after(0, _append)

    def update_stats(self, key):
        def _update():
            self.stats[key] += 1
            self.stats_lbl.configure(
                text=f"Total: {self.stats['total']}  ·  Success: {self.stats['success']}  ·  Error: {self.stats['error']}")
            self.cost_lbl.configure(
                text=f"Cost: ${tracker.estimated_cost_usd:.3f}  ·  Cache: {get_cache_hits()}")

            # Update header status
            if self.is_running:
                done = self.stats['success'] + self.stats['error']
                self.header_status.configure(
                    text=f"Processing {done}/{self.stats['total']}",
                    text_color=C["warn"])
            else:
                self.header_status.configure(text="Ready", text_color=C["text3"])
        self.after(0, _update)

    def update_preview(self, img, status_text: str, status_color: str, meta: dict, out_path: str, file_hash: str):
        def _draw():
            try:
                img.thumbnail((180, 180))
                self.current_preview_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                self.preview_lbl.configure(image=self.current_preview_img, text="")
                self.status_badge.configure(text=status_text, fg_color=status_color)

                self.edit_title_var.set(meta.get("title", ""))
                self.edit_desc_var.set(meta.get("description", ""))
                self.edit_kws_var.set(", ".join(meta.get("keywords", [])))

                self.current_edit_file = out_path
                self.current_edit_hash = file_hash
            except: pass
        self.after(0, _draw)

    def _on_provider_change(self, choice):
        models = self.MODEL_MAP.get(choice, [])
        self.model_cb.configure(values=models)
        if models:
            self.model_cb.set(models[0])

    def _get_copyright_text(self) -> str:
        cr = self.copyright_entry.get().strip()
        if cr:
            return cr
        author = self.author_entry.get().strip()
        if author:
            from datetime import datetime as dt
            return f"Copyright (c) {dt.now().year} {author}. All rights reserved."
        return ""

    def _update_kw_counter(self):
        raw = self.edit_kws_var.get()
        count = len([k for k in raw.split(",") if k.strip()])
        min_kw = int(self.min_kw_entry.get() or 5)
        max_kw = int(self.max_kw_entry.get() or 20)
        if min_kw <= count <= max_kw:
            color = C["success"]
        elif count < min_kw:
            color = C["warn"]
        else:
            color = C["error"]
        self.kw_counter_lbl.configure(text=f"Keywords ({count} / {max_kw})", text_color=color)

    def _dedup_keywords(self):
        raw = [k.strip() for k in self.edit_kws_var.get().split(",") if k.strip()]
        max_kw = int(self.max_kw_entry.get() or 50)
        cleaned = sanitize_keywords(raw, max_kw)
        self.edit_kws_var.set(", ".join(cleaned))

    def save_manual(self):
        if not self.current_edit_file or not os.path.exists(self.current_edit_file): return
        title = self.edit_title_var.get()
        desc = self.edit_desc_var.get()
        kws = [k.strip() for k in self.edit_kws_var.get().split(",") if k.strip()]

        name = os.path.basename(self.current_edit_file)
        if self.processor.embed_metadata(self.current_edit_file, title, desc, kws, self._get_copyright_text(), self.author_entry.get().strip()):
            meta = {"title": title, "description": desc, "keywords": kws}
            set_cached_metadata(self.current_edit_hash, meta)
            self.log(f"{name} (Manual save OK)", "success")

            sub_dir = os.path.dirname(self.current_edit_file)
            temp_master = os.path.join(sub_dir, "metadata_output.csv")
            import csv
            with open(temp_master, 'w', newline='', encoding='utf-8') as tf:
                tw = csv.writer(tf)
                tw.writerow(["Filename","Title","Description","Keywords"])
                tw.writerow([name, title, desc, ",".join(kws)])
            generate_microstock_csvs(sub_dir)
        else:
            self.log(f"{name} (Manual save fail)", "error")

    def browse_input(self):
        dir_path = ctk.filedialog.askdirectory()
        if dir_path: self.input_dir.set(dir_path)

    def open_ftp_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("FTP / SFTP Uploader")
        dialog.geometry("450x450")
        dialog.configure(fg_color=C["bg"])
        dialog.transient(self)
        dialog.grab_set()

        _label(dialog, "Preset").pack(padx=12, pady=(12, 2), anchor="w")
        preset_cb = _combo(dialog, ["Custom", "Adobe Stock", "Shutterstock", "Vecteezy", "Freepik"])
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
        ctk.CTkCheckBox(dialog, text="Upload .ZIP only", variable=zip_only,
                        fg_color=C["accent"], hover_color=C["accent_h"],
                        font=ctk.CTkFont(family="Segoe UI", size=12)).pack(padx=12, pady=10, anchor="w")

        status_lbl = ctk.CTkLabel(dialog, text="", text_color=C["success"],
                                  font=ctk.CTkFont(family="Segoe UI", size=11))
        status_lbl.pack(pady=5)

        def apply_preset(choice):
            hosts = {
                "Adobe Stock": "ftp.contributor.adobestock.com",
                "Shutterstock": "ftp.shutterstock.com",
                "Vecteezy": "ftp.vecteezy.com",
                "Freepik": "ftp.freepik.com"
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
                status_lbl.configure(text="No folder selected in main window", text_color=C["error"])
                return

            dialog.destroy()
            threading.Thread(target=self._run_ftp_upload, args=(h, p, u, pw, target_dir, zip_only.get()), daemon=True).start()

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=10, side="bottom")
        _btn(btn_frame, "Test Connection", C["surface2"], C["border"],
             command=test_conn).pack(side="left", expand=True, padx=(0, 4))
        _btn(btn_frame, "Start Upload", C["violet"], C["violet_h"],
             command=start_upload).pack(side="right", expand=True, padx=(4, 0))

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
                    files = [f for f in os.listdir(in_dir) if os.path.isfile(os.path.join(in_dir, f)) and self._is_allowed_file(f)]
                    if any(f not in self.processed_files for f in files):
                        self.after(0, lambda: self.start_processing(new_only=True))

    def toggle_pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_btn.configure(text="Resume", fg_color=C["success"], hover_color=C["success_h"])
            self.log("Batch PAUSED.", "info")
        else:
            self.pause_event.set()
            self.pause_btn.configure(text="Pause", fg_color=C["warn"], hover_color=C["warn_h"])
            self.log("Batch RESUMED.", "info")

    def cancel_batch(self):
        if self.is_running:
            self.cancel_flag = True
            self.pause_event.set()
            self.log("Canceling batch... finishing current active files.", "error")
            self.pause_btn.configure(state="disabled")
            self.cancel_btn.configure(state="disabled")

    def process_file(self, file_path, out_dir, ai, min_kw, max_kw, style_preset, csv_logger):
        self.pause_event.wait()
        if self.cancel_flag: return

        name = os.path.basename(file_path)
        self.log(f"{name}", "processing")

        preview = extract_preview_image(file_path, self.processor)
        if not preview:
            self.log(f"{name} (No preview)", "error")
            self.update_stats("error")
            return

        file_hash = get_file_hash(preview)
        cached = get_cached_metadata(file_hash)

        if cached:
            self.log(f"{name} [CACHE HIT]", "cache")
            meta = cached
            status, color = "CACHE", C["violet"]
        else:
            meta = ai.generate_metadata(preview, min_kw, max_kw, style_preset)
            set_cached_metadata(file_hash, meta)
            status, color = "API", C["warn"]

        try:
            img = Image.open(preview).copy()
        except:
            img = None

        try: os.remove(preview)
        except: pass

        meta = clean_metadata(meta, max_kw)

        out_path = os.path.join(out_dir, name)

        base_name = os.path.splitext(name)[0]
        sub_dir = os.path.join(out_dir, base_name)
        os.makedirs(sub_dir, exist_ok=True)

        final_path = os.path.join(sub_dir, name)
        shutil.move(file_path, final_path)

        title, desc, keywords = meta.get("title", ""), meta.get("description", ""), meta.get("keywords", [])

        if img:
            self.update_preview(img, status, color, meta, final_path, file_hash)

        if self.processor.embed_metadata(final_path, title, desc, keywords, self._get_copyright_text(), self.author_entry.get().strip()):
            self.log(f"{name} ({len(keywords)} kw)", "success")
            csv_logger.log(name, title, desc, keywords)
            generate_microstock_csvs(out_dir)
            temp_master = os.path.join(sub_dir, "metadata_output.csv")
            import csv
            with open(temp_master, 'w', newline='', encoding='utf-8') as tf:
                tw = csv.writer(tf)
                tw.writerow(["Filename","Title","Description","Keywords"])
                tw.writerow([name, title, desc, ",".join(keywords)])
            generate_microstock_csvs(sub_dir)

            if getattr(self, 'auto_zip', None) and self.auto_zip.get() and name.lower().endswith(('.svg', '.eps')):
                import zipfile
                jpg_path = os.path.join(sub_dir, base_name + ".jpg")
                if img:
                    try: img.convert("RGB").save(jpg_path, "JPEG", quality=95)
                    except: pass
                zip_path = os.path.join(sub_dir, base_name + ".zip")
                try:
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                        zf.write(final_path, arcname=name)
                        if os.path.exists(jpg_path): zf.write(jpg_path, arcname=base_name + ".jpg")
                except: pass

            self.update_stats("success")
        else:
            self.log(f"{name} (Embed failed)", "error")
            self.update_stats("error")

    def start_offline_retag(self):
        csv_path = ctk.filedialog.askopenfilename(
            title="Select metadata CSV",
            filetypes=[("CSV files", "*.csv")]
        )
        if not csv_path:
            return

        target_dir = self.input_dir.get()
        if not target_dir or not os.path.isdir(target_dir):
            self.log("Set Folder first.", "error")
            return

        self.retag_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        threading.Thread(target=self._run_offline_retag, args=(csv_path, target_dir), daemon=True).start()

    def _find_asset(self, target_dir: str, filename: str) -> str | None:
        for root, _dirs, files in os.walk(target_dir):
            if filename in files:
                return os.path.join(root, filename)
        return None

    def _run_offline_retag(self, csv_path: str, target_dir: str):
        import csv as csv_mod
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                rows = list(csv_mod.DictReader(f))
        except Exception as e:
            self.log(f"CSV read error: {e}", "error")
            self.after(0, lambda: self.retag_btn.configure(state="normal"))
            self.after(0, lambda: self.start_btn.configure(state="normal"))
            return

        if not rows:
            self.log("CSV empty.", "error")
            self.after(0, lambda: self.retag_btn.configure(state="normal"))
            self.after(0, lambda: self.start_btn.configure(state="normal"))
            return

        max_kw = int(self.max_kw_entry.get() or 50)
        total = len(rows)
        success = 0
        self.log(f"Offline Re-Tag: {total} rows from {os.path.basename(csv_path)}", "info")
        self.progress_bar.set(0)

        for i, row in enumerate(rows):
            filename = row.get("Filename", "").strip()
            if not filename:
                self.log(f"Row {i+1}: missing Filename", "error")
                continue

            asset_path = self._find_asset(target_dir, filename)
            if not asset_path:
                self.log(f"{filename} not found in folder", "error")
                continue

            title = row.get("Title", "").strip()
            desc = row.get("Description", "").strip()
            raw_kws = [k.strip() for k in row.get("Keywords", "").split(",") if k.strip()]
            keywords = sanitize_keywords(raw_kws, max_kw)

            if self.processor.embed_metadata(asset_path, title, desc, keywords, self._get_copyright_text(), self.author_entry.get().strip()):
                file_hash = get_file_hash(asset_path)
                set_cached_metadata(file_hash, {"title": title, "description": desc, "keywords": keywords})
                self.log(f"[OFFLINE SUCCESS] {filename}", "success")
                success += 1
            else:
                self.log(f"[OFFLINE FAIL] {filename}", "error")

            self.after(0, self.progress_bar.set, (i + 1) / total)

        self.log(f"Offline Re-Tag done: {success}/{total} succeeded", "info")
        self.after(0, lambda: self.retag_btn.configure(state="normal"))
        self.after(0, lambda: self.start_btn.configure(state="normal"))

    def start_processing(self, new_only=False):
        if self.is_running: return

        self.config.update({
            "provider": self.provider_cb.get(),
            "model": self.model_cb.get(),
            "temperature": round(float(self.temp_slider.get()), 1),
            "style_preset": self.style_cb.get(),
            "api_key": self.api_key_entry.get(),
            "min_kw": int(self.min_kw_entry.get() or 5),
            "max_kw": int(self.max_kw_entry.get() or 20),
            "workers": int(self.workers_slider.get()),
            "formats": {ext: var.get() for ext, var in self.fmt_vars.items()},
            "author": self.author_entry.get().strip(),
            "copyright": self.copyright_entry.get().strip()
        })
        save_config(self.config)

        in_dir = self.input_dir.get()
        out_dir = in_dir
        if not in_dir: return self.log("Path missing.", "error")

        files = [f for f in os.listdir(in_dir) if os.path.isfile(os.path.join(in_dir, f)) and self._is_allowed_file(f)]
        if new_only:
            files = [f for f in files if f not in self.processed_files]

        if not files: return self.log("No new files." if new_only else "No files.", "error")
        self.processed_files.update(files)

        self.is_running = True
        self.cancel_flag = False
        self.pause_event.set()
        self.pause_btn.configure(text="Pause", fg_color=C["warn"], hover_color=C["warn_h"], state="normal")
        self.cancel_btn.configure(state="normal")

        self.start_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self.stats = {"total": len(files), "success": 0, "error": 0}
        self.update_stats("total")
        self.stats["total"] = len(files)

        self.header_status.configure(text=f"Processing 0/{len(files)}", text_color=C["warn"])

        paths = [os.path.join(in_dir, f) for f in files]
        threading.Thread(target=self._run_batch, args=(paths, out_dir), daemon=True).start()

    def _run_batch(self, paths, out_dir):
        ai = AIService(self.config["provider"], self.config["api_key"], self.config.get("model"), self.config.get("temperature", 0.3))
        csv_logger = CSVLogger(os.path.join(out_dir, "metadata_output.csv"))

        with ThreadPoolExecutor(max_workers=self.config["workers"]) as executor:
            futures = [executor.submit(self.process_file, f, out_dir, ai, self.config["min_kw"], self.config["max_kw"], self.config["style_preset"], csv_logger) for f in paths]
            for i, f in enumerate(futures):
                f.result()
                if not self.cancel_flag:
                    self.after(0, self.progress_bar.set, (i + 1) / len(paths))

        if self.cancel_flag:
            self.log("Batch CANCELED.", "error")
        else:
            self.log("Batch complete. Generating exports...", "info")
            generate_microstock_csvs(out_dir)

        self.is_running = False
        self.after(0, lambda: self.start_btn.configure(state="normal"))
        self.after(0, lambda: self.pause_btn.configure(state="disabled"))
        self.after(0, lambda: self.cancel_btn.configure(state="disabled"))
        self.after(0, lambda: self.header_status.configure(text="Ready", text_color=C["text3"]))

if __name__ == "__main__":
    app = App()
    app.mainloop()
