"""Login / register modal dialog. Extracted from App.show_login_modal."""

import customtkinter as ctk

from ui.theme import C


def show_login_modal(app):
    app.withdraw()

    modal = ctk.CTkToplevel(app)
    modal.title("NRA Metadata - Autentikasi")
    modal.geometry("480x640")
    modal.resizable(False, False)
    modal.configure(fg_color=C["bg"])
    modal.protocol("WM_DELETE_WINDOW", lambda: _close_modal())
    modal.attributes("-topmost", True)
    modal.update_idletasks()

    def _close_modal():
        app._auth_modal_open = False
        modal.destroy()
        app.deiconify()

    def _alive(widget):
        try:
            return bool(widget.winfo_exists())
        except Exception:
            return False

    # Center Screen
    w, h = 480, 640
    sx = (modal.winfo_screenwidth() - w) // 2
    sy = (modal.winfo_screenheight() - h) // 2
    modal.geometry(f"{w}x{h}+{sx}+{sy}")

    # Fade in effect
    modal.attributes("-alpha", 0.0)

    def fade_in(alpha=0.0):
        if alpha >= 1.0:
            return
        if not _alive(modal):
            return
        alpha += 0.05
        try:
            modal.attributes("-alpha", alpha)
            modal.after(15, lambda: fade_in(alpha))
        except Exception:
            return

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

    # ───────────────────────── labelled entry row ─────────────────────────
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

    # ─────────────────────────────── LOGIN TAB ───────────────────────────
    login_scroll = ctk.CTkScrollableFrame(
        tab_login, fg_color="transparent", scrollbar_button_color=C["surface2"]
    )
    login_scroll.pack(fill="both", expand=True, padx=0, pady=0)

    # Remember account logic
    last_auth_user = app.config.get("last_auth_user", app.auth.username)
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
            app.config["last_auth_user"] = ""
            from backend.core.config_manager import save_config

            save_config(app.config)
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
        login_scroll, "Username", user_var_login, icon="\U0001f464"
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

    def _show_auth_error(label, msg):
        try:
            if _alive(label):
                label.configure(text=f"\u274c {msg}", text_color=C["error"])
        except Exception:
            pass
        import tkinter.messagebox as messagebox

        try:
            if _alive(modal):
                messagebox.showerror("Autentikasi", msg, parent=modal)
        except Exception:
            pass

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
            text="\u231b Menghubungkan...", text_color=C["text3"]
        )
        btn_login.configure(state="disabled", text="Memverifikasi...")
        modal.update()

        def _bg():
            try:
                res = app.auth.login(u, p)
            except Exception as e:
                try:
                    modal.after(
                        0,
                        lambda: _login_done(
                            {"status": "ERROR", "message": f"Login error: {e!s}"}, u
                        ),
                    )
                except Exception:
                    pass
                return
            try:
                modal.after(0, lambda: _login_done(res, u))
            except Exception:
                pass

        import threading

        threading.Thread(target=_bg, daemon=True).start()

    def _login_done(res, u):
        if not _alive(modal) or not _alive(btn_login):
            return
        try:
            btn_login.configure(state="normal", text="\U0001f680 Masuk ke Aplikasi")
        except Exception:
            return
        try:
            if res.get("error"):
                _show_auth_error(status_lbl_login, res.get("error"))
                return
            if res.get("status") == "SUCCESS":
                actual_user = res.get("username", u)
                if remember_var.get():
                    app.config["last_auth_user"] = actual_user
                    from backend.core.config_manager import save_config

                    save_config(app.config)
                else:
                    app.auth.config["auth_user"] = ""
                    app.config["last_auth_user"] = ""
                    from backend.core.config_manager import save_config

                    save_config(app.config)
                    save_config(app.auth.config)

                if _alive(status_lbl_login):
                    status_lbl_login.configure(
                        text="\u2705 Login berhasil!", text_color=C["success"]
                    )
                if not _alive(modal):
                    return
                modal.update()

                def fade_out(alpha=1.0):
                    if not _alive(modal):
                        app._auth_modal_open = False
                        return
                    if alpha > 0.0:
                        alpha -= 0.1
                        try:
                            modal.attributes("-alpha", alpha)
                            modal.after(15, lambda: fade_out(alpha))
                        except Exception:
                            app._auth_modal_open = False
                            return
                    else:
                        app._auth_modal_open = False
                        try:
                            modal.destroy()
                        except Exception:
                            pass
                        try:
                            app.deiconify()
                        except Exception:
                            pass

                fade_out()

                if _alive(app):
                    app.after(
                        500,
                        lambda: app.log(f"Login sukses sebagai {actual_user}", "success"),
                    )
            else:
                if _alive(status_lbl_login):
                    status_lbl_login.configure(
                        text=f"\u274c {res.get('message', 'Error login')}",
                        text_color=C["error"],
                    )
        except Exception:
            return

    btn_login.configure(command=_do_login)
    btn_login.pack(padx=20, pady=(8, 12))

    def _go_offline():
        app._auth_modal_open = False
        app.auth.enable_offline_mode()
        app.deiconify()
        modal.destroy()
        app.log("Mode Offline aktif: autentikasi server dilewati.", "warn")

    ctk.CTkButton(
        login_scroll,
        text="\U0001f6e1\ufe0f Lanjut Mode Offline / Pengembang",
        width=FW,
        fg_color=C["surface2"],
        hover_color=C["border"],
        font=ctk.CTkFont(family="Segoe UI", size=12),
        height=34,
        corner_radius=8,
        command=_go_offline,
    ).pack(padx=20, pady=(0, 16))

    # ───────────────────────────── REGISTER TAB ──────────────────────────
    reg_scroll = ctk.CTkScrollableFrame(
        tab_register, fg_color="transparent", scrollbar_button_color=C["surface2"]
    )
    reg_scroll.pack(fill="both", expand=True, padx=0, pady=0)

    user_var_reg = ctk.StringVar()
    pass_var_reg = ctk.StringVar()
    pass2_var_reg = ctk.StringVar()
    show_pass_reg = ctk.BooleanVar(value=False)

    _field(reg_scroll, "Username", user_var_reg, icon="\U0001f464")

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
        u = user_var_reg.get().strip()
        pw = pass_var_reg.get().strip()
        pw2 = pass2_var_reg.get().strip()
        if not u or not pw:
            return None, "Isi username dan password"
        if pw != pw2:
            return None, "Password dan konfirmasi tidak cocok"
        return {
            "username": u,
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
            text="\u231b Menghubungkan...", text_color=C["text3"]
        )
        btn_reg.configure(state="disabled", text="Menghubungkan...")
        modal.update()

        def _bg():
            try:
                res = app.auth.register(
                    data["username"],
                    data["password"],
                )
            except Exception as e:
                try:
                    modal.after(
                        0,
                        lambda: _reg_done(
                            {"status": "ERROR", "message": f"Registrasi error: {e!s}"},
                            data["username"],
                        ),
                    )
                except Exception:
                    pass
                return
            try:
                modal.after(0, lambda: _reg_done(res, data["username"]))
            except Exception:
                pass

        import threading

        threading.Thread(target=_bg, daemon=True).start()

    def _reg_done(res, u):
        if not _alive(modal) or not _alive(btn_reg):
            return
        try:
            btn_reg.configure(
                state="normal", text="\u2728 Buat Akun & Gabung Komunitas"
            )
        except Exception:
            return
        try:
            if res.get("error"):
                _show_auth_error(status_lbl_reg, res.get("error"))
                return
            if res.get("status") == "SUCCESS":
                if _alive(status_lbl_reg):
                    status_lbl_reg.configure(
                        text="\u2705 Registrasi sukses! Silakan login.",
                        text_color=C["success"],
                    )
                user_var_login.set(u)
                if _alive(tabview):
                    tabview.set(" Masuk ")
            else:
                if _alive(status_lbl_reg):
                    status_lbl_reg.configure(
                        text=f"\u274c {res.get('message', 'Error registrasi')}",
                        text_color=C["error"],
                    )
        except Exception:
            return

    btn_reg.configure(command=_do_register)
    btn_reg.pack(padx=20, pady=(8, 12))

    modal.grab_set()
    # Defer sash restore until window is rendered
    app.after(100, app._restore_sash_positions)
    # Watcher lifecycle and keyboard shortcuts are owned by AppWindow itself
    # (_apply_auto_watch_startup / _toggle_auto_watch / __init__ binds).