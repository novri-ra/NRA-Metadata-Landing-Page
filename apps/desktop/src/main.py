import os
import shutil
import threading
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import customtkinter as ctk

from packages.media_processor.embedder import MediaProcessor
from packages.media_processor.previews import extract_preview_image
from packages.ai_engine.service import AIService
from packages.shared_utils.config import load_config, save_config
from packages.shared_utils.logger import CSVLogger
from packages.shared_utils.cache import get_file_hash, get_cached_metadata, set_cached_metadata
from packages.shared_utils.filter import clean_metadata, sanitize_keywords
from packages.shared_utils.csv_exporter import generate_microstock_csvs
from packages.shared_utils.tracker import tracker
from packages.shared_utils.cache import get_cache_hits
from packages.shared_utils.ftp_uploader import FTPClient

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

def make_frame(parent, **kwargs):
    kwargs.setdefault("fg_color", "#1e293b")
    kwargs.setdefault("corner_radius", 12)
    return ctk.CTkFrame(parent, **kwargs)

def make_label(parent, text, **kwargs):
    kwargs.setdefault("font", ctk.CTkFont(size=13, weight="bold"))
    kwargs.setdefault("text_color", "#cbd5e1")
    return ctk.CTkLabel(parent, text=text, **kwargs)

def make_entry(parent, text_var=None, **kwargs):
    return ctk.CTkEntry(parent, textvariable=text_var, fg_color="#0f172a", border_color="#334155", corner_radius=8, **kwargs)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Auto Metadata")
        self.geometry("1100x650")
        self.minsize(1000, 650)
        self.configure(fg_color="#0f172a")

        self.input_dir = ctk.StringVar()
        self.output_dir = ctk.StringVar()
        
        self.config = load_config()
        self.processor = MediaProcessor()
        self.stats = {"total": 0, "success": 0, "error": 0}
        self.current_preview_img = None
        self.processed_files = set()
        self.is_running = False
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.cancel_flag = False
        
        self.current_edit_file = None
        self.current_edit_hash = None

        self.build_ui()
        threading.Thread(target=self._watcher_loop, daemon=True).start()

    def build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar (scrollable for small screens)
        sidebar = ctk.CTkScrollableFrame(self, fg_color="#1e293b", corner_radius=12, width=220)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        sidebar.grid_columnconfigure(0, weight=1)

        r = 0
        make_label(sidebar, "Settings", font=ctk.CTkFont(size=18, weight="bold"), text_color="white").grid(row=r, column=0, pady=(5,10)); r += 1

        make_label(sidebar, "Provider:").grid(row=r, column=0, sticky="w", padx=10, pady=2); r += 1
        self.provider_cb = ctk.CTkComboBox(sidebar, values=["Gemini", "OpenAI", "Mistral"], fg_color="#0f172a", border_color="#334155", button_color="#3b82f6")
        self.provider_cb.set(self.config.get("provider", "Gemini"))
        self.provider_cb.grid(row=r, column=0, sticky="ew", padx=10, pady=(0, 5)); r += 1

        make_label(sidebar, "Asset Style:").grid(row=r, column=0, sticky="w", padx=10, pady=2); r += 1
        self.style_cb = ctk.CTkComboBox(sidebar, values=["General Commercial", "Icons & Clipart", "Backgrounds & Patterns", "Characters & Mascot"], fg_color="#0f172a", border_color="#334155", button_color="#3b82f6")
        self.style_cb.set(self.config.get("style_preset", "General Commercial"))
        self.style_cb.grid(row=r, column=0, sticky="ew", padx=10, pady=(0, 5)); r += 1

        make_label(sidebar, "API Key:").grid(row=r, column=0, sticky="w", padx=10, pady=2); r += 1
        self.api_key_entry = make_entry(sidebar, show="*")
        self.api_key_entry.insert(0, self.config.get("api_key", ""))
        self.api_key_entry.grid(row=r, column=0, sticky="ew", padx=10, pady=(0, 5)); r += 1

        make_label(sidebar, "Min KW:").grid(row=r, column=0, sticky="w", padx=10, pady=2); r += 1
        self.min_kw_entry = make_entry(sidebar)
        self.min_kw_entry.insert(0, str(self.config.get("min_kw", 5)))
        self.min_kw_entry.grid(row=r, column=0, sticky="ew", padx=10, pady=(0, 5)); r += 1

        make_label(sidebar, "Max KW:").grid(row=r, column=0, sticky="w", padx=10, pady=2); r += 1
        self.max_kw_entry = make_entry(sidebar)
        self.max_kw_entry.insert(0, str(self.config.get("max_kw", 20)))
        self.max_kw_entry.grid(row=r, column=0, sticky="ew", padx=10, pady=(0, 5)); r += 1

        make_label(sidebar, "Workers:").grid(row=r, column=0, sticky="w", padx=10, pady=2); r += 1
        self.workers_val = ctk.StringVar(value=str(self.config.get("workers", 2)))
        def update_worker_lbl(val): self.workers_val.set(str(int(val)))
        self.workers_slider = ctk.CTkSlider(sidebar, from_=1, to=8, number_of_steps=7, command=update_worker_lbl, progress_color="#3b82f6")
        self.workers_slider.set(self.config.get("workers", 2))
        self.workers_slider.grid(row=r, column=0, sticky="ew", padx=10, pady=0); r += 1
        ctk.CTkLabel(sidebar, textvariable=self.workers_val).grid(row=r, column=0, pady=(0, 5)); r += 1

        self.auto_watch = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(sidebar, text="Auto-Watch Input", variable=self.auto_watch, progress_color="#10b981").grid(row=r, column=0, sticky="w", padx=10, pady=3); r += 1

        self.auto_zip = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(sidebar, text="Auto-Zip Vector", variable=self.auto_zip, progress_color="#10b981").grid(row=r, column=0, sticky="w", padx=10, pady=3); r += 1

        # Process Formats
        make_label(sidebar, "Process Formats:").grid(row=r, column=0, sticky="w", padx=10, pady=(3, 2)); r += 1
        fmt_saved = self.config.get("formats", {})
        self.fmt_vars = {}
        fmt_defs = [
            ("SVG", ".svg", True),  ("EPS", ".eps", True),  ("AI", ".ai", False),
            ("JPG", ".jpg", True),  ("PNG", ".png", True),
            ("MP4", ".mp4", False), ("MOV", ".mov", False),
        ]
        fmt_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        fmt_frame.grid(row=r, column=0, sticky="ew", padx=10, pady=(0, 5)); r += 1
        for i, (label, ext, default) in enumerate(fmt_defs):
            var = ctk.BooleanVar(value=fmt_saved.get(ext, default))
            self.fmt_vars[ext] = var
            ctk.CTkCheckBox(fmt_frame, text=label, variable=var, width=70, height=22,
                            checkbox_width=18, checkbox_height=18,
                            fg_color="#3b82f6", hover_color="#2563eb",
                            font=ctk.CTkFont(size=12)).grid(row=i // 3, column=i % 3, sticky="w", padx=2, pady=1)

        self.start_btn = ctk.CTkButton(sidebar, text="Start", font=ctk.CTkFont(weight="bold"), fg_color="#3b82f6", hover_color="#2563eb", corner_radius=8, command=self.start_processing)
        self.start_btn.grid(row=r, column=0, sticky="ew", padx=10, pady=(5,2)); r += 1

        ctrl_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        ctrl_frame.grid(row=r, column=0, sticky="ew", padx=10, pady=(0,5)); r += 1
        
        self.pause_btn = ctk.CTkButton(ctrl_frame, text="Pause", width=90, fg_color="#f59e0b", hover_color="#d97706", command=self.toggle_pause)
        self.pause_btn.pack(side="left", padx=(0,5), expand=True, fill="x")
        self.pause_btn.configure(state="disabled")

        self.cancel_btn = ctk.CTkButton(ctrl_frame, text="Cancel", width=90, fg_color="#ef4444", hover_color="#dc2626", command=self.cancel_batch)
        self.cancel_btn.pack(side="right", padx=(5,0), expand=True, fill="x")
        self.cancel_btn.configure(state="disabled")

        self.retag_btn = ctk.CTkButton(sidebar, text="Offline Re-Tag from CSV", font=ctk.CTkFont(weight="bold"), fg_color="#f59e0b", hover_color="#d97706", corner_radius=8, command=self.start_offline_retag)
        self.retag_btn.grid(row=r, column=0, sticky="ew", padx=10, pady=3); r += 1

        self.ftp_btn = ctk.CTkButton(sidebar, text="FTP / SFTP Uploader", font=ctk.CTkFont(weight="bold"), fg_color="#8b5cf6", hover_color="#7c3aed", corner_radius=8, command=self.open_ftp_dialog)
        self.ftp_btn.grid(row=r, column=0, sticky="ew", padx=10, pady=(3, 10)); r += 1

        # Main Panel
        main_panel = make_frame(self, fg_color="#0f172a")
        main_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        main_panel.grid_columnconfigure(0, weight=1)
        main_panel.grid_rowconfigure(3, weight=1)

        # Top area: IO Cards (Left) + Edit (Right)
        top_frame = ctk.CTkFrame(main_panel, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="ew")
        top_frame.grid_columnconfigure(0, weight=1)

        io_frame = make_frame(top_frame)
        io_frame.grid(row=0, column=0, sticky="nsew", padx=(0,10))
        io_frame.grid_columnconfigure(1, weight=1)

        make_label(io_frame, "Folder:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        make_entry(io_frame, self.input_dir).grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(io_frame, text="...", width=40, fg_color="#475569", command=self.browse_input).grid(row=0, column=2, padx=10, pady=10)

        # Edit Frame
        self.edit_frame = make_frame(top_frame, width=280)
        self.edit_frame.grid(row=0, column=1, sticky="nsew")
        
        self.preview_lbl = ctk.CTkLabel(self.edit_frame, text="No Preview", width=160, height=140)
        self.preview_lbl.pack(pady=5)
        
        self.status_badge = ctk.CTkLabel(self.edit_frame, text="", fg_color="transparent", corner_radius=6, padx=6, font=ctk.CTkFont(size=11, weight="bold"))
        self.status_badge.place(relx=0.05, rely=0.05, anchor="nw")

        self.edit_title_var = ctk.StringVar()
        self.edit_desc_var = ctk.StringVar()
        self.edit_kws_var = ctk.StringVar()
        
        make_label(self.edit_frame, "Title:").pack(fill="x", padx=10, pady=(5,0))
        make_entry(self.edit_frame, text_var=self.edit_title_var, placeholder_text="Title").pack(fill="x", padx=10, pady=2)
        make_label(self.edit_frame, "Description:").pack(fill="x", padx=10, pady=(5,0))
        make_entry(self.edit_frame, text_var=self.edit_desc_var, placeholder_text="Description").pack(fill="x", padx=10, pady=2)
        make_label(self.edit_frame, "Keywords:").pack(fill="x", padx=10, pady=(5,0))
        make_entry(self.edit_frame, text_var=self.edit_kws_var, placeholder_text="Keywords (comma separated)").pack(fill="x", padx=10, pady=2)
        ctk.CTkButton(self.edit_frame, text="Save / Re-embed", fg_color="#10b981", hover_color="#059669", height=28, command=self.save_manual).pack(fill="x", padx=10, pady=5)

        self.stats_lbl = make_label(main_panel, "Total: 0 | Success: 0 | Error: 0", text_color="#3b82f6")
        self.stats_lbl.grid(row=1, column=0, sticky="w", pady=(10, 5))
        
        self.cost_lbl = make_label(main_panel, "[Est. Cost: $0.00] [Saved via Cache: 0 calls]", text_color="#10b981")
        self.cost_lbl.grid(row=1, column=0, sticky="e", pady=(10, 5), padx=10)

        self.progress_bar = ctk.CTkProgressBar(main_panel, progress_color="#3b82f6", height=8, corner_radius=4)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=2, column=0, sticky="ew", pady=5)

        self.console = ctk.CTkTextbox(main_panel, fg_color="#1e293b", corner_radius=12, border_width=1, border_color="#334155")
        self.console.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        
        tb = self.console._textbox
        tb.tag_config("success", foreground="#10b981")
        tb.tag_config("processing", foreground="#f59e0b")
        tb.tag_config("error", foreground="#ef4444")
        tb.tag_config("info", foreground="#94a3b8")
        tb.tag_config("cache", foreground="#8b5cf6")
        tb.tag_config("timestamp", foreground="#64748b")
        self.console.configure(state="disabled")

    def log(self, message: str, level="info"):
        def _append():
            self.console.configure(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            tb = self.console._textbox
            tb.insert("end", f"[{ts}] ", "timestamp")
            tb.insert("end", f"[{level.upper()}] ", level)
            tb.insert("end", f"{message}\n", level)
            self.console.see("end")
            self.console.configure(state="disabled")
        self.after(0, _append)

    def update_stats(self, key):
        def _update():
            self.stats[key] += 1
            self.stats_lbl.configure(text=f"Total: {self.stats['total']} | Success: {self.stats['success']} | Error: {self.stats['error']}")
            self.cost_lbl.configure(text=f"[Est. Cost: ${tracker.estimated_cost_usd:.3f}] [Saved via Cache: {get_cache_hits()} calls]")
        self.after(0, _update)

    def update_preview(self, img, status_text: str, status_color: str, meta: dict, out_path: str, file_hash: str):
        def _draw():
            try:
                img.thumbnail((160, 160))
                self.current_preview_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                self.preview_lbl.configure(image=self.current_preview_img, text="")
                self.status_badge.configure(text=status_text, fg_color=status_color)
                
                self.edit_title_var.set(meta.get("title", ""))
                self.edit_desc_var.set(meta.get("description", ""))
                self.edit_kws_var.set(", ".join(meta.get("keywords", [])))
                
                self.current_edit_file = out_path
                self.current_edit_hash = file_hash
            except: pass
        self.after(0, _draw)

    def save_manual(self):
        if not self.current_edit_file or not os.path.exists(self.current_edit_file): return
        title = self.edit_title_var.get()
        desc = self.edit_desc_var.get()
        kws = [k.strip() for k in self.edit_kws_var.get().split(",") if k.strip()]
        
        name = os.path.basename(self.current_edit_file)
        if self.processor.embed_metadata(self.current_edit_file, title, desc, kws, "Copyright Text"):
            meta = {"title": title, "description": desc, "keywords": kws}
            set_cached_metadata(self.current_edit_hash, meta)
            self.log(f"{name} (Manual save OK)", "success")
            
            # update csv in subfolder
            sub_dir = os.path.dirname(self.current_edit_file)
            temp_master = os.path.join(sub_dir, "metadata_output.csv")
            import csv
            with open(temp_master, 'w', newline='', encoding='utf-8') as tf:
                tw = csv.writer(tf)
                tw.writerow(["Filename","Title","Description","Keywords"])
                tw.writerow([name, title, desc, ",".join(kws)])
            generate_microstock_csvs(sub_dir)
            
            # note: updating the root master CSV from manual edit is complex without reading it fully.
            # user should re-run or edit the master directly if they manually edit after the fact.
        else:
            self.log(f"{name} (Manual save fail)", "error")

    def browse_input(self):
        dir_path = ctk.filedialog.askdirectory()
        if dir_path: self.input_dir.set(dir_path)

    def open_ftp_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("FTP / SFTP Uploader")
        dialog.geometry("450x450")
        dialog.transient(self)
        dialog.grab_set()

        make_label(dialog, "Preset:").pack(padx=10, pady=(10, 2), anchor="w")
        preset_cb = ctk.CTkComboBox(dialog, values=["Custom", "Adobe Stock", "Shutterstock", "Vecteezy", "Freepik"])
        preset_cb.pack(padx=10, pady=2, fill="x")

        make_label(dialog, "Host:").pack(padx=10, pady=2, anchor="w")
        host_entry = make_entry(dialog)
        host_entry.insert(0, self.config.get("ftp_host", ""))
        host_entry.pack(padx=10, pady=2, fill="x")

        make_label(dialog, "Port:").pack(padx=10, pady=2, anchor="w")
        port_entry = make_entry(dialog)
        port_entry.insert(0, "21")
        port_entry.pack(padx=10, pady=2, fill="x")

        make_label(dialog, "Username:").pack(padx=10, pady=2, anchor="w")
        user_entry = make_entry(dialog)
        user_entry.insert(0, self.config.get("ftp_user", ""))
        user_entry.pack(padx=10, pady=2, fill="x")

        make_label(dialog, "Password:").pack(padx=10, pady=2, anchor="w")
        pass_entry = make_entry(dialog, show="*")
        pass_entry.pack(padx=10, pady=2, fill="x")

        zip_only = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(dialog, text="Upload .ZIP only", variable=zip_only).pack(padx=10, pady=10, anchor="w")

        status_lbl = ctk.CTkLabel(dialog, text="", text_color="#10b981")
        status_lbl.pack(pady=5)

        def apply_preset(choice):
            hosts = {
                "Adobe Stock": "ftp.contributor.adobestock.com",
                "Shutterstock": "ftp.shutterstock.com",
                "Vecteezy": "ftp.vecteezy.com",
                "Freepik": "ftp.freepik.com"
            }
            if choice in hosts:
                host_entry.delete(0, "end")
                host_entry.insert(0, hosts[choice])
        preset_cb.configure(command=apply_preset)

        def test_conn():
            status_lbl.configure(text="Testing...", text_color="#f59e0b")
            dialog.update()
            h, p = host_entry.get(), int(port_entry.get() or 21)
            u, pw = user_entry.get(), pass_entry.get()
            
            client = FTPClient(h, p, u, pw)
            ok, msg = client.connect()
            if ok:
                status_lbl.configure(text="Connection OK", text_color="#10b981")
                client.disconnect()
            else:
                status_lbl.configure(text=f"Fail: {msg}", text_color="#ef4444")

        def start_upload():
            h, p = host_entry.get(), int(port_entry.get() or 21)
            u, pw = user_entry.get(), pass_entry.get()
            self.config["ftp_host"] = h
            self.config["ftp_user"] = u
            save_config(self.config)
            
            target_dir = self.input_dir.get()
            if not target_dir or not os.path.isdir(target_dir):
                status_lbl.configure(text="No folder selected in main window", text_color="#ef4444")
                return

            dialog.destroy()
            threading.Thread(target=self._run_ftp_upload, args=(h, p, u, pw, target_dir, zip_only.get()), daemon=True).start()

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10, side="bottom")
        ctk.CTkButton(btn_frame, text="Test Connection", fg_color="#475569", command=test_conn).pack(side="left", expand=True, padx=5)
        ctk.CTkButton(btn_frame, text="Start Upload", fg_color="#8b5cf6", command=start_upload).pack(side="right", expand=True, padx=5)

    def _run_ftp_upload(self, host, port, user, passwd, folder, zip_only):
        self.log(f"Connecting to FTP {host}...", "info")
        client = FTPClient(host, port, user, passwd)
        ok, msg = client.connect()
        if not ok:
            return self.log(f"FTP Connect Error: {msg}", "error")

        files_to_upload = []
        valid_exts = (".zip",) if zip_only else (".zip", ".eps", ".jpg", ".svg", ".csv")
        for root, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(valid_exts):
                    files_to_upload.append(os.path.join(root, f))

        if not files_to_upload:
            client.disconnect()
            return self.log("No valid files to upload via FTP.", "error")

        self.log(f"FTP Uploading {len(files_to_upload)} files...", "info")
        self.progress_bar.set(0)
        
        success = 0
        total = len(files_to_upload)
        for i, fpath in enumerate(files_to_upload):
            fname = os.path.basename(fpath)
            self.log(f"FTP: uploading {fname}...", "processing")
            if client.upload_file(fpath):
                self.log(f"FTP: OK {fname}", "success")
                success += 1
            else:
                self.log(f"FTP: FAIL {fname}", "error")
            self.after(0, self.progress_bar.set, (i + 1) / total)

        client.disconnect()
        self.log(f"FTP Upload Complete: {success}/{total} successful.", "info")

    def _get_allowed_extensions(self) -> set:
        exts = {ext for ext, var in self.fmt_vars.items() if var.get()}
        if ".jpg" in exts:
            exts.add(".jpeg")
        return exts

    def _is_allowed_file(self, filename: str) -> bool:
        ext = os.path.splitext(filename)[1].lower()
        return ext in self._get_allowed_extensions()

    def _watcher_loop(self):
        while True:
            time.sleep(3)
            if self.auto_watch.get() and not self.is_running:
                in_dir = self.input_dir.get()
                if in_dir and os.path.isdir(in_dir):
                    files = [f for f in os.listdir(in_dir) if os.path.isfile(os.path.join(in_dir, f)) and self._is_allowed_file(f)]
                    if any(f not in self.processed_files for f in files):
                        self.after(0, lambda: self.start_processing(new_only=True))

    def toggle_pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_btn.configure(text="Resume", fg_color="#10b981", hover_color="#059669")
            self.log("Batch PAUSED.", "info")
        else:
            self.pause_event.set()
            self.pause_btn.configure(text="Pause", fg_color="#f59e0b", hover_color="#d97706")
            self.log("Batch RESUMED.", "info")

    def cancel_batch(self):
        if self.is_running:
            self.cancel_flag = True
            self.pause_event.set() # Unblock if paused
            self.log("Canceling batch... finishing current active files.", "error")
            self.pause_btn.configure(state="disabled")
            self.cancel_btn.configure(state="disabled")

    def process_file(self, file_path, out_dir, ai, min_kw, max_kw, style_preset, csv_logger):
        self.pause_event.wait()
        if self.cancel_flag: return

        name = os.path.basename(file_path)
        self.log(f"{name}", "processing")
        
        preview = extract_preview_image(file_path, self.processor)
        if not preview:
            self.log(f"{name} (No preview)", "error")
            self.update_stats("error")
            return

        file_hash = get_file_hash(preview)
        cached = get_cached_metadata(file_hash)

        if cached:
            self.log(f"{name} [CACHE HIT]", "cache")
            meta = cached
            status, color = "CACHE", "#8b5cf6"
        else:
            meta = ai.generate_metadata(preview, min_kw, max_kw, style_preset)
            set_cached_metadata(file_hash, meta)
            status, color = "API CALL", "#f59e0b"

        try:
            img = Image.open(preview).copy()
        except:
            img = None

        try: os.remove(preview)
        except: pass

        meta = clean_metadata(meta, max_kw)

        out_path = os.path.join(out_dir, name)
        
        # In-place subfolder pipeline
        base_name = os.path.splitext(name)[0]
        sub_dir = os.path.join(out_dir, base_name)
        os.makedirs(sub_dir, exist_ok=True)
        
        final_path = os.path.join(sub_dir, name)
        
        # move original file to subfolder
        shutil.move(file_path, final_path)

        title, desc, keywords = meta.get("title", ""), meta.get("description", ""), meta.get("keywords", [])
        
        if img:
            self.update_preview(img, status, color, meta, final_path, file_hash)

        if self.processor.embed_metadata(final_path, title, desc, keywords, "Copyright Text"):
            self.log(f"{name} ({len(keywords)} kw)", "success")
            # Write master CSV (at root)
            csv_logger.log(name, title, desc, keywords)
            generate_microstock_csvs(out_dir)
            # Write localized CSV for this file alone in the subfolder
            temp_master = os.path.join(sub_dir, "metadata_output.csv")
            import csv
            with open(temp_master, 'w', newline='', encoding='utf-8') as tf:
                tw = csv.writer(tf)
                tw.writerow(["Filename","Title","Description","Keywords"])
                tw.writerow([name, title, desc, ",".join(keywords)])
            generate_microstock_csvs(sub_dir)

            if getattr(self, 'auto_zip', None) and self.auto_zip.get() and name.lower().endswith(('.svg', '.eps')):
                import zipfile
                jpg_path = os.path.join(sub_dir, base_name + ".jpg")
                if img:
                    try: img.convert("RGB").save(jpg_path, "JPEG", quality=95)
                    except: pass
                zip_path = os.path.join(sub_dir, base_name + ".zip")
                try:
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                        zf.write(final_path, arcname=name)
                        if os.path.exists(jpg_path): zf.write(jpg_path, arcname=base_name + ".jpg")
                except: pass
            
            self.update_stats("success")
        else:
            self.log(f"{name} (Embed failed)", "error")
            self.update_stats("error")

    def start_offline_retag(self):
        csv_path = ctk.filedialog.askopenfilename(
            title="Select metadata CSV",
            filetypes=[("CSV files", "*.csv")]
        )
        if not csv_path:
            return

        target_dir = self.input_dir.get()
        if not target_dir or not os.path.isdir(target_dir):
            self.log("Set Folder first.", "error")
            return

        self.retag_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        threading.Thread(target=self._run_offline_retag, args=(csv_path, target_dir), daemon=True).start()

    def _find_asset(self, target_dir: str, filename: str) -> str | None:
        for root, _dirs, files in os.walk(target_dir):
            if filename in files:
                return os.path.join(root, filename)
        return None

    def _run_offline_retag(self, csv_path: str, target_dir: str):
        import csv as csv_mod
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                rows = list(csv_mod.DictReader(f))
        except Exception as e:
            self.log(f"CSV read error: {e}", "error")
            self.after(0, lambda: self.retag_btn.configure(state="normal"))
            self.after(0, lambda: self.start_btn.configure(state="normal"))
            return

        if not rows:
            self.log("CSV empty.", "error")
            self.after(0, lambda: self.retag_btn.configure(state="normal"))
            self.after(0, lambda: self.start_btn.configure(state="normal"))
            return

        max_kw = int(self.max_kw_entry.get() or 50)
        total = len(rows)
        success = 0
        self.log(f"Offline Re-Tag: {total} rows from {os.path.basename(csv_path)}", "info")
        self.progress_bar.set(0)

        for i, row in enumerate(rows):
            filename = row.get("Filename", "").strip()
            if not filename:
                self.log(f"Row {i+1}: missing Filename", "error")
                continue

            asset_path = self._find_asset(target_dir, filename)
            if not asset_path:
                self.log(f"{filename} not found in folder", "error")
                continue

            title = row.get("Title", "").strip()
            desc = row.get("Description", "").strip()
            raw_kws = [k.strip() for k in row.get("Keywords", "").split(",") if k.strip()]
            keywords = sanitize_keywords(raw_kws, max_kw)

            if self.processor.embed_metadata(asset_path, title, desc, keywords, "Copyright Text"):
                file_hash = get_file_hash(asset_path)
                set_cached_metadata(file_hash, {"title": title, "description": desc, "keywords": keywords})
                self.log(f"[OFFLINE SUCCESS] {filename}", "success")
                success += 1
            else:
                self.log(f"[OFFLINE FAIL] {filename}", "error")

            self.after(0, self.progress_bar.set, (i + 1) / total)

        self.log(f"Offline Re-Tag done: {success}/{total} succeeded", "info")
        self.after(0, lambda: self.retag_btn.configure(state="normal"))
        self.after(0, lambda: self.start_btn.configure(state="normal"))

    def start_processing(self, new_only=False):
        if self.is_running: return
        
        self.config.update({
            "provider": self.provider_cb.get(),
            "style_preset": self.style_cb.get(),
            "api_key": self.api_key_entry.get(),
            "min_kw": int(self.min_kw_entry.get() or 5),
            "max_kw": int(self.max_kw_entry.get() or 20),
            "workers": int(self.workers_slider.get()),
            "formats": {ext: var.get() for ext, var in self.fmt_vars.items()}
        })
        save_config(self.config)
        
        in_dir = self.input_dir.get()
        out_dir = in_dir
        if not in_dir: return self.log("Path missing.", "error")

        files = [f for f in os.listdir(in_dir) if os.path.isfile(os.path.join(in_dir, f)) and self._is_allowed_file(f)]
        if new_only:
            files = [f for f in files if f not in self.processed_files]
            
        if not files: return self.log("No new files." if new_only else "No files.", "error")
        self.processed_files.update(files)

        self.is_running = True
        self.cancel_flag = False
        self.pause_event.set()
        self.pause_btn.configure(text="Pause", fg_color="#f59e0b", hover_color="#d97706", state="normal")
        self.cancel_btn.configure(state="normal")
        
        self.start_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self.stats = {"total": len(files), "success": 0, "error": 0}
        self.update_stats("total")
        self.stats["total"] = len(files)

        paths = [os.path.join(in_dir, f) for f in files]
        threading.Thread(target=self._run_batch, args=(paths, out_dir), daemon=True).start()

    def _run_batch(self, paths, out_dir):
        ai = AIService(self.config["provider"], self.config["api_key"])
        csv_logger = CSVLogger(os.path.join(out_dir, "metadata_output.csv"))
        
        with ThreadPoolExecutor(max_workers=self.config["workers"]) as executor:
            futures = [executor.submit(self.process_file, f, out_dir, ai, self.config["min_kw"], self.config["max_kw"], self.config["style_preset"], csv_logger) for f in paths]
            for i, f in enumerate(futures):
                f.result()
                if not self.cancel_flag:
                    self.after(0, self.progress_bar.set, (i + 1) / len(paths))

        if self.cancel_flag:
            self.log("Batch CANCELED.", "error")
        else:
            self.log("Batch complete. Generating exports...", "info")
            generate_microstock_csvs(out_dir)
        
        self.is_running = False
        self.after(0, lambda: self.start_btn.configure(state="normal"))
        self.after(0, lambda: self.pause_btn.configure(state="disabled"))
        self.after(0, lambda: self.cancel_btn.configure(state="disabled"))

if __name__ == "__main__":
    app = App()
    app.mainloop()