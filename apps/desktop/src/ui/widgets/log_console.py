import customtkinter as ctk

from ui.theme import C, _btn, _combo, _entry, _label


class LogConsole(ctk.CTkFrame):
    """Tabbable processing log: search, level filter, clear/export/cache actions."""

    def __init__(self, master, app):
        super().__init__(master, fg_color=C["surface"], corner_radius=0)
        self.app = app
        self._build()
        self.register_mirrors(app)

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        log_ctrl = ctk.CTkFrame(self, fg_color=C["surface"])
        log_ctrl.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 4))

        _label(
            log_ctrl,
            "Processing Log",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=C["text3"],
        ).pack(side="left")

        self.log_search_var = ctk.StringVar()
        self.log_search_var.trace_add("write", lambda *_: self.app._refresh_log())
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
            command=self.app._refresh_log,
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
            command=self.app._clear_log,
        ).pack(side="right", padx=(4, 0))
        _btn(
            log_ctrl,
            "Export",
            C["surface2"],
            C["border"],
            height=24,
            width=50,
            font=ctk.CTkFont(size=10),
            command=self.app._export_log,
        ).pack(side="right")
        _btn(
            log_ctrl,
            "🗑️ Clear Cache",
            C["surface2"],
            C["border"],
            height=24,
            width=80,
            font=ctk.CTkFont(size=10),
            command=self.app._flush_cache,
        ).pack(side="right", padx=(4, 4))

        self.console = ctk.CTkTextbox(
            self,
            fg_color=C["surface"],
            corner_radius=0,
            border_width=0,
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self.console.grid(row=1, column=0, sticky="nsew", padx=0, pady=(0, 0))

        tb = self.console._textbox
        tb.tag_config("info", foreground=C["info"])
        tb.tag_config("success", foreground=C["success_soft"])
        tb.tag_config("processing", foreground=C["cyan"])
        tb.tag_config("warn", foreground=C["warn_soft"])
        tb.tag_config("error", foreground=C["error_soft"])
        tb.tag_config("cache", foreground=C["cyan"])
        tb.tag_config("debug", foreground=C["text3"])
        tb.tag_config("timestamp", foreground=C["text3"])
        tb.configure(spacing1=2, spacing3=3)
        self.console.configure(state="disabled")

    def register_mirrors(self, app):
        app.log_search_var = self.log_search_var
        app.log_level_var = self.log_level_var
        app.console = self.console