"""Batch processing summary dialog. Extracted from AppWindow._show_batch_summary."""

import os

import customtkinter as ctk

from ui.theme import CR, C, _btn, _divider


def show_batch_summary(app):
    """Show batch processing summary dialog."""
    s = app.batch_session_stats
    dialog = ctk.CTkToplevel(app)
    dialog.title("Processing Summary Report")
    
    # Center modal
    w, h = 600, 480
    sx = (dialog.winfo_screenwidth() - w) // 2
    sy = (dialog.winfo_screenheight() - h) // 2
    dialog.geometry(f"{w}x{h}+{sx}+{sy}")
    
    dialog.configure(fg_color=C["bg"])
    dialog.transient(app)
    dialog.grab_set()

    processed = s.get("processed", 0)
    errors = s.get("errors", 0)
    skipped = s.get("skipped", 0)
    tokens_est = s.get("tokens_est", 0)
    cost = s.get("cost", 0)
    
    # Header badge logic
    if errors > 0:
        hdr_color = C["error"]
        hdr_icon = "\u274c"
        hdr_text = "Batch Completed with Errors"
    elif skipped > 0:
        hdr_color = C["warn"]
        hdr_icon = "\u26a0\ufe0f"
        hdr_text = "Batch Completed with Exclusions"
    else:
        hdr_color = C["success"]
        hdr_icon = "\u2714\ufe0f"
        hdr_text = "Batch Processing Complete"

    # Header
    ctk.CTkLabel(
        dialog,
        text=f"{hdr_icon}  {hdr_text}",
        font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
        text_color=hdr_color,
    ).pack(padx=24, pady=(24, 4), anchor="w")

    _divider(dialog).pack(fill="x", padx=24, pady=12)

    # Stats Grid
    grid_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    grid_frame.pack(fill="x", padx=24, pady=(0, 16))
    grid_frame.grid_columnconfigure((0, 1), weight=1)

    def _stat_card(parent, row, col, label, value, val_color):
        card = ctk.CTkFrame(parent, fg_color=C["surface"], corner_radius=CR)
        card.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(
            card, text=label, text_color=C["text3"], font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        ).pack(anchor="nw", padx=14, pady=(12, 0))
        ctk.CTkLabel(
            card, text=value, text_color=val_color, font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold")
        ).pack(anchor="nw", padx=14, pady=(2, 14))

    err_skip_color = C["error"] if errors > 0 else (C["text3"] if skipped == 0 else C["warn"])
    _stat_card(grid_frame, 0, 0, "FILES PROCESSED", str(processed), C["success"] if processed > 0 else C["text3"])
    _stat_card(grid_frame, 0, 1, "ERRORS / SKIPPED", f"{errors} / {skipped}", err_skip_color)
    _stat_card(grid_frame, 1, 0, "TOKENS USED", f"~{tokens_est:,}", C["warn"])
    _stat_card(grid_frame, 1, 1, "ESTIMATED COST", f"${cost:.4f}", C["warn"])

    # CSV files generated in a scrollable frame
    csvs = s.get("csvs", [])
    ctk.CTkLabel(
        dialog,
        text="Generated CSV Exports:",
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        text_color=C["text2"],
    ).pack(padx=30, pady=(4, 4), anchor="w")

    csv_scroll = ctk.CTkScrollableFrame(dialog, fg_color=C["surface"], corner_radius=CR, height=100)
    csv_scroll.pack(fill="both", expand=True, padx=24, pady=(0, 16))

    if not csvs:
        ctk.CTkLabel(
            csv_scroll, text="Tidak ada CSV yang diekspor.", text_color=C["text3"]
        ).pack(anchor="center", pady=30)
    else:
        for csv_f in csvs:
            row = ctk.CTkFrame(csv_scroll, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=4)
            ctk.CTkLabel(
                row,
                text=f"\ud83d\udcc4  {csv_f}",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=C["text"],
            ).pack(side="left")

    _divider(dialog).pack(fill="x", padx=24, pady=4)

    # Action buttons
    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_frame.pack(fill="x", padx=24, pady=(8, 20))

    def open_folder():
        out = s.get("out_dir", "")
        if out and os.path.isdir(out):
            os.startfile(out)

    def copy_summary():
        lines = [
            "=== NRA Metadata - Batch Processing Summary ===",
            f"Files Processed: {processed}",
            f"Files Skipped: {skipped}",
            f"Errors: {errors}",
            f"Estimated Tokens: ~{tokens_est:,}",
            f"Estimated Cost: ${cost:.4f}",
            f"CSV Exports: {', '.join(csvs)}",
        ]
        app.clipboard_clear()
        app.clipboard_append("\n".join(lines))

    # Tombol sekunder
    _btn(
        btn_frame,
        "\ud83d\udcc1 Buka Folder Output",
        C["surface2"],
        C["border"],
        command=open_folder,
        height=36,
        text_color=C["text"]
    ).pack(side="left", padx=(0, 8))
    
    _btn(
        btn_frame,
        "\ud83d\udccb Salin Ringkasan",
        C["surface2"],
        C["border"],
        command=copy_summary,
        height=36,
        text_color=C["text"]
    ).pack(side="left", padx=(0, 8))

    # Tombol primer
    _btn(
        btn_frame,
        "Selesai / Tutup",
        C["accent"],
        C["accent_h"],
        command=dialog.destroy,
        height=36,
        font=("Segoe UI", 13, "bold"),
    ).pack(side="right")
