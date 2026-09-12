import customtkinter as ctk

from ui.theme import C, CR, _btn, _label


class QueueView(ctk.CTkFrame):
    """File queue panel: header toolbar + scrollable rows of input files."""

    def __init__(self, master, app):
        super().__init__(
            master,
            fg_color=C["surface"],
            border_width=1,
            border_color=C["border_sub"],
            corner_radius=CR,
        )
        self.app = app
        self._build()
        self.register_mirrors(app)

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        queue_header = ctk.CTkFrame(self, fg_color=C["surface"])
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
            command=lambda: self.app._toggle_all_exclusions(True),
        ).pack(side="right", padx=(2, 0))
        _btn(
            queue_header,
            "Include All",
            C["surface2"],
            C["border"],
            height=22,
            width=75,
            font=ctk.CTkFont(size=9),
            command=lambda: self.app._toggle_all_exclusions(False),
        ).pack(side="right", padx=(2, 0))
        _btn(
            queue_header,
            "Refresh",
            C["surface2"],
            C["border"],
            height=22,
            width=55,
            font=ctk.CTkFont(size=9),
            command=self.app._refresh_file_queue,
        ).pack(side="right")

        self.queue_scroll = ctk.CTkScrollableFrame(
            self,
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

    def register_mirrors(self, app):
        app.queue_count_lbl = self.queue_count_lbl
        app.queue_scroll = self.queue_scroll
        app._queue_vars = self._queue_vars