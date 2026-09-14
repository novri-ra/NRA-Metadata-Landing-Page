"""FTP Uploader dialog. Extracted from AppWindow.open_ftp_dialog."""

import os
import threading

import customtkinter as ctk

from backend.core.config_manager import save_config
from packages.shared_utils.ftp_uploader import FTPClient
from ui.theme import C, _btn, _combo, _entry, _label


def show_ftp_dialog(app):
    dialog = ctk.CTkToplevel(app)
    dialog.title("FTP Uploader")
    dialog.geometry("450x450")
    dialog.configure(fg_color=C["bg"])
    dialog.transient(app)
    dialog.grab_set()

    _label(dialog, "Preset").pack(padx=12, pady=(12, 2), anchor="w")
    preset_cb = _combo(
        dialog, ["Custom", "Adobe Stock", "Shutterstock", "Vecteezy", "Freepik"]
    )
    preset_cb.pack(padx=12, pady=2, fill="x")

    _label(dialog, "Host").pack(padx=12, pady=2, anchor="w")
    host_entry = _entry(dialog)
    host_entry.insert(0, app.config.get("ftp_host", ""))
    host_entry.pack(padx=12, pady=2, fill="x")

    _label(dialog, "Port").pack(padx=12, pady=2, anchor="w")
    port_entry = _entry(dialog)
    port_entry.insert(0, "21")
    port_entry.pack(padx=12, pady=2, fill="x")

    _label(dialog, "Username").pack(padx=12, pady=2, anchor="w")
    user_entry = _entry(dialog)
    user_entry.insert(0, app.config.get("ftp_user", ""))
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
        app.config["ftp_host"] = h
        app.config["ftp_user"] = u
        save_config(app.config)

        target_dir = app.input_dir.get()
        if not target_dir or not os.path.isdir(target_dir):
            status_lbl.configure(
                text="No folder selected in main window", text_color=C["error"]
            )
            return

        dialog.destroy()
        threading.Thread(
            target=app._run_ftp_upload,
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