import sys, os
os.chdir(os.path.join(os.environ['USERPROFILE'], 'Saved Games', 'NRA-Metadata'))

with open('apps/desktop/src/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

OLD = '''        self.kw_counter_lbl = _label(inspector, "Keywords (0 / 20)", text_color=C["success"])
        self.kw_counter_lbl.pack(fill="x", padx=12, pady=(4, 0))
        self._kws_entry = _entry(inspector, text_var=self.edit_kws_var,
               placeholder_text="Keywords (comma separated)")
        self._kws_entry.pack(fill="x", padx=12, pady=2)
        self._kws_entry.bind("<FocusIn>", lambda e: self._save_snapshot())

        # Keyword cleanup buttons'''

NEW = '''        self.kw_counter_lbl = _label(inspector, "Keywords (0 / 20)", text_color=C["success"])
        self.kw_counter_lbl.pack(fill="x", padx=12, pady=(4, 0))

        # \u2500\u2500 Keyword Chips Area \u2500\u2500
        self.kw_chips_frame = ctk.CTkScrollableFrame(inspector, fg_color=C["surface2"], corner_radius=CR, height=120)
        self.kw_chips_frame.pack(fill="x", padx=12, pady=2)

        self.kw_add_frame = ctk.CTkFrame(inspector, fg_color="transparent")
        self.kw_add_frame.pack(fill="x", padx=12, pady=(0, 4))
        self.kw_add_entry = _entry(self.kw_add_frame, placeholder_text="Add keyword... (Press Enter)")
        self.kw_add_entry.pack(side="left", fill="x", expand=True)
        self.kw_add_entry.bind("<Return>", lambda e: self._add_keyword_chip())

        # Sync chip frame with edit_kws_var
        self.edit_kws_var.trace_add("write", lambda *_: self._render_keyword_chips())
        self._kw_chip_widgets = []

        # Redundancy detector UI
        self.redundancy_frame = ctk.CTkFrame(inspector, fg_color="transparent")
        self.redundancy_frame.pack(fill="x", padx=12, pady=(0, 2))
        self.redundancy_lbl = ctk.CTkLabel(self.redundancy_frame, text="", text_color=C["warn"],
                                           font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"))
        self.redundancy_lbl.pack(side="left")
        self.redundancy_btn = _btn(self.redundancy_frame, "Remove Redundancies", C["surface2"], C["border"],
                                   height=22, font=ctk.CTkFont(family="Segoe UI", size=9),
                                   command=self._remove_redundancies)
        self.redundancy_btn.pack(side="right")
        self.redundancy_btn.pack_forget()

        # Keyword cleanup buttons'''

# Normalize line endings for comparison
content_norm = content.replace('\r\n', '\n')
OLD_norm = OLD.replace('\r\n', '\n')
NEW_norm = NEW.replace('\r\n', '\n')

if OLD_norm in content_norm:
    content_norm = content_norm.replace(OLD_norm, NEW_norm, 1)
    # Restore original line endings
    if '\r\n' in content:
        content_norm = content_norm.replace('\n', '\r\n')
    with open('apps/desktop/src/main.py', 'w', encoding='utf-8', newline='') as f:
        f.write(content_norm)
    print('OK: Replaced keyword entry with chips UI')
else:
    print('ERROR: old string not found')
    # Debug: find closest match
    idx = content_norm.find('self._kws_entry')
    if idx >= 0:
        print(f'Found _kws_entry at position {idx}')
        print(repr(content_norm[idx-50:idx+200]))
    else:
        print('_kws_entry not found anywhere!')
