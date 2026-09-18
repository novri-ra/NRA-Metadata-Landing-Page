import os
import sys
import threading
import time
import urllib.request
import subprocess
import customtkinter as ctk

from backend.processors._tools import no_window_kwargs

class DownloaderDialog(ctk.CTkToplevel):
    def __init__(self, parent, url: str, dest_dir: str, title: str = "Downloader", exe_name: str = "installer.exe"):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x180")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.url = url
        self.dest_dir = dest_dir
        self.exe_name = exe_name
        self.installer_path = os.path.join(dest_dir, exe_name)
        
        # UI Components
        self.status_label = ctk.CTkLabel(self, text="Memulai unduhan...", font=ctk.CTkFont(family="Segoe UI", size=12))
        self.status_label.pack(pady=(20, 10), padx=20, anchor="w")

        self.progress_bar = ctk.CTkProgressBar(self, width=360)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=5, padx=20)

        self.speed_label = ctk.CTkLabel(self, text="0% (0 KB/s)", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="gray")
        self.speed_label.pack(pady=(0, 20), padx=20, anchor="w")

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._cancel_flag = False

    def start_download(self, callback=None):
        self.callback = callback
        os.makedirs(self.dest_dir, exist_ok=True)
        threading.Thread(target=self._download_worker, daemon=True).start()

    def on_close(self):
        self._cancel_flag = True
        self.destroy()

    def _update_ui(self, status, progress, speed_text):
        if not self.winfo_exists():
            return
        if status:
            self.status_label.configure(text=status)
        if progress is not None:
            self.progress_bar.set(progress)
        if speed_text:
            self.speed_label.configure(text=speed_text)

    def _download_worker(self):
        try:
            req = urllib.request.Request(self.url, headers={'User-Agent': 'curl/7.68.0'})
            ctx = None
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                total_size = int(resp.headers.get('Content-Length', 0))
                downloaded = 0
                chunk_size = 65536
                start_time = time.time()
                
                with open(self.installer_path, "wb") as f:
                    while True:
                        if self._cancel_flag:
                            break
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Calculate progress and speed
                        elapsed = time.time() - start_time
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        speed_mb = speed / (1024 * 1024)
                        
                        if total_size > 0:
                            prog = downloaded / total_size
                            status = f"Mengunduh... ({downloaded/(1024*1024):.1f} MB / {total_size/(1024*1024):.1f} MB)"
                            pct = int(prog * 100)
                            speed_str = f"{pct}% ({speed_mb:.1f} MB/s)"
                        else:
                            prog = 0
                            status = f"Mengunduh... ({downloaded/(1024*1024):.1f} MB)"
                            speed_str = f"({speed_mb:.1f} MB/s)"
                            
                        self.after(0, self._update_ui, status, prog, speed_str)
            
            if self._cancel_flag:
                if os.path.exists(self.installer_path):
                    os.remove(self.installer_path)
                return

            # Check Magic Bytes
            with open(self.installer_path, "rb") as f:
                if f.read(2) != b"MZ":
                    raise ValueError("File yang diunduh bukan executable yang valid.")

            # Proceed to installation
            self.after(0, self._update_ui, "Memasang GTK3 Runtime (Silent)...", None, "Harap tunggu...")
            self.after(0, lambda: self.progress_bar.configure(mode="indeterminate"))
            self.after(0, self.progress_bar.start)

            # Install silently
            cmd = [self.installer_path, "/S", f"/D={self.dest_dir}"]
            env = os.environ.copy()
            env["__COMPAT_LAYER"] = "RunAsInvoker"
            
            res = subprocess.run(cmd, check=False, timeout=120, env=env, **no_window_kwargs())
            
            # Clean up installer
            if os.path.exists(self.installer_path):
                try:
                    os.remove(self.installer_path)
                except Exception:
                    pass

            if res.returncode == 0:
                self.after(0, self._update_ui, "Instalasi Selesai!", 1.0, "")
            else:
                self.after(0, self._update_ui, f"Gagal instalasi (Code: {res.returncode})", 1.0, "")

            time.sleep(1)
            if not self._cancel_flag:
                self.after(0, self.destroy)
                if self.callback:
                    self.after(0, self.callback)

        except Exception as e:
            if not self._cancel_flag:
                self.after(0, self._update_ui, f"Error: {e}", 0, "Gagal mengunduh.")
                self.after(0, self.progress_bar.stop)
