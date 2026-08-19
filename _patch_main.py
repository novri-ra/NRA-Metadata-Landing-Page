import os

fp = os.path.join("apps", "desktop", "src", "main.py")
with open(fp, "r", encoding="utf-8") as f:
    c = f.read()

# 1. Filter excluded files in start_processing
old = """        files = [f for f in os.listdir(in_dir) if os.path.isfile(os.path.join(in_dir, f)) and self._is_allowed_file(f)]
        if new_only:
            files = [f for f in files if f not in self.processed_files]

        if not files: return self.log("No new files." if new_only else "No files.", "error")
        self.processed_files.update(files)

        self.is_running = True
        self.cancel_flag = False"""

new = """        all_files = [f for f in os.listdir(in_dir) if os.path.isfile(os.path.join(in_dir, f)) and self._is_allowed_file(f)]
        files = [f for f in all_files if f not in self.excluded_files]
        skipped_count = len(all_files) - len(files)

        if skipped_count:
            self.log(f"Skipping {skipped_count} excluded file(s)", "info")

        if new_only:
            files = [f for f in files if f not in self.processed_files]

        if not files: return self.log("No new files." if new_only else "No files.", "error")
        self.processed_files.update(files)

        self.is_running = True
        self.batch_session_stats = {"processed": 0, "skipped": skipped_count, "cost": tracker.estimated_cost_usd, "tokens_est": 0, "csvs": []}
        self.cancel_flag = False"""

assert old in c, "old text not found for start_processing patch"
c = c.replace(old, new)

# 2. Modify _run_batch to collect stats and show summary
old2 = """        if self.cancel_flag:
            self.log("Batch CANCELED.", "error")
        else:
            self.log("Batch complete. Generating exports...", "info")
            generate_microstock_csvs(out_dir, self._get_selected_csv_platforms())

        self.is_running = False
        self.after(0, lambda: self.start_btn.configure(state="normal"))
        self.after(0, lambda: self.pause_btn.configure(state="disabled"))
        self.after(0, lambda: self.cancel_btn.configure(state="disabled"))
        self.after(0, lambda: self.header_status.configure(text="Ready", text_color=C["text3"]))"""

new2 = """        if self.cancel_flag:
            self.log("Batch CANCELED.", "error")
        else:
            self.log("Batch complete. Generating exports...", "info")
            generate_microstock_csvs(out_dir, self._get_selected_csv_platforms())

            # Collect generated CSV list
            csv_files = [f for f in os.listdir(out_dir) if f.endswith("_export.csv") or f == "metadata_output.csv"]
            cost_delta = tracker.estimated_cost_usd - self.batch_session_stats["cost"]
            self.batch_session_stats.update({
                "processed": self.stats["success"],
                "errors": self.stats["error"],
                "cost": cost_delta,
                "tokens_est": int(cost_delta / 0.002 * 1000) if cost_delta > 0 else 0,
                "csvs": csv_files,
                "out_dir": out_dir,
            })
            self.after(0, lambda: self._show_batch_summary())

        self.is_running = False
        self.after(0, lambda: self.start_btn.configure(state="normal"))
        self.after(0, lambda: self.pause_btn.configure(state="disabled"))
        self.after(0, lambda: self.cancel_btn.configure(state="disabled"))
        self.after(0, lambda: self.header_status.configure(text="Ready", text_color=C["text3"]))
        self.after(0, lambda: self._refresh_file_queue())"""

assert old2 in c, "old text not found for _run_batch patch"
c = c.replace(old2, new2)

# 3. Add _show_batch_summary method before the final "if __name__" block
summary_method = '''
    def _show_batch_summary(self):
        """Show batch processing summary dialog."""
        s = self.batch_session_stats
        dialog = ctk.CTkToplevel(self)
        dialog.title("Processing Summary Report")
        dialog.geometry("480x420")
        dialog.configure(fg_color=C["bg"])
        dialog.transient(self)
        dialog.grab_set()

        # Header
        ctk.CTkLabel(dialog, text="\\u2714  Batch Processing Complete",
                     font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
                     text_color=C["success"]).pack(padx=20, pady=(20, 4), anchor="w")

        _divider(dialog).pack(fill="x", padx=20, pady=8)

        # Stats grid
        stats_frame = ctk.CTkFrame(dialog, fg_color=C["surface"], corner_radius=CR)
        stats_frame.pack(fill="x", padx=20, pady=(0, 8))

        rows = [
            ("Files Processed", str(s.get("processed", 0)), C["success"]),
            ("Files Skipped (Excluded)", str(s.get("skipped", 0)), C["text3"]),
            ("Errors", str(s.get("errors", 0)), C["error"]),
            ("Estimated Tokens Used", f"~{s.get('tokens_est', 0):,}", C["warn"]),
            ("Estimated API Cost", f"${s.get('cost', 0):.4f}", C["warn"]),
        ]

        for i, (label, value, color) in enumerate(rows):
            r = ctk.CTkFrame(stats_frame, fg_color="transparent")
            r.pack(fill="x", padx=12, pady=3)
            ctk.CTkLabel(r, text=label, font=ctk.CTkFont(family="Segoe UI", size=12),
                         text_color=C["text2"]).pack(side="left")
            ctk.CTkLabel(r, text=value, font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                         text_color=color).pack(side="right")

        # CSV files generated
        csvs = s.get("csvs", [])
        if csvs:
            ctk.CTkLabel(dialog, text="Generated CSV Exports:",
                         font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                         text_color=C["text3"]).pack(padx=20, pady=(8, 2), anchor="w")

            csv_frame = ctk.CTkFrame(dialog, fg_color=C["surface"], corner_radius=CR)
            csv_frame.pack(fill="x", padx=20, pady=(0, 8))
            for csv_f in csvs:
                ctk.CTkLabel(csv_frame, text=f"  \\u2022  {csv_f}",
                             font=ctk.CTkFont(family="Segoe UI", size=11),
                             text_color=C["accent"]).pack(anchor="w", padx=8, pady=1)

        _divider(dialog).pack(fill="x", padx=20, pady=4)

        # Action buttons
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(4, 16))

        def open_folder():
            out = s.get("out_dir", "")
            if out and os.path.isdir(out):
                os.startfile(out)

        def copy_summary():
            lines = [
                "=== NRA Metadata - Batch Processing Summary ===",
                f"Files Processed: {s.get('processed', 0)}",
                f"Files Skipped: {s.get('skipped', 0)}",
                f"Errors: {s.get('errors', 0)}",
                f"Estimated Tokens: ~{s.get('tokens_est', 0):,}",
                f"Estimated Cost: ${s.get('cost', 0):.4f}",
                f"CSV Exports: {', '.join(csvs)}",
            ]
            self.clipboard_clear()
            self.clipboard_append("\\n".join(lines))
            self.log("Summary copied to clipboard.", "info")

        _btn(btn_frame, "Open Output Folder", C["accent"], C["accent_h"],
             command=open_folder, height=32).pack(side="left", expand=True, fill="x", padx=(0, 4))
        _btn(btn_frame, "Copy Summary to Clipboard", C["violet"], C["violet_h"],
             command=copy_summary, height=32).pack(side="left", expand=True, fill="x", padx=(4, 0))

        _btn(btn_frame, "Close", C["surface2"], C["border"],
             command=dialog.destroy, height=32, width=60).pack(side="right", padx=(8, 0))

'''

assert 'if __name__ == "__main__":' in c, "if __name__ not found"
c = c.replace('if __name__ == "__main__":', summary_method + 'if __name__ == "__main__":')

with open(fp, "w", encoding="utf-8") as f:
    f.write(c)

print("OK: all patches applied")
