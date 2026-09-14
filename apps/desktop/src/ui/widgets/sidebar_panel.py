import customtkinter as ctk

from ui.theme import C, _btn, _combo, _divider, _entry, _label, _section_header, _slider


class SidebarPanel(ctk.CTkFrame):
    """Left sidebar: profiles, AI engine, keywords, processing, export."""

    def __init__(self, master, app):
        super().__init__(master, fg_color=C["surface"], corner_radius=0)
        self.app = app
        self._build()
        self.register_mirrors(app)
        app._load_custom_presets()

    def _build(self):
        sidebar = ctk.CTkScrollableFrame(
            self,
            fg_color=C["surface"],
            corner_radius=0,
            scrollbar_button_color=C["surface2"],
            scrollbar_button_hover_color=C["border"],
        )
        sidebar.pack(fill="both", expand=True)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar._parent_canvas.configure(bg=C["surface"], highlightthickness=0)

        PAD = {"padx": 12, "pady": (0, 4)}
        LPAD = {"padx": 12, "pady": (0, 1)}
        app = self.app
        config = app.config

        _section_header(sidebar, "Profiles").pack(fill="x", **{**PAD, "pady": (12, 6)})

        preset_row = ctk.CTkFrame(sidebar, fg_color=C["surface"])
        preset_row.pack(fill="x", **LPAD)
        self.preset_var = ctk.StringVar(value=config.get("active_profile", "Default"))
        self.preset_cb = _combo(
            preset_row,
            [
                "Default",
                "Adobe Stock Vector",
                "Shutterstock Photo",
                "Vecteezy Icon/Clipart",
            ],
            command=app._on_preset_change,
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
            command=app._save_preset,
        ).pack(side="left", padx=1)
        _btn(
            preset_row,
            "Del",
            C["error"],
            C["error_h"],
            width=30,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=app._delete_preset,
        ).pack(side="left", padx=(1, 0))

        _section_header(sidebar, "AI Engine").pack(fill="x", **{**PAD, "pady": (12, 6)})

        _label(sidebar, "Provider").pack(fill="x", anchor="w", **LPAD)
        self.provider_cb = _combo(
            sidebar,
            ["Gemini", "OpenAI", "Mistral", "Groq", "Custom"],
            command=app._on_provider_change,
        )

        provider = config.get("provider", "Gemini")
        if provider not in ["Gemini", "OpenAI", "Mistral", "Groq", "Custom"]:
            provider = "Gemini"

        self.provider_cb.set(provider)
        self.provider_cb.pack(fill="x", **PAD)

        _label(sidebar, "Model").pack(fill="x", anchor="w", **LPAD)
        model_list = app.MODEL_MAP.get(provider, [])
        self.model_cb = _combo(
            sidebar, model_list, command=lambda _: app._save_current_config()
        )
        saved_model = config.get("model", "")

        if saved_model and saved_model in model_list:
            self.model_cb.set(saved_model)
        elif model_list:
            self.model_cb.set(model_list[0])
            config["model"] = model_list[0]

        self.model_cb.pack(fill="x", **PAD)

        _label(sidebar, "API Key").pack(fill="x", anchor="w", **LPAD)
        self.api_key_entry = _entry(sidebar, show="*")
        self.keys_counter_lbl = _label(sidebar, "(0 keys loaded)")
        self.keys_counter_lbl.pack(fill="x", anchor="w", padx=16, pady=2)

        if "api_keys" not in config:
            config["api_keys"] = {}
            if "api_key" in config:
                old_key = config.pop("api_key")
                old_provider = config.get("provider", "Gemini")
                if old_key:
                    config["api_keys"][old_provider] = old_key

        current_provider = config.get("provider", "Gemini")
        self.api_key_entry.insert(0, config["api_keys"].get(current_provider, ""))
        self.api_key_entry.pack(fill="x", **PAD)

        def _on_key_type(event=None):
            active_prov = self.provider_cb.get()
            if "api_keys" not in config:
                config["api_keys"] = {}
            config["api_keys"][active_prov] = self.api_key_entry.get().strip()
            app._save_current_config()

        self.api_key_entry.bind("<KeyRelease>", _on_key_type)
        self.api_key_entry.bind("<FocusOut>", _on_key_type)

        self.fetch_models_btn = ctk.CTkButton(
            sidebar,
            text="🔄 Fetch Models",
            fg_color=C["surface2"],
            hover_color=C["border"],
            text_color=C["text2"],
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=app._fetch_models,
        )
        self.fetch_models_btn.pack(fill="x", padx=16, pady=(0, 16))

        _label(sidebar, "Custom Base URL (OpenAI-compatible)").pack(
            fill="x", anchor="w", **LPAD
        )
        self.base_url_entry = _entry(sidebar)
        self.base_url_entry.insert(0, config.get("custom_base_url", ""))
        self.base_url_entry.pack(fill="x", **PAD)

        def _on_base_url_type(event=None):
            config["custom_base_url"] = self.base_url_entry.get().strip()
            app._save_current_config()

        self.base_url_entry.bind("<KeyRelease>", _on_base_url_type)
        self.base_url_entry.bind("<FocusOut>", _on_base_url_type)

        temp_row = ctk.CTkFrame(sidebar, fg_color=C["surface"])
        temp_row.pack(fill="x", **LPAD)
        _label(temp_row, "Temperature").pack(side="left")
        self.temp_val = ctk.StringVar(value=f"{config.get('temperature', 0.3):.1f}")
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
        self.temp_slider.set(config.get("temperature", 0.3))
        self.temp_slider.pack(fill="x", **PAD)
        self.temp_slider.bind(
            "<ButtonRelease-1>", lambda e: app._save_current_config()
        )
        update_temp_lbl(config.get("temperature", 0.3))

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
            command=lambda _: app._save_current_config(),
        )
        self.style_cb.set(config.get("style_preset", "General Commercial"))
        self.style_cb.pack(fill="x", **PAD)

        kw_row = ctk.CTkFrame(sidebar, fg_color=C["surface"])
        kw_row.pack(fill="x", padx=12, pady=(0, 4))
        kw_row.grid_columnconfigure(0, weight=1)
        kw_row.grid_columnconfigure(1, weight=1)

        lf = ctk.CTkFrame(kw_row, fg_color=C["surface"])
        lf.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        _label(lf, "Min KW").pack(anchor="w")
        self.min_kw_entry = _entry(lf, width=60)
        self.min_kw_entry.insert(0, str(config.get("min_kw", 10)))
        self.min_kw_entry.pack(fill="x")
        self.min_kw_entry.bind("<FocusOut>", lambda e: app._save_current_config())

        rf = ctk.CTkFrame(kw_row, fg_color=C["surface"])
        rf.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        _label(rf, "Max KW").pack(anchor="w")
        self.max_kw_entry = _entry(rf, width=60)
        self.max_kw_entry.insert(0, str(config.get("max_kw", 49)))
        self.max_kw_entry.pack(fill="x")
        self.max_kw_entry.bind("<FocusOut>", lambda e: app._save_current_config())

        self.custom_kw_range = ctk.BooleanVar(
            value=bool(config.get("kw_locked", False))
        )
        ctk.CTkCheckBox(
            kw_row,
            text="Custom Range (override platform)",
            variable=self.custom_kw_range,
            fg_color=C["accent"],
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=lambda: app._save_current_config(),
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=(0, 4), pady=(4, 0))

        _label(sidebar, "Mandatory Keywords").pack(fill="x", anchor="w", **LPAD)
        self.custom_kw_entry = _entry(sidebar, placeholder_text="e.g. 3d, isolated")
        self.custom_kw_entry.insert(0, config.get("custom_kw", ""))
        self.custom_kw_entry.pack(fill="x", **PAD)
        self.custom_kw_entry.bind("<FocusOut>", lambda e: app._save_current_config())

        _label(sidebar, "Extra AI Context / Focus").pack(fill="x", anchor="w", **LPAD)
        self.extra_prompt_entry = _entry(
            sidebar, placeholder_text="e.g. Isolated on white background"
        )
        self.extra_prompt_entry.insert(0, config.get("extra_prompt", ""))
        self.extra_prompt_entry.pack(fill="x", **PAD)
        self.extra_prompt_entry.bind(
            "<FocusOut>", lambda e: app._save_current_config()
        )

        inj_row = ctk.CTkFrame(sidebar, fg_color=C["surface"])
        inj_row.pack(fill="x", **LPAD)
        _label(inj_row, "Inject at:").pack(side="left", padx=(0, 4))
        self.custom_kw_pos = _combo(
            inj_row,
            ["Start (Priority)", "End"],
            command=lambda _: app._save_current_config(),
        )
        self.custom_kw_pos.set(config.get("custom_kw_pos", "Start (Priority)"))
        self.custom_kw_pos.pack(side="left", expand=True, fill="x")

        _section_header(sidebar, "Processing").pack(
            fill="x", **{**PAD, "pady": (10, 6)}
        )

        workers_row = ctk.CTkFrame(sidebar, fg_color=C["surface"])
        workers_row.pack(fill="x", **LPAD)
        _label(workers_row, "Workers").pack(side="left")
        self.workers_val = ctk.StringVar(value=str(config.get("workers", 2)))
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
        self.workers_slider.set(config.get("workers", 2))
        self.workers_slider.pack(fill="x", **PAD)
        self.workers_slider.bind(
            "<ButtonRelease-1>", lambda e: app._save_current_config()
        )

        delay_val = config.get("delay", 0)
        if not (0 <= delay_val <= 5):
            delay_val = 0

        delay_row = ctk.CTkFrame(sidebar, fg_color=C["surface"])
        delay_row.pack(fill="x", **LPAD)
        _label(delay_row, "Delay after file (s)").pack(side="left")
        self.delay_val = ctk.StringVar(value=f"{int(delay_val)}s")
        ctk.CTkLabel(
            delay_row,
            textvariable=self.delay_val,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=C["accent"],
        ).pack(side="right")

        def update_delay_lbl(val):
            self.delay_val.set(f"{int(round(float(val)))}s")

        self.delay_slider = _slider(
            sidebar,
            from_=0,
            to=5,
            number_of_steps=5,
            command=update_delay_lbl,
            progress_color=C["accent"],
        )
        self.delay_slider.set(int(delay_val))
        self.delay_slider.pack(fill="x", **PAD)
        self.delay_slider.bind(
            "<ButtonRelease-1>", lambda e: app._save_current_config()
        )
        update_delay_lbl(int(delay_val))

        _label(sidebar, "Formats").pack(fill="x", anchor="w", **LPAD)
        fmt_saved = config.get("formats", {})
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

        toggle_frame = ctk.CTkFrame(sidebar, fg_color=C["surface"])
        toggle_frame.pack(fill="x", padx=12, pady=(0, 6))
        self.auto_watch = ctk.BooleanVar(value=config.get("auto_watch", False))
        ctk.CTkSwitch(
            toggle_frame,
            text="Auto-Watch",
            variable=self.auto_watch,
            command=app._toggle_auto_watch,
            progress_color=C["success"],
            button_color=C["text3"],
            button_hover_color=C["text2"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
        ).pack(anchor="w", pady=1)
        self.auto_zip = ctk.BooleanVar(value=config.get("auto_zip_vector", False))
        ctk.CTkSwitch(
            toggle_frame,
            text="Auto-Zip Vector",
            variable=self.auto_zip,
            progress_color=C["success"],
            button_color=C["text3"],
            button_hover_color=C["text2"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
        ).pack(anchor="w", pady=1)

        _section_header(sidebar, "Output & Export").pack(
            fill="x", **{**PAD, "pady": (10, 6)}
        )

        _label(sidebar, "Author").pack(fill="x", anchor="w", **LPAD)
        self.author_entry = _entry(sidebar)
        self.author_entry.insert(0, config.get("author", ""))
        self.author_entry.pack(fill="x", **PAD)
        self.author_entry.bind("<FocusOut>", lambda e: app._save_current_config())

        _label(sidebar, "Copyright").pack(fill="x", anchor="w", **LPAD)
        self.copyright_entry = _entry(sidebar)
        self.copyright_entry.insert(0, config.get("copyright", ""))
        self.copyright_entry.pack(fill="x", **PAD)
        self.copyright_entry.bind("<FocusOut>", lambda e: app._save_current_config())

        _label(sidebar, "Generate CSVs").pack(fill="x", anchor="w", **LPAD)
        csv_frame = ctk.CTkFrame(sidebar, fg_color=C["surface"])
        csv_frame.pack(fill="x", padx=12, pady=(0, 6))

        self.csv_vars = {}
        csv_defs = ["Generic", "Adobe Stock", "Shutterstock", "Vecteezy", "Freepik"]
        saved_csvs = config.get(
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

        _divider(sidebar).pack(fill="x", padx=12, pady=(8, 8))

        self.start_btn = _btn(
            sidebar,
            "▶  Start Processing",
            C["accent"],
            C["accent_h"],
            command=app.start_processing,
        )
        self.start_btn.pack(fill="x", padx=12, pady=(0, 4))

        ctrl_frame = ctk.CTkFrame(sidebar, fg_color=C["surface"])
        ctrl_frame.pack(fill="x", padx=12, pady=(0, 4))

        self.pause_btn = _btn(
            ctrl_frame,
            "Pause",
            C["warn"],
            C["warn_h"],
            command=app.toggle_pause,
            width=90,
        )
        self.pause_btn.pack(side="left", padx=(0, 4), expand=True, fill="x")
        self.pause_btn.configure(state="disabled")

        self.cancel_btn = _btn(
            ctrl_frame,
            "Cancel",
            C["error"],
            C["error_h"],
            command=app.cancel_batch,
            width=90,
        )
        self.cancel_btn.pack(side="right", padx=(4, 0), expand=True, fill="x")
        self.cancel_btn.configure(state="disabled")

        self.retag_btn = _btn(
            sidebar,
            "Import Metadata from CSV...",
            C["surface2"],
            C["border"],
            command=app.start_offline_retag,
        )
        self.retag_btn.pack(fill="x", padx=12, pady=(4, 2))

        self.ftp_btn = _btn(
            sidebar,
            "FTP / SFTP Upload",
            C["violet"],
            C["violet_h"],
            command=app.open_ftp_dialog,
        )
        self.ftp_btn.pack(fill="x", padx=12, pady=(2, 6))

        self.blacklist_btn = _btn(
            sidebar,
            "Manage Blacklist",
            C["surface2"],
            C["border"],
            command=app.open_blacklist_manager,
        )
        self.blacklist_btn.pack(fill="x", padx=12, pady=(2, 16))

    def register_mirrors(self, app):
        for name in (
            "preset_var",
            "preset_cb",
            "provider_cb",
            "model_cb",
            "api_key_entry",
            "keys_counter_lbl",
            "fetch_models_btn",
            "base_url_entry",
            "temp_val",
            "temp_slider",
            "style_cb",
            "min_kw_entry",
            "max_kw_entry",
            "custom_kw_range",
            "custom_kw_entry",
            "extra_prompt_entry",
            "custom_kw_pos",
            "workers_val",
            "workers_slider",
            "delay_val",
            "delay_slider",
            "fmt_vars",
            "auto_watch",
            "auto_zip",
            "author_entry",
            "copyright_entry",
            "csv_vars",
            "start_btn",
            "pause_btn",
            "cancel_btn",
            "retag_btn",
            "ftp_btn",
            "blacklist_btn",
        ):
            setattr(app, name, getattr(self, name))