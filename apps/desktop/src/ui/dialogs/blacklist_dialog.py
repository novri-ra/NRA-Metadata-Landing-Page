"""Blacklist Manager dialog. Extracted from AppWindow.open_blacklist_manager."""

import customtkinter as ctk

from packages.shared_utils.filter import (
    add_to_blacklist,
    get_blacklist,
    remove_from_blacklist,
)
from ui.theme import C, CR, _btn, _entry, _label


def show_blacklist_manager(app):
    dialog = ctk.CTkToplevel(app)
    dialog.title("Blacklist Manager")
    dialog.geometry("400x500")
    dialog.configure(fg_color=C["bg"])
    dialog.transient(app)
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
                app.log(f"Imported {len(words)} words to blacklist.", "info")

    def export_bl():
        path = ctk.filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text files", "*.txt")]
        )
        if path:
            import shutil

            from packages.shared_utils.filter import BLACKLIST_FILE

            shutil.copy(BLACKLIST_FILE, path)
            app.log("Blacklist exported.", "info")

    _btn(
        btn_frame, "Import .txt", C["surface2"], C["border"], command=import_bl
    ).pack(side="left", expand=True, padx=(0, 4))
    _btn(
        btn_frame, "Export .txt", C["surface2"], C["border"], command=export_bl
    ).pack(side="right", expand=True, padx=(4, 0))