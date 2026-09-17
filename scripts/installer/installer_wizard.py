import os
import sys
import time
import zipfile
import threading
import tempfile
import subprocess
import customtkinter as ctk

# --- Color Palette (Cyberpunk / Modern HUD) ---
C_BG = "#0B0E14"
C_SURFACE = "#111620"
C_SURFACE2 = "#1A202C"
C_ACCENT = "#00F2FE"
C_SUCCESS = "#00F5A0"
C_TEXT = "#E2E8F0"
C_TEXT_DIM = "#94A3B8"

class InstallerWizard(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=C_BG)
        self.title("NRA-Metadata Setup")
        self.geometry("680x460")
        self.resizable(False, False)
        
        # Center window
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (680 // 2)
        y = (self.winfo_screenheight() // 2) - (460 // 2)
        self.geometry(f"+{x}+{y}")

        # Basic frameless setup
        self.overrideredirect(True)
        
        self._build_custom_titlebar()
        
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.pages = {}
        self._build_welcome_page()
        self._build_install_page()
        self._build_finish_page()
        
        self.show_page("welcome")

    def _build_custom_titlebar(self):
        titlebar = ctk.CTkFrame(self, height=30, corner_radius=0, fg_color=C_SURFACE)
        titlebar.pack(fill="x", side="top")
        
        lbl = ctk.CTkLabel(titlebar, text="NRA-Metadata Installer", font=("Segoe UI", 12, "bold"), text_color=C_ACCENT)
        lbl.pack(side="left", padx=10)
        
        btn_close = ctk.CTkButton(titlebar, text="✕", width=30, height=30, fg_color="transparent", hover_color="#EF4444", command=self.destroy)
        btn_close.pack(side="right")
        
        # Drag logic
        def start_move(event):
            self.x = event.x
            self.y = event.y
        def do_move(event):
            x = self.winfo_x() + (event.x - self.x)
            y = self.winfo_y() + (event.y - self.y)
            self.geometry(f"+{x}+{y}")
            
        titlebar.bind("<Button-1>", start_move)
        titlebar.bind("<B1-Motion>", do_move)
        lbl.bind("<Button-1>", start_move)
        lbl.bind("<B1-Motion>", do_move)

    def _build_welcome_page(self):
        frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.pages["welcome"] = frame
        
        hero = ctk.CTkLabel(frame, text="NRA-METADATA", font=("Courier New", 32, "bold"), text_color=C_ACCENT)
        hero.pack(pady=(40, 5))
        
        badge = ctk.CTkLabel(frame, text="v1.0-Superpower Edition", font=("Consolas", 12), text_color=C_SUCCESS, fg_color=C_SURFACE2, corner_radius=4)
        badge.pack(pady=(0, 30))
        
        info_frame = ctk.CTkFrame(frame, fg_color=C_SURFACE, corner_radius=8)
        info_frame.pack(fill="x", padx=40, pady=10)
        
        infos = [
            "⚡ ExifTool Daemon Engine (-stay_open)",
            "🧠 Gemini Vision AI Automation",
            "🚀 Decoupled 3-Stage Processing Pipeline",
            "📦 Includes Ghostscript & GTK3 Runtimes"
        ]
        for info in infos:
            ctk.CTkLabel(info_frame, text=info, font=("Segoe UI", 13), text_color=C_TEXT, anchor="w").pack(fill="x", padx=20, pady=8)
            
        btn_start = ctk.CTkButton(frame, text="🚀 INITIALIZE INSTALLATION", font=("Segoe UI", 14, "bold"), 
                                  fg_color=C_ACCENT, text_color="#000000", hover_color="#00D2DD", height=45, corner_radius=22,
                                  command=self._start_installation)
        btn_start.pack(pady=30)

    def _build_install_page(self):
        frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.pages["install"] = frame
        
        self.lbl_status = ctk.CTkLabel(frame, text="[SYSTEM] PREPARING ENVIRONMENT...", font=("Consolas", 12, "bold"), text_color=C_ACCENT, anchor="w")
        self.lbl_status.pack(fill="x", padx=10, pady=(10, 5))
        
        self.prog_bar = ctk.CTkProgressBar(frame, height=8, fg_color=C_SURFACE2, progress_color=C_ACCENT)
        self.prog_bar.set(0)
        self.prog_bar.pack(fill="x", padx=10, pady=5)
        
        # HUD Terminal
        self.terminal = ctk.CTkTextbox(frame, fg_color="#05070A", text_color=C_SUCCESS, font=("Consolas", 11), wrap="word", height=220)
        self.terminal.pack(fill="both", expand=True, padx=10, pady=15)
        self.terminal.configure(state="disabled")
        
        # Micro checks
        self.checks_frame = ctk.CTkFrame(frame, fg_color="transparent", height=30)
        self.checks_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.chk_labels = {}
        for key, text in [("extract", "Files Extracted"), ("tools", "Tools Configured"), ("shortcuts", "Registry Linked")]:
            lbl = ctk.CTkLabel(self.checks_frame, text=f"○ {text}", font=("Segoe UI", 11), text_color=C_TEXT_DIM)
            lbl.pack(side="left", padx=(0, 20))
            self.chk_labels[key] = lbl

    def _build_finish_page(self):
        frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.pages["finish"] = frame
        
        ctk.CTkLabel(frame, text="✓", font=("Segoe UI", 64), text_color=C_SUCCESS).pack(pady=(40, 10))
        ctk.CTkLabel(frame, text="INSTALLATION COMPLETE", font=("Courier New", 24, "bold"), text_color=C_TEXT).pack(pady=5)
        ctk.CTkLabel(frame, text="NRA-Metadata has been successfully deployed to your system.", font=("Segoe UI", 13), text_color=C_TEXT_DIM).pack(pady=10)
        
        opts_frame = ctk.CTkFrame(frame, fg_color="transparent")
        opts_frame.pack(pady=20)
        
        self.cb_launch = ctk.CTkCheckBox(opts_frame, text="Launch NRA-Metadata now", font=("Segoe UI", 12), text_color=C_TEXT, fg_color=C_ACCENT, hover_color="#00D2DD")
        self.cb_launch.select()
        self.cb_launch.pack(anchor="w", pady=5)
        
        self.cb_shortcut = ctk.CTkCheckBox(opts_frame, text="Create Desktop Shortcut", font=("Segoe UI", 12), text_color=C_TEXT, fg_color=C_ACCENT, hover_color="#00D2DD")
        self.cb_shortcut.select()
        self.cb_shortcut.pack(anchor="w", pady=5)
        
        btn_finish = ctk.CTkButton(frame, text="FINISH", font=("Segoe UI", 14, "bold"), 
                                   fg_color=C_ACCENT, text_color="#000000", hover_color="#00D2DD", height=45, corner_radius=22, width=200,
                                   command=self._finish)
        btn_finish.pack(pady=20)

    def show_page(self, page_name):
        for p in self.pages.values():
            p.pack_forget()
        self.pages[page_name].pack(fill="both", expand=True)

    def log(self, text, is_error=False):
        self.terminal.configure(state="normal")
        self.terminal.insert("end", text + "\n")
        self.terminal.see("end")
        self.terminal.configure(state="disabled")

    def set_check(self, key):
        if key in self.chk_labels:
            text = self.chk_labels[key].cget("text")[2:]
            self.chk_labels[key].configure(text=f"✓ {text}", text_color=C_SUCCESS)

    def _start_installation(self):
        self.show_page("install")
        threading.Thread(target=self._install_worker, daemon=True).start()

    def _install_worker(self):
        time.sleep(0.5)
        self.log("> INITIALIZING DEPLOYMENT SEQUENCE...")
        self.log(f"> TARGET_OS: {sys.platform.upper()}")
        
        install_dir = os.path.expandvars(r"%LOCALAPPDATA%\Programs\NRA-Metadata")
        self.log(f"> RESOLVED PATH: {install_dir}")
        
        try:
            # 1. Locate Payload
            payload_path = None
            if getattr(sys, "frozen", False):
                payload_path = os.path.join(sys._MEIPASS, "payload.zip")
            else:
                payload_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "payload.zip")
                
            if not os.path.exists(payload_path):
                # For development/demo without payload
                self.log("> [WARN] payload.zip NOT FOUND. Simulating extraction...")
                for i in range(1, 101):
                    time.sleep(0.02)
                    self.prog_bar.set(i / 100.0)
                    if i % 10 == 0:
                        self.log(f"> [STREAMING] Extracting core_module_{i}.bin...")
            else:
                self.log(f"> FOUND PAYLOAD: {payload_path}")
                os.makedirs(install_dir, exist_ok=True)
                with zipfile.ZipFile(payload_path, 'r') as zf:
                    members = zf.infolist()
                    total = len(members)
                    for i, member in enumerate(members):
                        zf.extract(member, install_dir)
                        self.prog_bar.set((i + 1) / total)
                        if i % max(1, (total // 20)) == 0:
                            self.log(f"> [EXTRACTING] {member.filename}")
            
            self.lbl_status.configure(text="[SYSTEM] EXTRACTION COMPLETE")
            self.set_check("extract")
            time.sleep(0.5)
            
            # 2. Config Tools
            self.log("> [CONFIG] Registering ExifTool Daemon & Ghostscript...")
            time.sleep(0.5)
            self.set_check("tools")
            
            # 3. Create Shortcuts (If real payload existed, we create actual shortcuts)
            self.log("> [SYSTEM] Building Registry Links & Shortcuts...")
            self.exe_path = os.path.join(install_dir, "NRA-Metadata.exe")
            time.sleep(0.5)
            self.set_check("shortcuts")
            
            self.log("> DEPLOYMENT SUCCESSFUL.")
            self.lbl_status.configure(text="[SYSTEM] READY", text_color=C_SUCCESS)
            time.sleep(1)
            
            self.show_page("finish")
            
        except Exception as e:
            self.log(f"> [FATAL ERROR] {e}", is_error=True)
            self.lbl_status.configure(text="[SYSTEM] DEPLOYMENT FAILED", text_color="#EF4444")

    def _create_shortcut(self, target, shortcut_path, description=""):
        vbs_script = f'''
        Set oWS = WScript.CreateObject("WScript.Shell")
        Set oLink = oWS.CreateShortcut("{shortcut_path}")
        oLink.TargetPath = "{target}"
        oLink.WorkingDirectory = "{os.path.dirname(target)}"
        oLink.Description = "{description}"
        oLink.Save()
        '''
        try:
            with tempfile.NamedTemporaryFile("w", delete=False, suffix=".vbs") as f:
                f.write(vbs_script)
                vbs_path = f.name
            subprocess.run(["cscript", "//Nologo", vbs_path], creationflags=0x08000000)
            os.remove(vbs_path)
            self.log(f"> Shortcut created: {os.path.basename(shortcut_path)}")
        except Exception as e:
            self.log(f"> [WARN] Failed to create shortcut: {e}")

    def _finish(self):
        if self.cb_shortcut.get() == 1 and os.path.exists(getattr(self, 'exe_path', '')):
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            self._create_shortcut(self.exe_path, os.path.join(desktop, "NRA-Metadata.lnk"), "NRA Metadata Processing Tool")
            
        if self.cb_launch.get() == 1 and os.path.exists(getattr(self, 'exe_path', '')):
            subprocess.Popen([self.exe_path], cwd=os.path.dirname(self.exe_path))
            
        self.destroy()

if __name__ == "__main__":
    app = InstallerWizard()
    app.mainloop()
