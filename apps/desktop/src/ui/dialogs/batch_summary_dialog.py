"""Batch processing summary dialog. Extracted from AppWindow._show_batch_summary."""

import os

import customtkinter as ctk

from ui.theme import C, CR, _btn, _divider


def show_batch_summary(app):
    """Show batch processing summary dialog."""
    s = app.batch_session_stats
    dialog = ctk.CTkToplevel(app)
    dialog.title("Processing Summary Report")
    dialog.geometry("480x420")
    dialog.configure(fg_color=C["bg"])
    dialog.transient(app)
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
        app.clipboard_clear()
        app.clipboard_append("\n".join(lines))
        app.log("Summary copied to clipboard.", "info")

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