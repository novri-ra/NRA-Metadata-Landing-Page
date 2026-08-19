import re
import os

with open('apps/desktop/src/main.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Imports
import_inject = """from packages.shared_utils.license_manager import AuthClient
"""

code = code.replace("from packages.media_processor.previews import extract_preview_image\n", 
                    "from packages.media_processor.previews import extract_preview_image\n" + import_inject)

# 2. Init AuthClient and check
init_search = """        self.config = load_config()
        self.input_dir = ctk.StringVar(value=self.config.get("last_folder", ""))"""

init_inject = """        self.config = load_config()
        self.auth = AuthClient()
        self.input_dir = ctk.StringVar(value=self.config.get("last_folder", ""))"""

code = code.replace(init_search, init_inject)

start_search = """    def start_processing(self, new_only=False):
        if self.is_running: return

        self._save_current_config()"""

start_inject = """    def start_processing(self, new_only=False):
        if self.is_running: return
        
        # Security: Background Auth Check
        auth_status = self.auth.verify_session()
        if auth_status.get("status") == "INVALID_SESSION":
            self.log("Sesi berakhir: Akun digunakan di perangkat lain.", "error")
            import tkinter.messagebox
            tkinter.messagebox.showerror("Akses Ditolak", "Sesi berakhir: Akun aktif di perangkat lain atau tidak valid.")
            self.show_login_modal()
            return

        self._save_current_config()"""
code = code.replace(start_search, start_inject)

# 3. Method for login modal
modal_code = """
    def show_login_modal(self):
        self.withdraw()
        
        modal = ctk.CTkToplevel(self)
        modal.title("NRA Metadata - Auth")
        modal.geometry("400x500")
        modal.resizable(False, False)
        modal.configure(fg_color=C["bg"])
        modal.protocol("WM_DELETE_WINDOW", lambda: sys.exit(0))
        modal.attributes("-topmost", True)
        
        title_lbl = ctk.CTkLabel(modal, text="NRA METADATA", font=ctk.CTkFont(family="Inter", size=24, weight="bold"), text_color=C["text"])
        title_lbl.pack(pady=(40, 20))
        
        user_var = ctk.StringVar(value=self.auth.username)
        pass_var = ctk.StringVar()
        
        ctk.CTkLabel(modal, text="Username", text_color=C["text"]).pack(anchor="w", padx=40, pady=(0, 5))
        user_entry = ctk.CTkEntry(modal, textvariable=user_var, width=320)
        user_entry.pack(padx=40, pady=(0, 15))
        
        ctk.CTkLabel(modal, text="Password", text_color=C["text"]).pack(anchor="w", padx=40, pady=(0, 5))
        pass_entry = ctk.CTkEntry(modal, textvariable=pass_var, show="*", width=320)
        pass_entry.pack(padx=40, pady=(0, 20))
        
        status_lbl = ctk.CTkLabel(modal, text="", text_color=C["error"])
        status_lbl.pack(pady=(0, 10))
        
        def on_login():
            status_lbl.configure(text="Logging in...", text_color=C["muted"])
            modal.update()
            u = user_var.get().strip()
            p = pass_var.get().strip()
            if not u or not p:
                status_lbl.configure(text="Isi username dan password", text_color=C["error"])
                return
            res = self.auth.login(u, p)
            if res.get("status") == "SUCCESS":
                modal.destroy()
                self.deiconify()
                self.log(f"Login sukses sebagai {u}", "success")
            else:
                status_lbl.configure(text=res.get("message", "Error login"), text_color=C["error"])
                
        def on_register():
            status_lbl.configure(text="Mendaftarkan akun...", text_color=C["muted"])
            modal.update()
            u = user_var.get().strip()
            p = pass_var.get().strip()
            if not u or not p:
                status_lbl.configure(text="Isi username dan password", text_color=C["error"])
                return
            res = self.auth.register(u, p)
            if res.get("status") == "SUCCESS":
                status_lbl.configure(text="Registrasi sukses, silakan login.", text_color=C["success"])
            else:
                status_lbl.configure(text=res.get("message", "Error registrasi"), text_color=C["error"])
                
        def on_demo():
            modal.destroy()
            self.deiconify()
            self.log("Masuk ke Setup / Demo Mode", "warning")
            
        login_btn = ctk.CTkButton(modal, text="Login", fg_color=C["primary"], hover_color=C["primary_hover"], command=on_login)
        login_btn.pack(pady=(0, 10), padx=40, fill="x")
        
        reg_btn = ctk.CTkButton(modal, text="Register", fg_color=C["surface"], hover_color=C["border"], text_color=C["text"], command=on_register)
        reg_btn.pack(pady=(0, 10), padx=40, fill="x")
        
        if not self.auth.is_setup():
            demo_btn = ctk.CTkButton(modal, text="Demo Mode (Unconfigured)", fg_color="transparent", border_width=1, border_color=C["border"], text_color=C["muted"], command=on_demo)
            demo_btn.pack(pady=(10, 0), padx=40, fill="x")
            status_lbl.configure(text="Endpoint Auth belum dikonfigurasi.", text_color=C["muted"])
            
        modal.grab_set()

    def run(self):
"""

code = code.replace("    def run(self):", modal_code)

init_check_code = """
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Initial Auth Check
        self.after(100, self._check_initial_auth)
        
    def _check_initial_auth(self):
        auth_status = self.auth.verify_session()
        if auth_status.get("status") not in ["SUCCESS"]:
            self.show_login_modal()
"""
code = code.replace("        self.protocol(\"WM_DELETE_WINDOW\", self._on_closing)", init_check_code)

with open('apps/desktop/src/main.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Auth patched successfully!")