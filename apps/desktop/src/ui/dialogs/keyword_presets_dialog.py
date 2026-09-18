"""Keyword Presets dialog. Extracted from AppWindow._open_keyword_presets."""

import customtkinter as ctk

from packages.shared_utils.presets import delete_preset as delete_kw_preset
from packages.shared_utils.presets import (
    export_presets,
    get_preset,
    get_preset_names,
    import_presets,
)
from packages.shared_utils.presets import save_preset as save_kw_preset
from ui.theme import CR, C, _btn, _divider, _entry, _label


def show_keyword_presets(app):
    dialog = ctk.CTkToplevel(app)
    dialog.title("Keyword Presets")
    dialog.geometry("420x480")
    dialog.configure(fg_color=C["bg"])
    dialog.transient(app)
    dialog.grab_set()
    dialog.bind("<Escape>", lambda e: dialog.destroy())

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
        kws = app._get_kws_list()
        save_kw_preset(n, kws)
        name_entry.delete(0, "end")
        refresh()
        app.log(f"Saved keyword preset: {n} ({len(kws)} keywords)", "info")

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
                command=lambda n=pname: app._apply_preset_kws(n, "append"),
            ).pack(side="right", padx=2)

            ctk.CTkButton(
                row,
                text="Replace",
                width=55,
                height=20,
                fg_color=C["accent"],
                hover_color=C["accent_h"],
                font=ctk.CTkFont(size=9),
                command=lambda n=pname: app._apply_preset_kws(n, "replace"),
            ).pack(side="right", padx=2)

    refresh()

    io_row = ctk.CTkFrame(dialog, fg_color="transparent")
    io_row.pack(fill="x", padx=12, pady=(0, 12))

    def do_import():
        path = ctk.filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            count = import_presets(path)
            refresh()
            app.log(f"Imported {count} keyword presets.", "info")

    def do_export():
        path = ctk.filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON", "*.json")]
        )
        if path:
            export_presets(path)
            app.log("Keyword presets exported.", "info")

    _btn(
        io_row, "Import .json", C["surface2"], C["border"], command=do_import
    ).pack(side="left", expand=True, padx=(0, 4))
    _btn(
        io_row, "Export .json", C["surface2"], C["border"], command=do_export
    ).pack(side="right", expand=True, padx=(4, 0))