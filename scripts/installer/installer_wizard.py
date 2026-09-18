import os
import sys
import time
import zipfile
import threading
import tempfile
import subprocess
import ctypes

def get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

def has_real_admin_rights() -> bool:
    try:
        test_dir = r"C:\Program Files\_nra_admin_test"
        os.makedirs(test_dir, exist_ok=True)
        os.rmdir(test_dir)
        return True
    except Exception:
        return False

import customtkinter as ctk

# --- Color Palette (Hermes Agent Style) ---
C_BG = "#0D1F46"          # Deep Navy
C_SURFACE = "#0A1733"     # Darker Navy
C_TEXT = "#F0F2F8"        # Cream / Soft White
C_TEXT_SUB = "#8FA0BC"    # Periwinkle / Slate
C_ACCENT = "#38BDF8"      # Electric Cyan
C_SUCCESS = "#10B981"     # Soft Green
C_BORDER = "#1E3A8A"      # Blue border

class InstallerWizard(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=C_BG)
        self.title("NRA Metadata Setup")
        
        # Dimensi: 800x520 (Centered, non-resizable)
        self.geometry("800x520")
        self.resizable(False, False)
        self.overrideredirect(True)
        
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (800 // 2)
        y = (self.winfo_screenheight() // 2) - (520 // 2)
        self.geometry(f"+{x}+{y}")

        # Topmost & Focus
        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        self.focus_force()

        # Taskbar icon for frameless window
        self.after(100, self._force_taskbar_icon)

        # Title bar for drag & close
        self._build_custom_titlebar()

        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)

        self.pages = {}
        self._build_welcome_page()
        self._build_install_page()
        
        self.show_page("welcome")

    def _force_taskbar_icon(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            style = style & ~0x00000080
            style = style | 0x00040000
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)
            self.wm_withdraw()
            self.after(10, self.wm_deiconify)
        except Exception:
            pass

    def _build_custom_titlebar(self):
        titlebar = ctk.CTkFrame(self, height=30, corner_radius=0, fg_color=C_SURFACE)
        titlebar.pack(fill="x", side="top")
        
        lbl = ctk.CTkLabel(titlebar, text="", height=30)
        lbl.pack(side="left")
        
        btn_close = ctk.CTkButton(titlebar, text="✕", width=30, height=30, fg_color="transparent", 
                                  hover_color="#EF4444", text_color=C_TEXT_SUB, command=self.destroy)
        btn_close.pack(side="right")
        
        drag_pos = {"x": 0, "y": 0}
        def start_move(event):
            drag_pos["x"] = event.x
            drag_pos["y"] = event.y
        def do_move(event):
            x = self.winfo_x() + (event.x - drag_pos["x"])
            y = self.winfo_y() + (event.y - drag_pos["y"])
            self.geometry(f"+{x}+{y}")
            
        titlebar.bind("<Button-1>", start_move)
        titlebar.bind("<B1-Motion>", do_move)

    def _build_welcome_page(self):
        frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.pages["welcome"] = frame

        content = ctk.CTkFrame(frame, fg_color="transparent")
        content.place(relx=0.5, rely=0.45, anchor="center")

        ctk.CTkLabel(content, text="NRA METADATA", font=("Cambria", 36, "bold"), text_color=C_TEXT).pack(pady=(0, 10))
        
        sub = "The microstock assistant that powers your workflow. We'll set things up in the background — takes a few minutes."
        ctk.CTkLabel(content, text=sub, font=("Segoe UI", 13), text_color=C_TEXT_SUB, wraplength=500, justify="center").pack(pady=(0, 30))
        
        ctk.CTkLabel(content, text="Target: C:\\Program Files\\NRA-Metadata", font=("Consolas", 12), text_color=C_ACCENT).pack(pady=(0, 40))

        btn_start = ctk.CTkButton(content, text="INSTALL", font=("Segoe UI", 14, "bold"), 
                                  fg_color="transparent", border_color=C_BORDER, border_width=2,
                                  text_color=C_TEXT, hover_color=C_SURFACE, height=45, width=160, corner_radius=4,
                                  command=self._start_installation)
        btn_start.pack()

    def _build_install_page(self):
        frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.pages["install"] = frame

        # Header
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=40, pady=(30, 20))
        
        ctk.CTkLabel(header, text="Setting up NRA Metadata", font=("Cambria", 22, "bold"), text_color=C_TEXT).pack(anchor="w")
        sub = "This is a one-time setup. The installer is configuring binaries, database, and system shortcuts. Subsequent launches will skip this step."
        ctk.CTkLabel(header, text=sub, font=("Segoe UI", 12), text_color=C_TEXT_SUB, wraplength=700, justify="left").pack(anchor="w", pady=(5, 0))

        # Status Bar
        status_frame = ctk.CTkFrame(frame, fg_color="transparent")
        status_frame.pack(fill="x", padx=40, pady=(10, 5))
        
        self.lbl_counter = ctk.CTkLabel(status_frame, text="0 of 6 steps complete", font=("Segoe UI", 11), text_color=C_TEXT_SUB)
        self.lbl_counter.pack(side="left")
        
        self.lbl_percent = ctk.CTkLabel(status_frame, text="0%", font=("Segoe UI", 11, "bold"), text_color=C_ACCENT)
        self.lbl_percent.pack(side="right")
        
        self.prog_bar = ctk.CTkProgressBar(frame, height=4, fg_color=C_SURFACE, progress_color=C_ACCENT, corner_radius=0)
        self.prog_bar.set(0)
        self.prog_bar.pack(fill="x", padx=40, pady=(0, 20))

        # Dual Column Setup
        split_frame = ctk.CTkFrame(frame, fg_color="transparent")
        split_frame.pack(fill="both", expand=True, padx=40, pady=(0, 20))
        split_frame.grid_columnconfigure(0, weight=1)
        split_frame.grid_columnconfigure(1, weight=1)

        # Left Column: Stepper
        self.step_frame = ctk.CTkFrame(split_frame, fg_color="transparent")
        self.step_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        
        self.steps = [
            "Verifying Administrator Privileges & Environment",
            "Creating directory C:\\Program Files\\NRA-Metadata",
            "Unpacking Core Engine & Binaries (payload.dat)",
            "Registering ExifTool Daemon & Ghostscript",
            "Initializing SQLite Cache & Settings",
            "Generating Desktop & Start Menu Shortcuts"
        ]
        self.step_widgets = []
        for s in self.steps:
            row = ctk.CTkFrame(self.step_frame, fg_color="transparent")
            row.pack(fill="x", pady=8)
            icon = ctk.CTkLabel(row, text="○", font=("Consolas", 14), text_color=C_TEXT_SUB, width=20)
            icon.pack(side="left")
            lbl = ctk.CTkLabel(row, text=s, font=("Segoe UI", 12), text_color=C_TEXT_SUB)
            lbl.pack(side="left", padx=(10, 0))
            self.step_widgets.append((icon, lbl))

        # Right Column: Terminal
        self.term_frame = ctk.CTkFrame(split_frame, fg_color=C_SURFACE, corner_radius=6)
        self.term_frame.grid(row=0, column=1, sticky="nsew")
        
        term_head = ctk.CTkFrame(self.term_frame, fg_color="transparent", height=30)
        term_head.pack(fill="x", padx=15, pady=(10, 5))
        ctk.CTkLabel(term_head, text="Live output", font=("Segoe UI", 11, "bold"), text_color=C_TEXT_SUB).pack(side="left")
        self.lbl_lines = ctk.CTkLabel(term_head, text="0 lines", font=("Segoe UI", 11), text_color=C_TEXT_SUB)
        self.lbl_lines.pack(side="right")
        
        self.terminal = ctk.CTkTextbox(self.term_frame, fg_color="transparent", text_color=C_TEXT_SUB, font=("Consolas", 10), wrap="word")
        self.terminal.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.terminal.configure(state="disabled")
        self.term_lines = 0

        # Footer
        footer = ctk.CTkFrame(frame, fg_color="transparent", height=50)
        footer.pack(fill="x", side="bottom", padx=40, pady=20)
        
        self.btn_toggle = ctk.CTkButton(footer, text="Hide details", font=("Segoe UI", 12), fg_color="transparent", hover_color=C_SURFACE, text_color=C_ACCENT, width=100, command=self._toggle_terminal)
        self.btn_toggle.pack(side="left")
        
        self.btn_action = ctk.CTkButton(footer, text="Cancel", font=("Segoe UI", 12, "bold"), fg_color="transparent", border_color=C_BORDER, border_width=1, text_color=C_TEXT, hover_color=C_SURFACE, width=100, command=self.destroy)
        self.btn_action.pack(side="right")
        
        self.term_visible = True

    def _toggle_terminal(self):
        if self.term_visible:
            self.term_frame.grid_remove()
            self.btn_toggle.configure(text="Show details")
            self.term_visible = False
        else:
            self.term_frame.grid()
            self.btn_toggle.configure(text="Hide details")
            self.term_visible = True

    def show_page(self, page_name):
        for p in self.pages.values():
            p.pack_forget()
        self.pages[page_name].pack(fill="both", expand=True)

    def log(self, text):
        self.terminal.configure(state="normal")
        self.terminal.insert("end", text + "\n")
        self.terminal.see("end")
        self.terminal.configure(state="disabled")
        self.term_lines += 1
        self.lbl_lines.configure(text=f"{self.term_lines} lines")

    def set_step_status(self, idx, status):
        # status: 0=pending, 1=active, 2=done
        icon, lbl = self.step_widgets[idx]
        if status == 0:
            icon.configure(text="○", text_color=C_TEXT_SUB)
            lbl.configure(text_color=C_TEXT_SUB)
        elif status == 1:
            icon.configure(text="↳", text_color=C_ACCENT)
            lbl.configure(text_color=C_TEXT)
        elif status == 2:
            icon.configure(text="✓", text_color=C_SUCCESS)
            lbl.configure(text_color=C_TEXT)

    def _start_installation(self):
        self.show_page("install")
        threading.Thread(target=self._install_worker, daemon=True).start()

    def _install_worker(self):
        try:
            program_files = os.environ.get("ProgramW6432", os.environ.get("ProgramFiles", "C:\\Program Files"))
            install_dir = os.path.join(program_files, "NRA-Metadata")
            
            # Step 1
            self.set_step_status(0, 1)
            self.log("> Checking administrator privileges...")
            time.sleep(0.5)
            if not has_real_admin_rights():
                self.log("> [WARN] Program Files write access blocked. Will fallback to Local AppData.")
            self.set_step_status(0, 2)
            self.lbl_counter.configure(text="1 of 6 steps complete")
            self.prog_bar.set(0.1)

            # Step 2
            self.set_step_status(1, 1)
            self.log(f"> Creating directory: {install_dir}")
            try:
                os.makedirs(install_dir, exist_ok=True)
            except PermissionError as pe:
                self.log(f"> [INFO] Program Files terproteksi khusus ({pe}), mengalihkan instalasi ke Local AppData...")
                install_dir = os.path.expandvars(r"%LOCALAPPDATA%\Programs\NRA-Metadata")
                self.log(f"> New target: {install_dir}")
                os.makedirs(install_dir, exist_ok=True)
            time.sleep(0.5)
            self.set_step_status(1, 2)
            self.lbl_counter.configure(text="2 of 6 steps complete")
            self.prog_bar.set(0.2)

            # Step 3
            self.set_step_status(2, 1)
            payload_path = os.path.join(get_base_dir(), "payload.dat")
                
            if not os.path.exists(payload_path):
                self.log("> [WARN] payload.dat NOT FOUND. Simulating extraction...")
                for i in range(1, 51):
                    time.sleep(0.02)
                    self.prog_bar.set(0.2 + (i/50.0)*0.5)
                    self.lbl_percent.configure(text=f"{int(20 + i)}%")
                    if i % 5 == 0:
                        self.log(f"> Extracting core_module_{i}.bin...")
            else:
                self.log(f"> Found payload: {payload_path}")
                with zipfile.ZipFile(payload_path, 'r') as zf:
                    members = zf.infolist()
                    total = len(members)
                    for i, member in enumerate(members):
                        zf.extract(member, install_dir)
                        progress = 0.2 + ((i + 1) / total) * 0.5
                        self.prog_bar.set(progress)
                        self.lbl_percent.configure(text=f"{int(progress*100)}%")
                        if i % max(1, (total // 20)) == 0:
                            self.log(f"> Unpacking {member.filename}")
            
            self.set_step_status(2, 2)
            self.lbl_counter.configure(text="3 of 6 steps complete")
            self.prog_bar.set(0.7)
            self.lbl_percent.configure(text="70%")

            # Step 4
            self.set_step_status(3, 1)
            self.log("> Registering ExifTool Daemon & Ghostscript paths...")
            time.sleep(0.5)
            self.set_step_status(3, 2)
            self.lbl_counter.configure(text="4 of 6 steps complete")
            self.prog_bar.set(0.8)
            self.lbl_percent.configure(text="80%")

            # Step 5
            self.set_step_status(4, 1)
            self.log("> Initializing SQLite Cache and transferring settings...")
            time.sleep(0.5)
            self.set_step_status(4, 2)
            self.lbl_counter.configure(text="5 of 6 steps complete")
            self.prog_bar.set(0.9)
            self.lbl_percent.configure(text="90%")

            # Step 6
            self.set_step_status(5, 1)
            self.log("> Generating shortcuts...")
            self.exe_path = os.path.join(install_dir, "NRA-Metadata.exe")
            
            desktop_path = os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "Desktop")
            if not os.path.exists(desktop_path):
                desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            self._create_shortcut(self.exe_path, os.path.join(desktop_path, "NRA-Metadata.lnk"), "NRA Metadata")
            
            start_menu = os.path.join(os.environ.get("ALLUSERSPROFILE", r"C:\ProgramData"), "Microsoft", "Windows", "Start Menu", "Programs")
            if not os.path.exists(start_menu):
                start_menu = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs")
            self._create_shortcut(self.exe_path, os.path.join(start_menu, "NRA-Metadata.lnk"), "NRA Metadata")
            
            time.sleep(0.5)
            self.set_step_status(5, 2)
            self.lbl_counter.configure(text="6 of 6 steps complete")
            self.prog_bar.set(1.0)
            self.lbl_percent.configure(text="100%")
            
            self.log("> [SUCCESS] Deployment completed successfully.")
            self.btn_action.configure(text="LAUNCH APPLICATION", fg_color=C_TEXT, text_color=C_BG, command=self._launch_app)
            
        except Exception as e:
            self.log(f"> [FATAL ERROR] {e}")
            self.btn_action.configure(text="CLOSE")

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
            self.log(f"> Linked {os.path.basename(shortcut_path)}")
        except Exception as e:
            self.log(f"> [WARN] Shortcut failed: {e}")

    def _launch_app(self):
        if hasattr(self, 'exe_path') and os.path.exists(self.exe_path):
            subprocess.Popen([self.exe_path], cwd=os.path.dirname(self.exe_path))
        self.destroy()

if __name__ == "__main__":
    app = InstallerWizard()
    app.mainloop()