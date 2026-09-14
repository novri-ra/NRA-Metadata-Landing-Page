import customtkinter as ctk

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
    "info": "#a1a1aa",  # zinc-400 — info log tag
    "success_soft": "#34d399",  # emerald-400 — success log tag
    "warn_soft": "#fbbf24",  # amber-400 — warning log tag
    "error_soft": "#f87171",  # red-400 — error log tag
    "cyan": "#22d3ee",  # cyan-400 — processing/cache log tag
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