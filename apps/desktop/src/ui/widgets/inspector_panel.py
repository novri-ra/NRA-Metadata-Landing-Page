import customtkinter as ctk

from packages.shared_utils.filter import (
    to_lowercase,
    to_sentence_case,
    to_title_case,
    to_uppercase,
)
from ui.theme import C, CR, _btn, _combo, _entry, _label


class InspectorPanel(ctk.CTkFrame):
    """Right inspector: preview, compliance, quality, editable metadata fields."""

    def __init__(self, master, app):
        super().__init__(master, fg_color=C["surface"], corner_radius=0)
        self.app = app
        self._scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=C["surface"],
            scrollbar_button_color=C["surface2"],
            scrollbar_button_hover_color=C["border"],
        )
        self._scroll.pack(fill="both", expand=True)
        self._scroll._parent_canvas.configure(bg=C["surface"], highlightthickness=0)
        self._build()
        self.register_mirrors(app)
        self._bind_traces(app)

    def _build(self):
        inspector = self._scroll
        app = self.app
        config = app.config

        _label(
            inspector,
            "Inspector",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=C["text3"],
        ).pack(anchor="w", padx=12, pady=(8, 4))

        preview_frame = ctk.CTkFrame(
            inspector, fg_color=C["surface2"], corner_radius=CR, height=180
        )
        preview_frame.pack(fill="x", padx=12, pady=(0, 6))
        preview_frame.pack_propagate(False)

        self.preview_lbl = ctk.CTkLabel(
            preview_frame,
            text="No Preview",
            width=180,
            height=170,
            fg_color="transparent",
            corner_radius=CR,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C["text3"],
        )
        self.preview_lbl.pack(expand=True)

        self.status_badge = ctk.CTkLabel(
            preview_frame,
            text="",
            fg_color="transparent",
            corner_radius=4,
            padx=6,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        )
        self.status_badge.place(relx=0.03, rely=0.05, anchor="nw")

        self.variant_badge = ctk.CTkLabel(
            preview_frame,
            text="",
            fg_color="transparent",
            corner_radius=4,
            padx=6,
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=C["accent"],
        )
        self.variant_badge.place(relx=0.03, rely=0.90, anchor="sw")

        self.edit_title_var = ctk.StringVar()
        self.edit_desc_var = ctk.StringVar()
        self.edit_kws_var = ctk.StringVar()

        _label(inspector, "Target Platform (Compliance)").pack(
            fill="x", padx=12, pady=(8, 0)
        )
        plat_row = ctk.CTkFrame(inspector, fg_color=C["surface"])
        plat_row.pack(fill="x", padx=12, pady=2)

        self.target_plat_var = ctk.StringVar(
            value=config.get("target_platform", "Adobe Stock")
        )
        self.target_plat_cb = _combo(
            plat_row,
            ["Adobe Stock", "Shutterstock", "Freepik", "Vecteezy"],
            variable=self.target_plat_var,
            command=lambda _: app._update_compliance(),
        )
        self.target_plat_cb.pack(side="left", expand=True, fill="x", padx=(0, 4))

        self.autofix_btn = _btn(
            plat_row,
            "Auto-Fix",
            C["accent"],
            C["accent_h"],
            height=28,
            width=70,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            command=app._autofix_metadata,
        )
        self.autofix_btn.pack(side="right")

        self.compliance_lbl = ctk.CTkLabel(
            inspector,
            text="● Pending Validation",
            text_color=C["text3"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
        )
        self.compliance_lbl.pack(fill="x", padx=12, pady=(0, 4), anchor="w")

        self.quality_score_lbl = ctk.CTkLabel(
            inspector,
            text="SEO & Quality: —",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=C["text3"],
        )
        self.quality_score_lbl.pack(fill="x", padx=12, pady=(0, 0), anchor="w")
        self.quality_bar = ctk.CTkProgressBar(
            inspector,
            progress_color=C["success"],
            fg_color=C["surface2"],
            height=6,
            corner_radius=3,
        )
        self.quality_bar.set(0)
        self.quality_bar.pack(fill="x", padx=12, pady=(0, 2))
        self.quality_issues_lbl = ctk.CTkLabel(
            inspector,
            text="",
            text_color=C["text3"],
            font=ctk.CTkFont(family="Segoe UI", size=9),
            wraplength=280,
            justify="left",
        )
        self.quality_issues_lbl.pack(fill="x", padx=12, pady=(0, 4), anchor="w")

        sync_row = ctk.CTkFrame(inspector, fg_color=C["surface"])
        sync_row.pack(fill="x", padx=12, pady=(0, 4))
        self.sync_companions = ctk.BooleanVar(
            value=config.get("sync_companion_files", True)
        )
        ctk.CTkSwitch(
            sync_row,
            text="Sync Companion Files",
            variable=self.sync_companions,
            progress_color=C["accent"],
            button_color=C["text3"],
            button_hover_color=C["text2"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
        ).pack(anchor="w")

        _label(inspector, "Title").pack(fill="x", padx=12, pady=(2, 0))
        self._title_entry = _entry(
            inspector, text_var=self.edit_title_var, placeholder_text="Title"
        )
        self._title_entry.pack(fill="x", padx=12, pady=2)
        self._title_entry.bind("<FocusIn>", lambda e: app._save_snapshot())

        title_fmt_row = ctk.CTkFrame(inspector, fg_color=C["surface"])
        title_fmt_row.pack(fill="x", padx=12, pady=(0, 2))
        _sm_font = ctk.CTkFont(family="Segoe UI", size=9)
        _btn(
            title_fmt_row,
            "Title Case",
            C["surface2"],
            C["border"],
            height=22,
            width=68,
            font=_sm_font,
            command=lambda: [
                app._save_snapshot(),
                self.edit_title_var.set(to_title_case(self.edit_title_var.get())),
            ],
        ).pack(side="left", padx=(0, 2))
        _btn(
            title_fmt_row,
            "Sentence",
            C["surface2"],
            C["border"],
            height=22,
            width=62,
            font=_sm_font,
            command=lambda: [
                app._save_snapshot(),
                self.edit_title_var.set(to_sentence_case(self.edit_title_var.get())),
            ],
        ).pack(side="left", padx=(0, 2))
        _btn(
            title_fmt_row,
            "UPPER",
            C["surface2"],
            C["border"],
            height=22,
            width=48,
            font=_sm_font,
            command=lambda: [
                app._save_snapshot(),
                self.edit_title_var.set(to_uppercase(self.edit_title_var.get())),
            ],
        ).pack(side="left", padx=(0, 2))
        _btn(
            title_fmt_row,
            "lower",
            C["surface2"],
            C["border"],
            height=22,
            width=42,
            font=_sm_font,
            command=lambda: [
                app._save_snapshot(),
                self.edit_title_var.set(to_lowercase(self.edit_title_var.get())),
            ],
        ).pack(side="left")

        _label(inspector, "Description").pack(fill="x", padx=12, pady=(4, 0))
        self._desc_entry = _entry(
            inspector, text_var=self.edit_desc_var, placeholder_text="Description"
        )
        self._desc_entry.pack(fill="x", padx=12, pady=2)
        self._desc_entry.bind("<FocusIn>", lambda e: app._save_snapshot())

        self.kw_counter_lbl = _label(
            inspector, "Keywords (0 / 20)", text_color=C["success"]
        )
        self.kw_counter_lbl.pack(fill="x", padx=12, pady=(4, 0))

        self.kw_chips_frame = ctk.CTkScrollableFrame(
            inspector, fg_color=C["surface2"], corner_radius=CR, height=120
        )
        self.kw_chips_frame.pack(fill="x", padx=12, pady=2)
        self.kw_chips_frame._parent_canvas.configure(
            bg=C["surface2"], highlightthickness=0
        )

        self.kw_add_frame = ctk.CTkFrame(inspector, fg_color=C["surface"])
        self.kw_add_frame.pack(fill="x", padx=12, pady=(0, 4))
        self.kw_add_entry = _entry(
            self.kw_add_frame, placeholder_text="Add keyword... (Press Enter)"
        )
        self.kw_add_entry.pack(side="left", fill="x", expand=True)
        self.kw_add_entry.bind("<Return>", lambda e: app._add_keyword_chip())

        self._kw_chip_widgets = []

        self.redundancy_frame = ctk.CTkFrame(inspector, fg_color=C["surface"])
        self.redundancy_frame.pack(fill="x", padx=12, pady=(0, 2))
        self.redundancy_lbl = ctk.CTkLabel(
            self.redundancy_frame,
            text="",
            text_color=C["warn"],
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        )
        self.redundancy_lbl.pack(side="left")
        self.redundancy_btn = _btn(
            self.redundancy_frame,
            "Remove Redundancies",
            C["surface2"],
            C["border"],
            height=22,
            font=ctk.CTkFont(family="Segoe UI", size=9),
            command=app._remove_redundancies,
        )
        self.redundancy_btn.pack(side="right")
        self.redundancy_btn.pack_forget()

        kw_fmt_row = ctk.CTkFrame(inspector, fg_color=C["surface"])
        kw_fmt_row.pack(fill="x", padx=12, pady=(0, 2))
        _btn(
            kw_fmt_row,
            "lowercase all",
            C["surface2"],
            C["border"],
            height=22,
            width=84,
            font=ctk.CTkFont(family="Segoe UI", size=9),
            command=app._lowercase_all_keywords,
        ).pack(side="left", padx=(0, 2))
        _btn(
            kw_fmt_row,
            "Trim Spacing",
            C["surface2"],
            C["border"],
            height=22,
            width=80,
            font=ctk.CTkFont(family="Segoe UI", size=9),
            command=app._trim_all_keywords,
        ).pack(side="left")

        preset_kw_row = ctk.CTkFrame(inspector, fg_color=C["surface"])
        preset_kw_row.pack(fill="x", padx=12, pady=(4, 2))
        _label(
            preset_kw_row,
            "Keyword Presets",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=C["text3"],
        ).pack(side="left")
        _btn(
            preset_kw_row,
            "Manage",
            C["surface2"],
            C["border"],
            height=22,
            width=60,
            font=ctk.CTkFont(family="Segoe UI", size=9),
            command=app._open_keyword_presets,
        ).pack(side="right")

        undo_row = ctk.CTkFrame(inspector, fg_color=C["surface"])
        undo_row.pack(fill="x", padx=12, pady=(2, 0))
        _btn(
            undo_row,
            "↶ Undo",
            C["surface2"],
            C["border"],
            height=24,
            width=70,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=app.undo_metadata,
        ).pack(side="left", padx=(0, 4))
        _btn(
            undo_row,
            "↷ Redo",
            C["surface2"],
            C["border"],
            height=24,
            width=70,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=app.redo_metadata,
        ).pack(side="left")
        _label(
            undo_row,
            "Ctrl+Z / Ctrl+Y",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=C["text3"],
        ).pack(side="right")

        btn_row = ctk.CTkFrame(inspector, fg_color=C["surface"])
        btn_row.pack(fill="x", padx=12, pady=(4, 4))
        _btn(
            btn_row,
            "Dedup",
            C["surface2"],
            C["border"],
            height=28,
            width=80,
            command=app._dedup_keywords,
            font=ctk.CTkFont(family="Segoe UI", size=11),
        ).pack(side="left", padx=(0, 4))
        _btn(
            btn_row,
            "Batch Replace",
            C["warn"],
            C["warn_h"],
            height=28,
            width=100,
            command=app.open_batch_replace,
            font=ctk.CTkFont(family="Segoe UI", size=11),
        ).pack(side="left", padx=(0, 4))
        _btn(
            btn_row,
            "Save & Embed",
            C["success"],
            C["success_h"],
            height=28,
            command=app.save_manual,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        ).pack(side="right", expand=True, fill="x")

        btn_row2 = ctk.CTkFrame(inspector, fg_color=C["surface"])
        btn_row2.pack(fill="x", padx=12, pady=(0, 12))
        _btn(
            btn_row2,
            "Apply to Batch...",
            C["violet"],
            C["violet_h"],
            height=28,
            command=app._open_batch_apply,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        ).pack(fill="x")

    def register_mirrors(self, app):
        app.preview_lbl = self.preview_lbl
        app.status_badge = self.status_badge
        app.variant_badge = self.variant_badge
        app.edit_frame = self._scroll
        app.edit_title_var = self.edit_title_var
        app.edit_desc_var = self.edit_desc_var
        app.edit_kws_var = self.edit_kws_var
        app.target_plat_var = self.target_plat_var
        app.target_plat_cb = self.target_plat_cb
        app.autofix_btn = self.autofix_btn
        app.compliance_lbl = self.compliance_lbl
        app.quality_score_lbl = self.quality_score_lbl
        app.quality_bar = self.quality_bar
        app.quality_issues_lbl = self.quality_issues_lbl
        app.sync_companions = self.sync_companions
        app._title_entry = self._title_entry
        app._desc_entry = self._desc_entry
        app.kw_counter_lbl = self.kw_counter_lbl
        app.kw_chips_frame = self.kw_chips_frame
        app.kw_add_frame = self.kw_add_frame
        app.kw_add_entry = self.kw_add_entry
        app._kw_chip_widgets = self._kw_chip_widgets
        app.redundancy_frame = self.redundancy_frame
        app.redundancy_lbl = self.redundancy_lbl
        app.redundancy_btn = self.redundancy_btn

    def _bind_traces(self, app):
        self.edit_kws_var.trace_add(
            "write", lambda *_: app._trigger_render_keyword_chips()
        )
        self.edit_title_var.trace_add("write", lambda *_: app._update_compliance())
        self.edit_kws_var.trace_add(
            "write",
            lambda *_: [
                app._update_kw_counter(),
                app._update_compliance(),
                app._update_quality_score(),
            ],
        )
        self.edit_title_var.trace_add("write", lambda *_: app._update_quality_score())
        self.edit_desc_var.trace_add("write", lambda *_: app._update_quality_score())