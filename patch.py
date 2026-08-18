import os

with open('apps/desktop/src/main.py', 'r', encoding='utf-8', newline='') as f:
    content = f.read()

if '\r\n' in content:
    nl = '\r\n'
else:
    nl = '\n'

old1 = f'        self.current_edit_hash = None{nl}{nl}        self.log_buffer = []'
new1 = f'        self.current_edit_hash = None{nl}{nl}        self.undo_stack = []{nl}        self.redo_stack = []{nl}        self._is_undoing = False{nl}{nl}        self.log_buffer = []'
content = content.replace(old1, new1, 1)

old2 = f'        threading.Thread(target=self._watcher_loop, daemon=True).start(){nl}{nl}    # ── UI Construction'
new2 = f'''        threading.Thread(target=self._watcher_loop, daemon=True).start(){nl}{nl}        self.bind("<Control-z>", lambda e: self.undo_metadata()){nl}        self.bind("<Control-y>", lambda e: self.redo_metadata()){nl}{nl}    # ── History & Undo ───────────────────────────────────────────────────{nl}    def _save_snapshot(self):{nl}        if self._is_undoing: return{nl}        self.redo_stack.clear(){nl}        state = {{{nl}            "title": self.edit_title_var.get(),{nl}            "desc": self.edit_desc_var.get(),{nl}            "kws": self.edit_kws_var.get(){nl}        }}{nl}        if not self.undo_stack or self.undo_stack[-1] != state:{nl}            self.undo_stack.append(state){nl}            if len(self.undo_stack) > 50:{nl}                self.undo_stack.pop(0){nl}{nl}    def _restore_snapshot(self, state):{nl}        self._is_undoing = True{nl}        self.edit_title_var.set(state.get("title", "")){nl}        self.edit_desc_var.set(state.get("desc", "")){nl}        self.edit_kws_var.set(state.get("kws", "")){nl}        self._is_undoing = False{nl}        self._update_kw_counter(){nl}        self._update_compliance(){nl}{nl}    def undo_metadata(self):{nl}        if not self.undo_stack: return{nl}        current_state = {{{nl}            "title": self.edit_title_var.get(),{nl}            "desc": self.edit_desc_var.get(),{nl}            "kws": self.edit_kws_var.get(){nl}        }}{nl}        if not self.redo_stack or self.redo_stack[-1] != current_state:{nl}            self.redo_stack.append(current_state){nl}        state = self.undo_stack.pop(){nl}        if state == current_state and self.undo_stack:{nl}            state = self.undo_stack.pop(){nl}        self._restore_snapshot(state){nl}{nl}    def redo_metadata(self):{nl}        if not self.redo_stack: return{nl}        current_state = {{{nl}            "title": self.edit_title_var.get(),{nl}            "desc": self.edit_desc_var.get(),{nl}            "kws": self.edit_kws_var.get(){nl}        }}{nl}        self.undo_stack.append(current_state){nl}        state = self.redo_stack.pop(){nl}        self._restore_snapshot(state){nl}{nl}    # ── UI Construction'''
content = content.replace(old2, new2, 1)

old3 = f'        _label(inspector, "Title").pack(fill="x", padx=12, pady=(2, 0)){nl}        _entry(inspector, text_var=self.edit_title_var, placeholder_text="Title").pack(fill="x", padx=12, pady=2){nl}{nl}        _label(inspector, "Description")'
new3 = f'''        _label(inspector, "Title").pack(fill="x", padx=12, pady=(2, 0)){nl}        self._title_entry = _entry(inspector, text_var=self.edit_title_var, placeholder_text="Title"){nl}        self._title_entry.pack(fill="x", padx=12, pady=2){nl}        self._title_entry.bind("<FocusIn>", lambda e: self._save_snapshot()){nl}{nl}        # Title Case Formatter buttons{nl}        title_fmt_row = ctk.CTkFrame(inspector, fg_color="transparent"){nl}        title_fmt_row.pack(fill="x", padx=12, pady=(0, 2)){nl}        _sm_font = ctk.CTkFont(family="Segoe UI", size=9){nl}        _btn(title_fmt_row, "Title Case", C["surface2"], C["border"],{nl}             height=22, width=68, font=_sm_font,{nl}             command=lambda: [self._save_snapshot(), self.edit_title_var.set(to_title_case(self.edit_title_var.get()))]).pack(side="left", padx=(0, 2)){nl}        _btn(title_fmt_row, "Sentence", C["surface2"], C["border"],{nl}             height=22, width=62, font=_sm_font,{nl}             command=lambda: [self._save_snapshot(), self.edit_title_var.set(to_sentence_case(self.edit_title_var.get()))]).pack(side="left", padx=(0, 2)){nl}        _btn(title_fmt_row, "UPPER", C["surface2"], C["border"],{nl}             height=22, width=48, font=_sm_font,{nl}             command=lambda: [self._save_snapshot(), self.edit_title_var.set(to_uppercase(self.edit_title_var.get()))]).pack(side="left", padx=(0, 2)){nl}        _btn(title_fmt_row, "lower", C["surface2"], C["border"],{nl}             height=22, width=42, font=_sm_font,{nl}             command=lambda: [self._save_snapshot(), self.edit_title_var.set(to_lowercase(self.edit_title_var.get()))]).pack(side="left"){nl}{nl}        _label(inspector, "Description")'''
content = content.replace(old3, new3, 1)

old4 = f'        _label(inspector, "Description").pack(fill="x", padx=12, pady=(4, 0)){nl}        _entry(inspector, text_var=self.edit_desc_var, placeholder_text="Description").pack(fill="x", padx=12, pady=2)'
new4 = f'        _label(inspector, "Description").pack(fill="x", padx=12, pady=(4, 0)){nl}        self._desc_entry = _entry(inspector, text_var=self.edit_desc_var, placeholder_text="Description"){nl}        self._desc_entry.pack(fill="x", padx=12, pady=2){nl}        self._desc_entry.bind("<FocusIn>", lambda e: self._save_snapshot())'
content = content.replace(old4, new4, 1)

old5 = f'        _entry(inspector, text_var=self.edit_kws_var,{nl}               placeholder_text="Keywords (comma separated)").pack(fill="x", padx=12, pady=2){nl}        self.edit_title_var.trace_add'
new5 = f'''        self._kws_entry = _entry(inspector, text_var=self.edit_kws_var,{nl}               placeholder_text="Keywords (comma separated)"){nl}        self._kws_entry.pack(fill="x", padx=12, pady=2){nl}        self._kws_entry.bind("<FocusIn>", lambda e: self._save_snapshot()){nl}{nl}        # Keyword cleanup buttons{nl}        kw_fmt_row = ctk.CTkFrame(inspector, fg_color="transparent"){nl}        kw_fmt_row.pack(fill="x", padx=12, pady=(0, 2)){nl}        _btn(kw_fmt_row, "lowercase all", C["surface2"], C["border"],{nl}             height=22, width=84, font=ctk.CTkFont(family="Segoe UI", size=9),{nl}             command=self._lowercase_all_keywords).pack(side="left", padx=(0, 2)){nl}        _btn(kw_fmt_row, "Trim Spacing", C["surface2"], C["border"],{nl}             height=22, width=80, font=ctk.CTkFont(family="Segoe UI", size=9),{nl}             command=self._trim_all_keywords).pack(side="left"){nl}{nl}        self.edit_title_var.trace_add'''
content = content.replace(old5, new5, 1)

old6 = f'        btn_row = ctk.CTkFrame(inspector, fg_color="transparent"){nl}        btn_row.pack(fill="x", padx=12, pady=(4, 12))'
new6 = f'''        # Undo / Redo toolbar{nl}        undo_row = ctk.CTkFrame(inspector, fg_color="transparent"){nl}        undo_row.pack(fill="x", padx=12, pady=(2, 0)){nl}        _btn(undo_row, "\u21b6 Undo", C["surface2"], C["border"],{nl}             height=24, width=70, font=ctk.CTkFont(family="Segoe UI", size=10),{nl}             command=self.undo_metadata).pack(side="left", padx=(0, 4)){nl}        _btn(undo_row, "\u21b7 Redo", C["surface2"], C["border"],{nl}             height=24, width=70, font=ctk.CTkFont(family="Segoe UI", size=10),{nl}             command=self.redo_metadata).pack(side="left"){nl}        _label(undo_row, "Ctrl+Z / Ctrl+Y",{nl}               font=ctk.CTkFont(family="Segoe UI", size=9), text_color=C["text3"]).pack(side="right"){nl}{nl}        btn_row = ctk.CTkFrame(inspector, fg_color="transparent"){nl}        btn_row.pack(fill="x", padx=12, pady=(4, 12))'''
content = content.replace(old6, new6, 1)

old7 = f'    def _dedup_keywords(self):{nl}        raw = [k.strip() for k in self.edit_kws_var.get().split(",") if k.strip()]'
new7 = f'    def _dedup_keywords(self):{nl}        self._save_snapshot(){nl}        raw = [k.strip() for k in self.edit_kws_var.get().split(",") if k.strip()]'
content = content.replace(old7, new7, 1)

old8 = f'    def save_manual(self):'
new8 = f'''    def _lowercase_all_keywords(self):{nl}        self._save_snapshot(){nl}        raw = [k.strip() for k in self.edit_kws_var.get().split(",") if k.strip()]{nl}        self.edit_kws_var.set(", ".join(lowercase_keywords(raw))){nl}{nl}    def _trim_all_keywords(self):{nl}        self._save_snapshot(){nl}        raw = [k for k in self.edit_kws_var.get().split(",")]{nl}        self.edit_kws_var.set(", ".join(trim_keywords(raw))){nl}{nl}    def save_manual(self):'''
content = content.replace(old8, new8, 1)

old9 = f'    def save_manual(self):{nl}        if not self.current_edit_file or not os.path.exists(self.current_edit_file): return{nl}        title = self.edit_title_var.get()'
new9 = f'    def save_manual(self):{nl}        if not self.current_edit_file or not os.path.exists(self.current_edit_file): return{nl}        self._save_snapshot(){nl}        title = self.edit_title_var.get()'
content = content.replace(old9, new9, 1)

old10 = f'    def _autofix_metadata(self):{nl}        title = self.edit_title_var.get()'
new10 = f'    def _autofix_metadata(self):{nl}        self._save_snapshot(){nl}        title = self.edit_title_var.get()'
content = content.replace(old10, new10, 1)

old11 = f'            # also update UI if current file is active{nl}            if self.current_edit_hash:{nl}                m = get_cached_metadata(self.current_edit_hash){nl}                if m:{nl}                    self.edit_title_var.set'
new11 = f'            # also update UI if current file is active{nl}            if self.current_edit_hash:{nl}                m = get_cached_metadata(self.current_edit_hash){nl}                if m:{nl}                    self._save_snapshot(){nl}                    self.edit_title_var.set'
content = content.replace(old11, new11, 1)

old12 = f'                self.current_edit_file = out_path{nl}                self.current_edit_hash = file_hash'
new12 = f'                self.current_edit_file = out_path{nl}                self.current_edit_hash = file_hash{nl}                self.undo_stack.clear(){nl}                self.redo_stack.clear()'
content = content.replace(old12, new12, 1)

with open('apps/desktop/src/main.py', 'w', encoding='utf-8', newline='') as f:
    f.write(content)
print('Done')
