import sys, os
os.chdir(os.path.join(os.environ['USERPROFILE'], 'Saved Games', 'NRA-Metadata'))

with open('apps/desktop/src/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

OLD = '''    def _update_kw_counter(self):
        raw = self.edit_kws_var.get()
        count = len([k for k in raw.split(",") if k.strip()])
        min_kw = self._safe_int(self.min_kw_entry.get(), 10)
        max_kw = self._safe_int(self.max_kw_entry.get(), 49)
        if min_kw <= count <= max_kw:
            color = C["success"]
        elif count < min_kw:
            color = C["warn"]
        else:
            color = C["error"]
        self.kw_counter_lbl.configure(text=f"Keywords ({count} / {max_kw})", text_color=color)

    def _dedup_keywords(self):'''

NEW = '''    def _update_kw_counter(self):
        raw = self.edit_kws_var.get()
        count = len([k for k in raw.split(",") if k.strip()])
        min_kw = self._safe_int(self.min_kw_entry.get(), 10)
        max_kw = self._safe_int(self.max_kw_entry.get(), 49)
        if min_kw <= count <= max_kw:
            color = C["success"]
        elif count < min_kw:
            color = C["warn"]
        else:
            color = C["error"]
        self.kw_counter_lbl.configure(text=f"Keywords ({count} / {max_kw})", text_color=color)
        self._check_redundancies()

    def _check_redundancies(self):
        kws = [k.strip() for k in self.edit_kws_var.get().split(",") if k.strip()]
        redundancies = detect_redundant_keywords(kws)
        if redundancies:
            total_dup = sum(len(v) for v in redundancies.values())
            self.redundancy_lbl.configure(text=f"\u26A0 {total_dup} similar keywords detected!")
            self.redundancy_btn.pack(side="right")
        else:
            self.redundancy_lbl.configure(text="")
            self.redundancy_btn.pack_forget()

    def _remove_redundancies(self):
        self._save_snapshot()
        kws = [k.strip() for k in self.edit_kws_var.get().split(",") if k.strip()]
        cleaned = remove_redundant_keywords(kws)
        self.edit_kws_var.set(", ".join(cleaned))

    def _get_kws_list(self):
        return [k.strip() for k in self.edit_kws_var.get().split(",") if k.strip()]

    def _set_kws_list(self, kws):
        self.edit_kws_var.set(", ".join([k.strip() for k in kws if k.strip()]))

    def _add_keyword_chip(self):
        new_kw = self.kw_add_entry.get().strip()
        if not new_kw: return
        self._save_snapshot()
        kws = self._get_kws_list()
        # prevent exact duplicates locally
        if new_kw.lower() not in [k.lower() for k in kws]:
            kws.append(new_kw)
            self._set_kws_list(kws)
        self.kw_add_entry.delete(0, "end")

    def _remove_keyword_chip(self, idx):
        self._save_snapshot()
        kws = self._get_kws_list()
        if 0 <= idx < len(kws):
            kws.pop(idx)
            self._set_kws_list(kws)

    def _move_keyword_chip(self, idx, direction):
        kws = self._get_kws_list()
        if direction == "up" and idx > 0:
            self._save_snapshot()
            kws[idx], kws[idx-1] = kws[idx-1], kws[idx]
            self._set_kws_list(kws)
        elif direction == "down" and idx < len(kws) - 1:
            self._save_snapshot()
            kws[idx], kws[idx+1] = kws[idx+1], kws[idx]
            self._set_kws_list(kws)

    # Re-entry guard to prevent infinite update loop
    _rendering_chips = False
    def _render_keyword_chips(self):
        if self._rendering_chips: return
        self._rendering_chips = True
        
        for widget in self._kw_chip_widgets:
            widget.destroy()
        self._kw_chip_widgets.clear()
        
        kws = self._get_kws_list()
        
        # Grid layout for chips
        row, col = 0, 0
        for i, kw in enumerate(kws):
            chip = ctk.CTkFrame(self.kw_chips_frame, fg_color=C["surface"], corner_radius=CR)
            chip.grid(row=row, column=col, padx=2, pady=2, sticky="w")
            self._kw_chip_widgets.append(chip)
            
            # Left arrow
            if i > 0:
                l_btn = ctk.CTkButton(chip, text="◀", width=16, height=20, fg_color="transparent",
                                      text_color=C["text3"], hover_color=C["surface2"],
                                      font=ctk.CTkFont(size=10),
                                      command=lambda idx=i: self._move_keyword_chip(idx, "up"))
                l_btn.pack(side="left", padx=(2,0))

            lbl = ctk.CTkLabel(chip, text=kw, font=ctk.CTkFont(family="Segoe UI", size=11), text_color=C["text"])
            lbl.pack(side="left", padx=4, pady=2)
            
            # Right arrow
            if i < len(kws) - 1:
                r_btn = ctk.CTkButton(chip, text="▶", width=16, height=20, fg_color="transparent",
                                      text_color=C["text3"], hover_color=C["surface2"],
                                      font=ctk.CTkFont(size=10),
                                      command=lambda idx=i: self._move_keyword_chip(idx, "down"))
                r_btn.pack(side="left", padx=(0,0))

            x_btn = ctk.CTkButton(chip, text="×", width=20, height=20, fg_color="transparent",
                                  text_color=C["error"], hover_color=C["surface2"],
                                  command=lambda idx=i: self._remove_keyword_chip(idx))
            x_btn.pack(side="right", padx=(0, 2))
            
            col += 1
            if col > 1: # 2 columns max
                col = 0
                row += 1

        self._rendering_chips = False

    def _dedup_keywords(self):'''

content_norm = content.replace('\r\n', '\n')
OLD_norm = OLD.replace('\r\n', '\n')
NEW_norm = NEW.replace('\r\n', '\n')

if OLD_norm in content_norm:
    content_norm = content_norm.replace(OLD_norm, NEW_norm, 1)
    if '\r\n' in content:
        content_norm = content_norm.replace('\n', '\r\n')
    with open('apps/desktop/src/main.py', 'w', encoding='utf-8', newline='') as f:
        f.write(content_norm)
    print('OK: Inserted methods')
else:
    print('ERROR: old string not found')
    idx = content_norm.find('def _dedup_keywords(self):')
    if idx >= 0:
        print(f'Found at position {idx}')
        print(repr(content_norm[idx-150:idx+50]))
