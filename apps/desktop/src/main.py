import os
import shutil
import sys
import threading
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import customtkinter as ctk
from PIL import Image

from packages.ai_engine.service import AIService
from packages.media_processor.embedder import MediaProcessor
from packages.media_processor.previews import extract_preview_image
from packages.shared_utils.cache import (
    get_cache_hits,
    get_cached_metadata,
    get_file_hash,
    set_cached_metadata,
)
from packages.shared_utils.config import load_config, save_config
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

# ── Design System (Zinc + Indigo, inspired by Linear/Raycast) ────────────
C = {
    "bg": "#09090b",  # zinc-950 — app canvas
    "surface": "#18181b",  # zinc-900 — cards, sidebar
    "surface2": "#27272a",  # zinc-800 — inputs, secondary
    "border": "#3f3f46",  # zinc-700 — borders
    "border_sub": "#27272a",  # zinc-800 — subtle dividers
    "text": "#f4f4f5",  # zinc-100 — primary text
    "text2": "#a1a1aa",  # zinc-400 — secondary text
    "text3": "#71717a",  # zinc-500 — muted text
    "accent": "#6366f1",  # indigo-500 — primary accent
    "accent_h": "#4f46e5",  # indigo-600 — hover
    "success": "#10b981",  # emerald-500
    "success_h": "#059669",  # emerald-600
    "warn": "#f59e0b",  # amber-500
    "warn_h": "#d97706",  # amber-600
    "error": "#ef4444",  # red-500
    "error_h": "#dc2626",  # red-600
    "violet": "#8b5cf6",  # violet-500
    "violet_h": "#7c3aed",  # violet-600
}

FONT_BRAND = ("Segoe UI", 16, "bold")
FONT_SEC = ("Segoe UI", 11, "bold")  # section header
FONT_LBL = ("Segoe UI", 12)  # labels
FONT_SM = ("Segoe UI", 11)  # small text
FONT_XS = ("Segoe UI", 10)  # extra small
FONT_BTN = ("Segoe UI", 12, "bold")  # buttons
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
    f = ctk.CTkFrame(parent, fg_color=C["surface"])
    ctk.CTkLabel(
        f,
        text=text.upper(),
        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        text_color=C["text3"],
    ).pack(side="left")
    ctk.CTkFrame(f, height=1, fg_color=C["border_sub"]).pack(
        side="left", fill="x", expand=True, padx=(8, 0), pady=1
    )
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

        self.MODEL_MAP = {
            "Gemini": [
                "gemini-3.7-flash",
                "gemini-3.6-flash",
                "gemini-3.5-flash-lite",
                "gemini-3.1-pro-preview",
                "gemini-3.1-flash-lite-preview",
                "gemini-3-flash-preview",
                "gemini-2.5-pro",
                "gemini-2.5-flash",
                "gemini-2.5-flash-lite",
                "gemma-4-31b-it",
            ],
            "Groq": [
                "llama-3.3-70b-versatile",
                "meta-llama/llama-4-maverick-17b-128e-instruct",
                "qwen/qwen3-32b",
                "openai/gpt-oss-120b",
                "llama-3.2-11b-vision-preview",
            ],
            "Mistral": [
                "mistral-large-latest",
                "codestral-latest",
                "mistral-medium-latest",
                "mistral-small-latest",
                "pixtral-12b-2409",
            ],
            "OpenAI": ["gpt-4o-mini", "gpt-4o", "chatgpt-4o-latest"],
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

        # Run tool downloader in background
        threading.Thread(target=setup_tools, daemon=True).start()

        is_valid, msg = self.auth.validate_session()
        if not is_valid:
            self.show_login_modal()

    def show_login_modal(self):
        self.withdraw()

        modal = ctk.CTkToplevel(self)
        modal.title("NRA Metadata - Autentikasi")
        modal.geometry("480x640")
        modal.resizable(False, False)
        modal.configure(fg_color=C["bg"])
        modal.protocol("WM_DELETE_WINDOW", lambda: sys.exit(0))
        modal.attributes("-topmost", True)
        modal.update_idletasks()

        # Center Screen
        w, h = 480, 640
        sx = (modal.winfo_screenwidth() - w) // 2
        sy = (modal.winfo_screenheight() - h) // 2
        modal.geometry(f"{w}x{h}+{sx}+{sy}")

        # Fade in effect
        modal.attributes("-alpha", 0.0)

        def fade_in(alpha=0.0):
            if alpha < 1.0:
                alpha += 0.05
                modal.attributes("-alpha", alpha)
                modal.after(15, lambda: fade_in(alpha))

        fade_in()

        # Header
        header_frame = ctk.CTkFrame(modal, fg_color="transparent")
        header_frame.pack(fill="x", pady=(24, 12))

        ctk.CTkLabel(
            header_frame,
            text="NRA METADATA",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=C["text"],
        ).pack()
        ctk.CTkLabel(
            header_frame,
            text="v0.1.0-alpha - AI Auto Tagger",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C["text3"],
        ).pack()

        # Tabs
        tabview = ctk.CTkTabview(
            modal,
            fg_color=C["surface"],
            segmented_button_fg_color=C["surface"],
            segmented_button_selected_color=C["accent"],
            segmented_button_selected_hover_color=C["accent_h"],
        )
        tabview.pack(padx=24, pady=(0, 16), fill="both", expand=True)

        tab_login = tabview.add(" Masuk ")
        tab_register = tabview.add(" Buat Akun ")

        # â”€â”€ helper: labelled entry row â”€â”€
        FW = 360  # field width

        def _field(parent, label, var, show="", icon="", **kw):
            lbl_text = f"{icon} {label}" if icon else label
            ctk.CTkLabel(
                parent,
                text=lbl_text,
                text_color=C["text"],
                font=ctk.CTkFont(family="Segoe UI", size=12),
            ).pack(anchor="w", padx=20, pady=(6, 2))
            e = ctk.CTkEntry(
                parent,
                textvariable=var,
                width=FW,
                show=show,
                fg_color=C["surface2"],
                border_color=C["border"],
                corner_radius=8,
                text_color=C["text"],
                font=ctk.CTkFont(family="Segoe UI", size=12),
                **kw,
            )
            e.pack(padx=20, pady=(0, 4))
            return e

        # â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â•  LOGIN TAB â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â•
        login_scroll = ctk.CTkScrollableFrame(
            tab_login, fg_color="transparent", scrollbar_button_color=C["surface2"]
        )
        login_scroll.pack(fill="both", expand=True, padx=0, pady=0)

        # Remember account logic
        last_auth_user = self.config.get("last_auth_user", self.auth.username)
        user_var_login = ctk.StringVar(value=last_auth_user)
        pass_var_login = ctk.StringVar()
        show_pass_login = ctk.BooleanVar(value=False)

        if last_auth_user:
            welcome_frame = ctk.CTkFrame(
                login_scroll, fg_color=C["surface2"], corner_radius=8
            )
            welcome_frame.pack(fill="x", padx=20, pady=(0, 10))
            ctk.CTkLabel(
                welcome_frame,
                text=f"\U0001f44b Selamat datang kembali,\n{last_auth_user}",
                text_color=C["text"],
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                justify="left",
            ).pack(side="left", padx=12, pady=8)

            def clear_user():
                user_var_login.set("")
                self.config["last_auth_user"] = ""
                from packages.shared_utils.config import save_config

                save_config(self.config)
                welcome_frame.pack_forget()
                user_entry.focus()

            ctk.CTkButton(
                welcome_frame,
                text="Ganti Akun",
                width=60,
                height=24,
                fg_color="transparent",
                text_color=C["accent"],
                hover_color=C["surface"],
                command=clear_user,
            ).pack(side="right", padx=12)

        user_entry = _field(
            login_scroll, "Username atau Email", user_var_login, icon="\U0001f464"
        )

        # password + toggle
        ctk.CTkLabel(
            login_scroll,
            text="\U0001f512 Password",
            text_color=C["text"],
            font=ctk.CTkFont(family="Segoe UI", size=12),
        ).pack(anchor="w", padx=20, pady=(6, 2))
        pw_frame_l = ctk.CTkFrame(login_scroll, fg_color="transparent")
        pw_frame_l.pack(padx=20, pady=(0, 4), fill="x")
        pass_entry_login = ctk.CTkEntry(
            pw_frame_l,
            textvariable=pass_var_login,
            show="*",
            width=FW - 40,
            fg_color=C["surface2"],
            border_color=C["border"],
            corner_radius=8,
            text_color=C["text"],
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        pass_entry_login.pack(side="left")

        def _toggle_pw_login():
            pass_entry_login.configure(show="" if show_pass_login.get() else "*")
            show_pass_login.set(not show_pass_login.get())

        ctk.CTkButton(
            pw_frame_l,
            text="\U0001f441",
            width=36,
            height=28,
            corner_radius=8,
            fg_color=C["surface2"],
            hover_color=C["border"],
            command=_toggle_pw_login,
        ).pack(side="left", padx=(4, 0))

        if last_auth_user:
            pass_entry_login.focus()

        remember_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            login_scroll,
            text="Ingat Saya",
            variable=remember_var,
            fg_color=C["accent"],
            hover_color=C["accent_h"],
            text_color=C["text2"],
            corner_radius=4,
            font=ctk.CTkFont(family="Segoe UI", size=11),
        ).pack(anchor="w", padx=20, pady=(8, 4))

        status_lbl_login = ctk.CTkLabel(
            login_scroll,
            text="",
            text_color=C["error"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
        )
        status_lbl_login.pack(pady=(2, 4))

        btn_login = ctk.CTkButton(
            login_scroll,
            text="\U0001f680 Masuk ke Aplikasi",
            width=FW,
            fg_color=C["accent"],
            hover_color=C["accent_h"],
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=38,
            corner_radius=8,
        )

        def _do_login():
            u = user_var_login.get().strip()
            p = pass_var_login.get().strip()
            if not u or not p:
                status_lbl_login.configure(
                    text="\u26a0\ufe0f Isi username/email dan password",
                    text_color=C["error"],
                )
                return
            status_lbl_login.configure(
                text="\u231b Memverifikasi kredensial...", text_color=C["text3"]
            )
            btn_login.configure(state="disabled", text="Memproses...")
            modal.update()

            def _bg():
                res = self.auth.login(u, p)
                modal.after(0, lambda: _login_done(res, u))

            import threading

            threading.Thread(target=_bg, daemon=True).start()

        def _login_done(res, u):
            btn_login.configure(state="normal", text="\U0001f680 Masuk ke Aplikasi")
            if res.get("status") == "SUCCESS":
                actual_user = res.get("username", u)
                if remember_var.get():
                    self.config["last_auth_user"] = actual_user
                    from packages.shared_utils.config import save_config

                    save_config(self.config)
                else:
                    self.auth.config["auth_user"] = ""
                    self.config["last_auth_user"] = ""
                    from packages.shared_utils.config import save_config

                    save_config(self.config)
                    save_config(self.auth.config)

                status_lbl_login.configure(
                    text="\u2705 Login berhasil!", text_color=C["success"]
                )
                modal.update()

                # Smooth fade out
                def fade_out(alpha=1.0):
                    if alpha > 0.0:
                        alpha -= 0.1
                        modal.attributes("-alpha", alpha)
                        modal.after(15, lambda: fade_out(alpha))
                    else:
                        modal.destroy()
                        self.deiconify()

                fade_out()

                self.after(
                    500,
                    lambda: self.log(f"Login sukses sebagai {actual_user}", "success"),
                )
            else:
                status_lbl_login.configure(
                    text=f"\u274c {res.get('message', 'Error login')}",
                    text_color=C["error"],
                )

        btn_login.configure(command=_do_login)
        btn_login.pack(padx=20, pady=(8, 12))

        # â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â•  REGISTER TAB â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â• â•
        reg_scroll = ctk.CTkScrollableFrame(
            tab_register, fg_color="transparent", scrollbar_button_color=C["surface2"]
        )
        reg_scroll.pack(fill="both", expand=True, padx=0, pady=0)

        fullname_var = ctk.StringVar()
        user_var_reg = ctk.StringVar()
        email_var_reg = ctk.StringVar()
        wa_var_reg = ctk.StringVar()
        pass_var_reg = ctk.StringVar()
        pass2_var_reg = ctk.StringVar()
        show_pass_reg = ctk.BooleanVar(value=False)

        _field(reg_scroll, "Nama Lengkap", fullname_var, icon="\U0001f4b3")
        _field(reg_scroll, "Username", user_var_reg, icon="\U0001f464")
        _field(reg_scroll, "Email Aktif", email_var_reg, icon="\u2709\ufe0f")

        # WA Banner
        wa_banner = ctk.CTkFrame(reg_scroll, fg_color=C["surface2"], corner_radius=6)
        wa_banner.pack(fill="x", padx=20, pady=(8, 0))
        ctk.CTkLabel(
            wa_banner,
            text="\U0001f4a1 Info: Untuk undangan grup update & rilis fitur.",
            text_color=C["text3"],
            font=ctk.CTkFont(family="Segoe UI", size=10, slant="italic"),
        ).pack(pady=4)
        _field(reg_scroll, "No. WhatsApp", wa_var_reg, icon="\U0001f4f1")

        # password + toggle
        ctk.CTkLabel(
            reg_scroll,
            text="\U0001f512 Password",
            text_color=C["text"],
            font=ctk.CTkFont(family="Segoe UI", size=12),
        ).pack(anchor="w", padx=20, pady=(6, 2))
        pw_frame_r = ctk.CTkFrame(reg_scroll, fg_color="transparent")
        pw_frame_r.pack(padx=20, pady=(0, 4), fill="x")
        pass_entry_reg = ctk.CTkEntry(
            pw_frame_r,
            textvariable=pass_var_reg,
            show="*",
            width=FW - 40,
            fg_color=C["surface2"],
            border_color=C["border"],
            corner_radius=8,
            text_color=C["text"],
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        pass_entry_reg.pack(side="left")

        def _toggle_pw_reg():
            ch = "" if show_pass_reg.get() else "*"
            pass_entry_reg.configure(show=ch)
            show_pass_reg.set(not show_pass_reg.get())

        ctk.CTkButton(
            pw_frame_r,
            text="\U0001f441",
            width=36,
            height=28,
            corner_radius=8,
            fg_color=C["surface2"],
            hover_color=C["border"],
            command=_toggle_pw_reg,
        ).pack(side="left", padx=(4, 0))

        _field(reg_scroll, "\U0001f512 Konfirmasi Password", pass2_var_reg, show="*")

        status_lbl_reg = ctk.CTkLabel(
            reg_scroll,
            text="",
            text_color=C["error"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
            wraplength=FW - 10,
        )
        status_lbl_reg.pack(pady=(2, 4))

        btn_reg = ctk.CTkButton(
            reg_scroll,
            text="\u2728 Buat Akun & Gabung Komunitas",
            width=FW,
            fg_color=C["accent"],
            hover_color=C["accent_h"],
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=38,
            corner_radius=8,
        )

        def _validate_register():
            fn = fullname_var.get().strip()
            u = user_var_reg.get().strip()
            em = email_var_reg.get().strip()
            wa = wa_var_reg.get().strip()
            pw = pass_var_reg.get().strip()
            pw2 = pass2_var_reg.get().strip()
            if not fn or not u or not em or not wa or not pw:
                return None, "Isi semua data"
            if "@" not in em or "." not in em.split("@")[-1]:
                return None, "Format email tidak valid"
            wa_clean = wa.replace("+", "").replace("-", "").replace(" ", "")
            if not wa_clean.isdigit() or len(wa_clean) < 10:
                return None, "Nomor WA minimal 10 digit angka"
            if wa_clean.startswith("08"):
                wa_clean = "62" + wa_clean[1:]
            elif not wa_clean.startswith("62"):
                wa_clean = "62" + wa_clean
            if pw != pw2:
                return None, "Password dan konfirmasi tidak cocok"
            return {
                "fullname": fn,
                "username": u,
                "email": em,
                "wa": wa_clean,
                "password": pw,
            }, ""

        def _do_register():
            data, err = _validate_register()
            if err or data is None:
                status_lbl_reg.configure(
                    text=f"\u26a0\ufe0f {err}", text_color=C["error"]
                )
                return
            status_lbl_reg.configure(
                text="\u231b Mendaftarkan perangkat...", text_color=C["text3"]
            )
            btn_reg.configure(state="disabled", text="Memproses...")
            modal.update()

            def _bg():
                res = self.auth.register(
                    data["username"],
                    data["password"],
                    email=data["email"],
                    wa=data["wa"],
                    fullname=data["fullname"],
                )
                modal.after(0, lambda: _reg_done(res, data["username"]))

            import threading

            threading.Thread(target=_bg, daemon=True).start()

        def _reg_done(res, u):
            btn_reg.configure(
                state="normal", text="\u2728 Buat Akun & Gabung Komunitas"
            )
            if res.get("status") == "SUCCESS":
                status_lbl_reg.configure(
                    text="\u2705 Registrasi sukses! Silakan login.",
                    text_color=C["success"],
                )
                user_var_login.set(u)
                tabview.set(" Masuk ")
            else:
                status_lbl_reg.configure(
                    text=f"\u274c {res.get('message', 'Error registrasi')}",
                    text_color=C["error"],
                )

        btn_reg.configure(command=_do_register)
        btn_reg.pack(padx=20, pady=(8, 12))

        modal.grab_set()
        # Defer sash restore until window is rendered
        self.after(100, self._restore_sash_positions)
        import threading

        threading.Thread(target=self._watcher_loop, daemon=True).start()

        self.bind("<Control-z>", lambda e: self.undo_metadata())
        self.bind("<Control-y>", lambda e: self.redo_metadata())

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

    # ── UI Construction ──────────────────────────────────────────────────
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
        sidebar_container = ctk.CTkFrame(
            self.outer_paned, fg_color=C["surface"], corner_radius=0
        )
        sidebar = ctk.CTkScrollableFrame(
            sidebar_container,
            fg_color=C["surface"],
            corner_radius=0,
            scrollbar_button_color=C["surface2"],
            scrollbar_button_hover_color=C["border"],
        )
        sidebar.pack(fill="both", expand=True)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar._parent_canvas.configure(bg=C["surface"], highlightthickness=0)
        self.outer_paned.add(
            sidebar_container, minsize=220, width=self.config.get("sidebar_width", 260)
        )

        PAD = {"padx": 12, "pady": (0, 4)}
        LPAD = {"padx": 12, "pady": (0, 1)}

        # ── Section: Presets ──
        _section_header(sidebar, "Profiles").pack(fill="x", **{**PAD, "pady": (12, 6)})

        preset_row = ctk.CTkFrame(sidebar, fg_color=C["surface"])
        preset_row.pack(fill="x", **LPAD)
        self.preset_var = ctk.StringVar(
            value=self.config.get("active_profile", "Default")
        )
        self.preset_cb = _combo(
            preset_row,
            [
                "Default",
                "Adobe Stock Vector",
                "Shutterstock Photo",
                "Vecteezy Icon/Clipart",
            ],
            command=self._on_preset_change,
            variable=self.preset_var,
        )
        self.preset_cb.pack(side="left", expand=True, fill="x", padx=(0, 4))

        _btn(
            preset_row,
            "Save",
            C["surface2"],
            C["border"],
            width=40,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=self._save_preset,
        ).pack(side="left", padx=1)
        _btn(
            preset_row,
            "Del",
            C["error"],
            C["error_h"],
            width=30,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=self._delete_preset,
        ).pack(side="left", padx=(1, 0))

        self._load_custom_presets()

        # ── Section: AI Engine ──
        _section_header(sidebar, "AI Engine").pack(fill="x", **{**PAD, "pady": (12, 6)})

        _label(sidebar, "Provider").pack(fill="x", anchor="w", **LPAD)
        self.provider_cb = _combo(
            sidebar,
            ["Gemini", "OpenAI", "Mistral", "Groq"],
            command=self._on_provider_change,
        )

        provider = self.config.get("provider", "Gemini")
        if provider not in ["Gemini", "OpenAI", "Mistral", "Groq"]:
            provider = "Gemini"

        self.provider_cb.set(provider)
        self.provider_cb.pack(fill="x", **PAD)

        _label(sidebar, "Model").pack(fill="x", anchor="w", **LPAD)
        # Initialize with the clean values for this provider to avoid CTkComboBox placeholder text
        model_list = self.MODEL_MAP.get(provider, [])
        self.model_cb = _combo(
            sidebar, model_list, command=lambda _: self._save_current_config()
        )
        saved_model = self.config.get("model", "")

        if saved_model and saved_model in model_list:
            self.model_cb.set(saved_model)
        elif model_list:
            self.model_cb.set(model_list[0])
            self.config["model"] = model_list[0]

        self.model_cb.pack(fill="x", **PAD)

        _label(sidebar, "API Key").pack(fill="x", anchor="w", **LPAD)
        self.api_key_entry = _entry(sidebar, show="*")
        self.keys_counter_lbl = _label(sidebar, "(0 keys loaded)")
        self.keys_counter_lbl.pack(fill="x", anchor="w", padx=16, pady=2)

        # Load API keys dict, handle migration from old single API key
        if "api_keys" not in self.config:
            self.config["api_keys"] = {}
            if "api_key" in self.config:
                old_key = self.config.pop("api_key")
                old_provider = self.config.get("provider", "Gemini")
                if old_key:
                    self.config["api_keys"][old_provider] = old_key

        current_provider = self.config.get("provider", "Gemini")
        self.api_key_entry.insert(0, self.config["api_keys"].get(current_provider, ""))
        self.api_key_entry.pack(fill="x", **PAD)

        def _on_key_type(event=None):
            active_prov = self.provider_cb.get()
            if "api_keys" not in self.config:
                self.config["api_keys"] = {}
            self.config["api_keys"][active_prov] = self.api_key_entry.get().strip()
            self._save_current_config()

        self.api_key_entry.bind("<KeyRelease>", _on_key_type)
        self.api_key_entry.bind("<FocusOut>", _on_key_type)

        # Fetch Models Button
        self.fetch_models_btn = ctk.CTkButton(
            sidebar,
            text="🔄 Fetch Models",
            fg_color=C["surface2"],
            hover_color=C["border"],
            text_color=C["text2"],
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._fetch_models,
        )
        self.fetch_models_btn.pack(fill="x", padx=16, pady=(0, 16))

        # Temperature
        temp_row = ctk.CTkFrame(sidebar, fg_color=C["surface"])
        temp_row.pack(fill="x", **LPAD)
        _label(temp_row, "Temperature").pack(side="left")
        self.temp_val = ctk.StringVar(
            value=f"{self.config.get('temperature', 0.3):.1f}"
        )
        ctk.CTkLabel(
            temp_row,
            textvariable=self.temp_val,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C["warn"],
        ).pack(side="right")

        def update_temp_lbl(val):
            v = round(float(val), 1)
            tag = (
                "Deterministic"
                if v <= 0.3
                else "Creative"
                if v <= 0.7
                else "Experimental"
            )
            self.temp_val.set(f"{v:.1f} {tag}")

        self.temp_slider = _slider(
            sidebar,
            from_=0.0,
            to=1.0,
            number_of_steps=10,
            command=update_temp_lbl,
            progress_color=C["warn"],
        )
        self.temp_slider.set(self.config.get("temperature", 0.3))
        self.temp_slider.pack(fill="x", **PAD)
        self.temp_slider.bind(
            "<ButtonRelease-1>", lambda e: self._save_current_config()
        )
        update_temp_lbl(self.config.get("temperature", 0.3))

        # ── Section: Keywords & Style ──
        _section_header(sidebar, "Keywords & Style").pack(
            fill="x", **{**PAD, "pady": (10, 6)}
        )

        _label(sidebar, "Asset Style").pack(fill="x", anchor="w", **LPAD)
        self.style_cb = _combo(
            sidebar,
            [
                "General Commercial",
                "Icons & Clipart",
                "Backgrounds & Patterns",
                "Characters & Mascot",
                "Photo Realistic",
                "Vector Clipart",
            ],
            command=lambda _: self._save_current_config(),
        )
        self.style_cb.set(self.config.get("style_preset", "General Commercial"))
        self.style_cb.pack(fill="x", **PAD)

        kw_row = ctk.CTkFrame(sidebar, fg_color=C["surface"])
        kw_row.pack(fill="x", padx=12, pady=(0, 4))
        kw_row.grid_columnconfigure(0, weight=1)
        kw_row.grid_columnconfigure(1, weight=1)

        lf = ctk.CTkFrame(kw_row, fg_color=C["surface"])
        lf.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        _label(lf, "Min KW").pack(anchor="w")
        self.min_kw_entry = _entry(lf, width=60)
        self.min_kw_entry.insert(0, str(self.config.get("min_kw", 10)))
        self.min_kw_entry.pack(fill="x")
        self.min_kw_entry.bind("<FocusOut>", lambda e: self._save_current_config())

        rf = ctk.CTkFrame(kw_row, fg_color=C["surface"])
        rf.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        _label(rf, "Max KW").pack(anchor="w")
        self.max_kw_entry = _entry(rf, width=60)
        self.max_kw_entry.insert(0, str(self.config.get("max_kw", 49)))
        self.max_kw_entry.pack(fill="x")
        self.max_kw_entry.bind("<FocusOut>", lambda e: self._save_current_config())

        _label(sidebar, "Mandatory Keywords").pack(fill="x", anchor="w", **LPAD)
        self.custom_kw_entry = _entry(sidebar, placeholder_text="e.g. 3d, isolated")
        self.custom_kw_entry.insert(0, self.config.get("custom_kw", ""))
        self.custom_kw_entry.pack(fill="x", **PAD)
        self.custom_kw_entry.bind("<FocusOut>", lambda e: self._save_current_config())

        _label(sidebar, "Extra AI Context / Focus").pack(fill="x", anchor="w", **LPAD)
        self.extra_prompt_entry = _entry(
            sidebar, placeholder_text="e.g. Isolated on white background"
        )
        self.extra_prompt_entry.insert(0, self.config.get("extra_prompt", ""))
        self.extra_prompt_entry.pack(fill="x", **PAD)
        self.extra_prompt_entry.bind(
            "<FocusOut>", lambda e: self._save_current_config()
        )

        inj_row = ctk.CTkFrame(sidebar, fg_color=C["surface"])
        inj_row.pack(fill="x", **LPAD)
        _label(inj_row, "Inject at:").pack(side="left", padx=(0, 4))
        self.custom_kw_pos = _combo(
            inj_row,
            ["Start (Priority)", "End"],
            command=lambda _: self._save_current_config(),
        )
        self.custom_kw_pos.set(self.config.get("custom_kw_pos", "Start (Priority)"))
        self.custom_kw_pos.pack(side="left", expand=True, fill="x")

        # ── Section: Processing ──
        _section_header(sidebar, "Processing").pack(
            fill="x", **{**PAD, "pady": (10, 6)}
        )

        # Workers
        workers_row = ctk.CTkFrame(sidebar, fg_color=C["surface"])
        workers_row.pack(fill="x", **LPAD)
        _label(workers_row, "Workers").pack(side="left")
        self.workers_val = ctk.StringVar(value=str(self.config.get("workers", 2)))
        ctk.CTkLabel(
            workers_row,
            textvariable=self.workers_val,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=C["accent"],
        ).pack(side="right")

        def update_worker_lbl(val):
            self.workers_val.set(str(int(val)))

        self.workers_slider = _slider(
            sidebar,
            from_=1,
            to=8,
            number_of_steps=7,
            command=update_worker_lbl,
            progress_color=C["accent"],
        )
        self.workers_slider.set(self.config.get("workers", 2))
        self.workers_slider.pack(fill="x", **PAD)
        self.workers_slider.bind(
            "<ButtonRelease-1>", lambda e: self._save_current_config()
        )

        # Format chips
        _label(sidebar, "Formats").pack(fill="x", anchor="w", **LPAD)
        fmt_saved = self.config.get("formats", {})
        self.fmt_vars = {}
        fmt_defs = [
            ("SVG", ".svg", True),
            ("EPS", ".eps", True),
            ("AI", ".ai", False),
            ("JPG", ".jpg", True),
            ("PNG", ".png", True),
            ("MP4", ".mp4", False),
            ("MOV", ".mov", False),
        ]
        fmt_frame = ctk.CTkFrame(sidebar, fg_color=C["surface"])
        fmt_frame.pack(fill="x", padx=12, pady=(0, 6))
        for i, (label, ext, default) in enumerate(fmt_defs):
            var = ctk.BooleanVar(value=fmt_saved.get(ext, default))
            self.fmt_vars[ext] = var
            ctk.CTkCheckBox(
                fmt_frame,
                text=label,
                variable=var,
                width=65,
                height=22,
                checkbox_width=16,
                checkbox_height=16,
                fg_color=C["accent"],
                hover_color=C["accent_h"],
                border_color=C["border"],
                font=ctk.CTkFont(family="Segoe UI", size=11),
            ).grid(row=i // 4, column=i % 4, sticky="w", padx=1, pady=1)

        # Toggles
        toggle_frame = ctk.CTkFrame(sidebar, fg_color=C["surface"])
        toggle_frame.pack(fill="x", padx=12, pady=(0, 6))
        self.auto_watch = ctk.BooleanVar(value=self.config.get("auto_watch", False))
        ctk.CTkSwitch(
            toggle_frame,
            text="Auto-Watch",
            variable=self.auto_watch,
            progress_color=C["success"],
            button_color=C["text3"],
            button_hover_color=C["text2"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
        ).pack(anchor="w", pady=1)
        self.auto_zip = ctk.BooleanVar(value=self.config.get("auto_zip_vector", False))
        ctk.CTkSwitch(
            toggle_frame,
            text="Auto-Zip Vector",
            variable=self.auto_zip,
            progress_color=C["success"],
            button_color=C["text3"],
            button_hover_color=C["text2"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
        ).pack(anchor="w", pady=1)

        # ── Section: Output & Export ──
        _section_header(sidebar, "Output & Export").pack(
            fill="x", **{**PAD, "pady": (10, 6)}
        )

        _label(sidebar, "Author").pack(fill="x", anchor="w", **LPAD)
        self.author_entry = _entry(sidebar)
        self.author_entry.insert(0, self.config.get("author", ""))
        self.author_entry.pack(fill="x", **PAD)
        self.author_entry.bind("<FocusOut>", lambda e: self._save_current_config())

        _label(sidebar, "Copyright").pack(fill="x", anchor="w", **LPAD)
        self.copyright_entry = _entry(sidebar)
        self.copyright_entry.insert(0, self.config.get("copyright", ""))
        self.copyright_entry.pack(fill="x", **PAD)
        self.copyright_entry.bind("<FocusOut>", lambda e: self._save_current_config())

        _label(sidebar, "Generate CSVs").pack(fill="x", anchor="w", **LPAD)
        csv_frame = ctk.CTkFrame(sidebar, fg_color=C["surface"])
        csv_frame.pack(fill="x", padx=12, pady=(0, 6))

        self.csv_vars = {}
        csv_defs = ["Generic", "Adobe Stock", "Shutterstock", "Vecteezy", "Freepik"]
        saved_csvs = self.config.get(
            "csv_platforms", ["Generic", "Adobe Stock", "Shutterstock"]
        )
        for i, plat in enumerate(csv_defs):
            var = ctk.BooleanVar(value=(plat in saved_csvs))
            self.csv_vars[plat] = var
            ctk.CTkCheckBox(
                csv_frame,
                text=plat,
                variable=var,
                fg_color=C["accent"],
                hover_color=C["accent_h"],
                font=ctk.CTkFont(family="Segoe UI", size=11),
            ).grid(row=i, column=0, sticky="w", pady=2)

        # ── Action Buttons ──
        _divider(sidebar).pack(fill="x", padx=12, pady=(8, 8))

        self.start_btn = _btn(
            sidebar,
            "▶  Start Processing",
            C["accent"],
            C["accent_h"],
            command=self.start_processing,
        )
        self.start_btn.pack(fill="x", padx=12, pady=(0, 4))

        ctrl_frame = ctk.CTkFrame(sidebar, fg_color=C["surface"])
        ctrl_frame.pack(fill="x", padx=12, pady=(0, 4))

        self.pause_btn = _btn(
            ctrl_frame,
            "Pause",
            C["warn"],
            C["warn_h"],
            command=self.toggle_pause,
            width=90,
        )
        self.pause_btn.pack(side="left", padx=(0, 4), expand=True, fill="x")
        self.pause_btn.configure(state="disabled")

        self.cancel_btn = _btn(
            ctrl_frame,
            "Cancel",
            C["error"],
            C["error_h"],
            command=self.cancel_batch,
            width=90,
        )
        self.cancel_btn.pack(side="right", padx=(4, 0), expand=True, fill="x")
        self.cancel_btn.configure(state="disabled")

        self.retag_btn = _btn(
            sidebar,
            "Import Metadata from CSV...",
            C["surface2"],
            C["border"],
            command=self.start_offline_retag,
        )
        self.retag_btn.pack(fill="x", padx=12, pady=(4, 2))

        self.ftp_btn = _btn(
            sidebar,
            "FTP / SFTP Upload",
            C["violet"],
            C["violet_h"],
            command=self.open_ftp_dialog,
        )
        self.ftp_btn.pack(fill="x", padx=12, pady=(2, 6))

        self.blacklist_btn = _btn(
            sidebar,
            "Manage Blacklist",
            C["surface2"],
            C["border"],
            command=self.open_blacklist_manager,
        )
        self.blacklist_btn.pack(fill="x", padx=12, pady=(2, 16))

        # ═══════════════════════════════════════════════════════════════
        # ── Main Content Area ─────────────────────────────────────────
        # ═══════════════════════════════════════════════════════════════
        main = ctk.CTkFrame(self.outer_paned, fg_color=C["bg"], corner_radius=0)
        self.outer_paned.add(main, minsize=500)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(4, weight=1)

        # ── Folder Bar ──
        # ── Update Banner ──
        self.update_banner = ctk.CTkLabel(
            main, text="", text_color=C["text3"], fg_color=C["bg"], height=0
        )
        self.update_banner.grid(row=0, column=0, sticky="ew", padx=15, pady=(0, 0))

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
        queue_outer = _frame(main, border_width=1, border_color=C["border_sub"])
        queue_outer.grid(row=2, column=0, sticky="ew", padx=12, pady=(6, 0))
        queue_outer.grid_columnconfigure(0, weight=1)

        queue_header = ctk.CTkFrame(queue_outer, fg_color=C["surface"])
        queue_header.pack(fill="x", padx=8, pady=(6, 2))
        _label(
            queue_header,
            "FILE QUEUE",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=C["text3"],
        ).pack(side="left")
        self.queue_count_lbl = _label(
            queue_header,
            "0 files",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=C["text3"],
        )
        self.queue_count_lbl.pack(side="left", padx=(8, 0))

        _btn(
            queue_header,
            "Exclude All",
            C["surface2"],
            C["border"],
            height=22,
            width=75,
            font=ctk.CTkFont(size=9),
            command=lambda: self._toggle_all_exclusions(True),
        ).pack(side="right", padx=(2, 0))
        _btn(
            queue_header,
            "Include All",
            C["surface2"],
            C["border"],
            height=22,
            width=75,
            font=ctk.CTkFont(size=9),
            command=lambda: self._toggle_all_exclusions(False),
        ).pack(side="right", padx=(2, 0))
        _btn(
            queue_header,
            "Refresh",
            C["surface2"],
            C["border"],
            height=22,
            width=55,
            font=ctk.CTkFont(size=9),
            command=self._refresh_file_queue,
        ).pack(side="right")

        self.queue_scroll = ctk.CTkScrollableFrame(
            queue_outer,
            fg_color=C["surface"],
            height=90,
            scrollbar_button_color=C["surface2"],
            scrollbar_button_hover_color=C["border"],
        )
        self.queue_scroll.pack(fill="x", padx=4, pady=(0, 4))
        self.queue_scroll._parent_canvas.configure(
            bg=C["surface"], highlightthickness=0
        )
        self._queue_vars = {}

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
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        # Log Control Bar
        log_ctrl = ctk.CTkFrame(log_frame, fg_color=C["surface"])
        log_ctrl.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 4))

        _label(
            log_ctrl,
            "Processing Log",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=C["text3"],
        ).pack(side="left")

        self.log_search_var = ctk.StringVar()
        self.log_search_var.trace_add("write", lambda *_: self._refresh_log())
        _entry(
            log_ctrl,
            text_var=self.log_search_var,
            placeholder_text="Search...",
            width=120,
            height=24,
        ).pack(side="left", padx=(12, 4))
        self.log_level_var = ctk.StringVar(value="All")
        _combo(
            log_ctrl,
            ["All", "Info", "Processing", "Success", "Warn", "Error", "Cache"],
            variable=self.log_level_var,
            command=self._refresh_log,
            width=80,
            height=24,
        ).pack(side="left", padx=4)

        _btn(
            log_ctrl,
            "Clear",
            C["surface2"],
            C["border"],
            height=24,
            width=50,
            font=ctk.CTkFont(size=10),
            command=self._clear_log,
        ).pack(side="right", padx=(4, 0))
        _btn(
            log_ctrl,
            "Export",
            C["surface2"],
            C["border"],
            height=24,
            width=50,
            font=ctk.CTkFont(size=10),
            command=self._export_log,
        ).pack(side="right")
        _btn(
            log_ctrl,
            "🗑️ Clear Cache",
            C["surface2"],
            C["border"],
            height=24,
            width=80,
            font=ctk.CTkFont(size=10),
            command=self._flush_cache,
        ).pack(side="right", padx=(4, 4))

        self.console = ctk.CTkTextbox(
            log_frame,
            fg_color=C["surface"],
            corner_radius=0,
            border_width=0,
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self.console.grid(row=1, column=0, sticky="nsew", padx=0, pady=(0, 0))

        tb = self.console._textbox
        tb.tag_config("success", foreground=C["success"])
        tb.tag_config("processing", foreground=C["warn"])
        tb.tag_config("error", foreground=C["error"])
        tb.tag_config("info", foreground=C["text2"])
        tb.tag_config("cache", foreground=C["violet"])
        tb.tag_config("timestamp", foreground=C["text3"])
        self.console.configure(state="disabled")

        # ── Inspector Panel ──
        inspector_container = _frame(
            self.content_paned, border_width=1, border_color=C["border_sub"]
        )
        self.content_paned.add(inspector_container, minsize=280)

        inspector = ctk.CTkScrollableFrame(
            inspector_container,
            fg_color=C["surface"],
            scrollbar_button_color=C["surface2"],
            scrollbar_button_hover_color=C["border"],
        )
        inspector.pack(fill="both", expand=True)
        inspector._parent_canvas.configure(bg=C["surface"], highlightthickness=0)

        _label(
            inspector,
            "Inspector",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=C["text3"],
        ).pack(anchor="w", padx=12, pady=(8, 4))

        # Preview canvas
        preview_frame = ctk.CTkFrame(
            inspector, fg_color=C["surface2"], corner_radius=CR, height=180
        )
        preview_frame.pack(fill="x", padx=12, pady=(0, 6))
        preview_frame.pack_propagate(False)

        self.preview_lbl = ctk.CTkLabel(
            preview_frame,
            text="No Preview",
            width=180,
            height=170,
            fg_color="transparent",
            corner_radius=CR,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C["text3"],
        )
        self.preview_lbl.pack(expand=True)

        self.status_badge = ctk.CTkLabel(
            preview_frame,
            text="",
            fg_color="transparent",
            corner_radius=4,
            padx=6,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        )
        self.status_badge.place(relx=0.03, rely=0.05, anchor="nw")

        self.variant_badge = ctk.CTkLabel(
            preview_frame,
            text="",
            fg_color="transparent",
            corner_radius=4,
            padx=6,
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=C["accent"],
        )
        self.variant_badge.place(relx=0.03, rely=0.90, anchor="sw")

        self.edit_frame = inspector  # reference for edit vars

        self.edit_title_var = ctk.StringVar()
        self.edit_desc_var = ctk.StringVar()
        self.edit_kws_var = ctk.StringVar()

        _label(inspector, "Target Platform (Compliance)").pack(
            fill="x", padx=12, pady=(8, 0)
        )
        plat_row = ctk.CTkFrame(inspector, fg_color=C["surface"])
        plat_row.pack(fill="x", padx=12, pady=2)

        self.target_plat_var = ctk.StringVar(
            value=self.config.get("target_platform", "Adobe Stock")
        )
        self.target_plat_cb = _combo(
            plat_row,
            ["Adobe Stock", "Shutterstock", "Freepik", "Vecteezy"],
            variable=self.target_plat_var,
            command=lambda _: self._update_compliance(),
        )
        self.target_plat_cb.pack(side="left", expand=True, fill="x", padx=(0, 4))

        self.autofix_btn = _btn(
            plat_row,
            "Auto-Fix",
            C["accent"],
            C["accent_h"],
            height=28,
            width=70,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            command=self._autofix_metadata,
        )
        self.autofix_btn.pack(side="right")

        self.compliance_lbl = ctk.CTkLabel(
            inspector,
            text="● Pending Validation",
            text_color=C["text3"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
        )
        self.compliance_lbl.pack(fill="x", padx=12, pady=(0, 4), anchor="w")

        # ── Quality Score Bar ──
        self.quality_score_lbl = ctk.CTkLabel(
            inspector,
            text="SEO & Quality: —",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=C["text3"],
        )
        self.quality_score_lbl.pack(fill="x", padx=12, pady=(0, 0), anchor="w")
        self.quality_bar = ctk.CTkProgressBar(
            inspector,
            progress_color=C["success"],
            fg_color=C["surface2"],
            height=6,
            corner_radius=3,
        )
        self.quality_bar.set(0)
        self.quality_bar.pack(fill="x", padx=12, pady=(0, 2))
        self.quality_issues_lbl = ctk.CTkLabel(
            inspector,
            text="",
            text_color=C["text3"],
            font=ctk.CTkFont(family="Segoe UI", size=9),
            wraplength=280,
            justify="left",
        )
        self.quality_issues_lbl.pack(fill="x", padx=12, pady=(0, 4), anchor="w")

        # ── Sync Companion Toggle ──
        sync_row = ctk.CTkFrame(inspector, fg_color=C["surface"])
        sync_row.pack(fill="x", padx=12, pady=(0, 4))
        self.sync_companions = ctk.BooleanVar(
            value=self.config.get("sync_companion_files", True)
        )
        ctk.CTkSwitch(
            sync_row,
            text="Sync Companion Files",
            variable=self.sync_companions,
            progress_color=C["accent"],
            button_color=C["text3"],
            button_hover_color=C["text2"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
        ).pack(anchor="w")

        _label(inspector, "Title").pack(fill="x", padx=12, pady=(2, 0))
        self._title_entry = _entry(
            inspector, text_var=self.edit_title_var, placeholder_text="Title"
        )
        self._title_entry.pack(fill="x", padx=12, pady=2)
        self._title_entry.bind("<FocusIn>", lambda e: self._save_snapshot())

        # Title Case Formatter buttons
        title_fmt_row = ctk.CTkFrame(inspector, fg_color=C["surface"])
        title_fmt_row.pack(fill="x", padx=12, pady=(0, 2))
        _sm_font = ctk.CTkFont(family="Segoe UI", size=9)
        _btn(
            title_fmt_row,
            "Title Case",
            C["surface2"],
            C["border"],
            height=22,
            width=68,
            font=_sm_font,
            command=lambda: [
                self._save_snapshot(),
                self.edit_title_var.set(to_title_case(self.edit_title_var.get())),
            ],
        ).pack(side="left", padx=(0, 2))
        _btn(
            title_fmt_row,
            "Sentence",
            C["surface2"],
            C["border"],
            height=22,
            width=62,
            font=_sm_font,
            command=lambda: [
                self._save_snapshot(),
                self.edit_title_var.set(to_sentence_case(self.edit_title_var.get())),
            ],
        ).pack(side="left", padx=(0, 2))
        _btn(
            title_fmt_row,
            "UPPER",
            C["surface2"],
            C["border"],
            height=22,
            width=48,
            font=_sm_font,
            command=lambda: [
                self._save_snapshot(),
                self.edit_title_var.set(to_uppercase(self.edit_title_var.get())),
            ],
        ).pack(side="left", padx=(0, 2))
        _btn(
            title_fmt_row,
            "lower",
            C["surface2"],
            C["border"],
            height=22,
            width=42,
            font=_sm_font,
            command=lambda: [
                self._save_snapshot(),
                self.edit_title_var.set(to_lowercase(self.edit_title_var.get())),
            ],
        ).pack(side="left")

        _label(inspector, "Description").pack(fill="x", padx=12, pady=(4, 0))
        self._desc_entry = _entry(
            inspector, text_var=self.edit_desc_var, placeholder_text="Description"
        )
        self._desc_entry.pack(fill="x", padx=12, pady=2)
        self._desc_entry.bind("<FocusIn>", lambda e: self._save_snapshot())

        self.kw_counter_lbl = _label(
            inspector, "Keywords (0 / 20)", text_color=C["success"]
        )
        self.kw_counter_lbl.pack(fill="x", padx=12, pady=(4, 0))

        # ── Keyword Chips Area ──
        self.kw_chips_frame = ctk.CTkScrollableFrame(
            inspector, fg_color=C["surface2"], corner_radius=CR, height=120
        )
        self.kw_chips_frame.pack(fill="x", padx=12, pady=2)
        self.kw_chips_frame._parent_canvas.configure(
            bg=C["surface2"], highlightthickness=0
        )

        self.kw_add_frame = ctk.CTkFrame(inspector, fg_color=C["surface"])
        self.kw_add_frame.pack(fill="x", padx=12, pady=(0, 4))
        self.kw_add_entry = _entry(
            self.kw_add_frame, placeholder_text="Add keyword... (Press Enter)"
        )
        self.kw_add_entry.pack(side="left", fill="x", expand=True)
        self.kw_add_entry.bind("<Return>", lambda e: self._add_keyword_chip())

        # Sync chip frame with edit_kws_var
        self.edit_kws_var.trace_add(
            "write", lambda *_: self._trigger_render_keyword_chips()
        )
        self._kw_chip_widgets = []

        # Redundancy detector UI
        self.redundancy_frame = ctk.CTkFrame(inspector, fg_color=C["surface"])
        self.redundancy_frame.pack(fill="x", padx=12, pady=(0, 2))
        self.redundancy_lbl = ctk.CTkLabel(
            self.redundancy_frame,
            text="",
            text_color=C["warn"],
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        )
        self.redundancy_lbl.pack(side="left")
        self.redundancy_btn = _btn(
            self.redundancy_frame,
            "Remove Redundancies",
            C["surface2"],
            C["border"],
            height=22,
            font=ctk.CTkFont(family="Segoe UI", size=9),
            command=self._remove_redundancies,
        )
        self.redundancy_btn.pack(side="right")
        self.redundancy_btn.pack_forget()

        # Keyword cleanup buttons
        kw_fmt_row = ctk.CTkFrame(inspector, fg_color=C["surface"])
        kw_fmt_row.pack(fill="x", padx=12, pady=(0, 2))
        _btn(
            kw_fmt_row,
            "lowercase all",
            C["surface2"],
            C["border"],
            height=22,
            width=84,
            font=ctk.CTkFont(family="Segoe UI", size=9),
            command=self._lowercase_all_keywords,
        ).pack(side="left", padx=(0, 2))
        _btn(
            kw_fmt_row,
            "Trim Spacing",
            C["surface2"],
            C["border"],
            height=22,
            width=80,
            font=ctk.CTkFont(family="Segoe UI", size=9),
            command=self._trim_all_keywords,
        ).pack(side="left")

        # ── Keyword Presets ──
        preset_kw_row = ctk.CTkFrame(inspector, fg_color=C["surface"])
        preset_kw_row.pack(fill="x", padx=12, pady=(4, 2))
        _label(
            preset_kw_row,
            "Keyword Presets",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=C["text3"],
        ).pack(side="left")
        _btn(
            preset_kw_row,
            "Manage",
            C["surface2"],
            C["border"],
            height=22,
            width=60,
            font=ctk.CTkFont(family="Segoe UI", size=9),
            command=self._open_keyword_presets,
        ).pack(side="right")

        self.edit_title_var.trace_add("write", lambda *_: self._update_compliance())
        self.edit_kws_var.trace_add(
            "write",
            lambda *_: [
                self._update_kw_counter(),
                self._update_compliance(),
                self._update_quality_score(),
            ],
        )
        self.edit_title_var.trace_add("write", lambda *_: self._update_quality_score())
        self.edit_desc_var.trace_add("write", lambda *_: self._update_quality_score())

        # Undo / Redo toolbar
        undo_row = ctk.CTkFrame(inspector, fg_color=C["surface"])
        undo_row.pack(fill="x", padx=12, pady=(2, 0))
        _btn(
            undo_row,
            "↶ Undo",
            C["surface2"],
            C["border"],
            height=24,
            width=70,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=self.undo_metadata,
        ).pack(side="left", padx=(0, 4))
        _btn(
            undo_row,
            "↷ Redo",
            C["surface2"],
            C["border"],
            height=24,
            width=70,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=self.redo_metadata,
        ).pack(side="left")
        _label(
            undo_row,
            "Ctrl+Z / Ctrl+Y",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=C["text3"],
        ).pack(side="right")

        btn_row = ctk.CTkFrame(inspector, fg_color=C["surface"])
        btn_row.pack(fill="x", padx=12, pady=(4, 4))
        _btn(
            btn_row,
            "Dedup",
            C["surface2"],
            C["border"],
            height=28,
            width=80,
            command=self._dedup_keywords,
            font=ctk.CTkFont(family="Segoe UI", size=11),
        ).pack(side="left", padx=(0, 4))
        _btn(
            btn_row,
            "Batch Replace",
            C["warn"],
            C["warn_h"],
            height=28,
            width=100,
            command=self.open_batch_replace,
            font=ctk.CTkFont(family="Segoe UI", size=11),
        ).pack(side="left", padx=(0, 4))
        _btn(
            btn_row,
            "Save & Embed",
            C["success"],
            C["success_h"],
            height=28,
            command=self.save_manual,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        ).pack(side="right", expand=True, fill="x")

        btn_row2 = ctk.CTkFrame(inspector, fg_color=C["surface"])
        btn_row2.pack(fill="x", padx=12, pady=(0, 12))
        _btn(
            btn_row2,
            "Apply to Batch...",
            C["violet"],
            C["violet_h"],
            height=28,
            command=self._open_batch_apply,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        ).pack(fill="x")

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
        q = self.log_search_var.get().lower()
        flt = self.log_level_var.get().lower()
        if (flt == "all" or flt == level) and (not q or q in message.lower()):

            def _append():
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
            meta = ai.generate_metadata(
                preview, min_kw, max_kw, style_preset, extra_prompt
            )

            if meta.get("is_fallback") or meta.get("error"):
                self.log(
                    f"[ERROR] {name} (AI generation failed - fallback rejected)",
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
            self.log(f"{name} ({len(keywords)} kw)", "success")

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

            self.update_stats("success")
        else:
            self.log(f"{name} (Embed failed)", "error")
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
        ai = AIService(
            provider,
            api_key,
            (self.config.get("model") or "Gemini"),
            self.config.get("temperature", 0.3),
            failover_providers=failover_providers,
        )

        processed_dir = os.path.join(out_dir, "Processed Assets")
        csv_dir = os.path.join(out_dir, "Metadata CSV")
        os.makedirs(processed_dir, exist_ok=True)
        os.makedirs(csv_dir, exist_ok=True)

        csv_logger = CSVLogger(os.path.join(csv_dir, "metadata_output.csv"))

        with ThreadPoolExecutor(max_workers=self.config["workers"]) as executor:
            futures = [
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
                )
                for f in paths
            ]
            for i, f in enumerate(futures):
                f.result()
                if not self.cancel_flag:
                    self.after(0, self.progress_bar.set, (i + 1) / len(paths))

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


if __name__ == "__main__":
    app = App()
    app.mainloop()
