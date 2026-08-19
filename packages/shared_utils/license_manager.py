import os
import sys
import json
import uuid
import hashlib
import platform
import subprocess
import requests
import urllib3
from packages.shared_utils.config import load_config, save_config

# Disable insecure request warnings if user deliberately bypasses SSL, but default to strict verify
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_machine_hwid() -> str:
    """Generate a unique hardware ID binding for the machine."""
    components = []
    
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                guid = winreg.QueryValueEx(key, "MachineGuid")[0]
                components.append(guid)
        except Exception:
            pass
        
        try:
            cmd = 'wmic csproduct get uuid'
            out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode().split('\n')[1].strip()
            if out: components.append(out)
        except Exception:
            pass
            
    elif sys.platform == "darwin":
        try:
            out = subprocess.check_output(['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice']).decode()
            for line in out.split('\n'):
                if 'IOPlatformUUID' in line:
                    components.append(line.split('=')[-1].strip().replace('"', ''))
                    break
        except Exception:
            pass
            
    elif sys.platform.startswith("linux"):
        try:
            with open('/etc/machine-id', 'r') as f:
                components.append(f.read().strip())
        except Exception:
            pass
            
    # Fallback to python UUID MAC address
    if not components:
        components.append(str(uuid.getnode()))
        
    raw_id = "-".join(components)
    return hashlib.sha256(raw_id.encode()).hexdigest()

class AuthClient:
    def __init__(self):
        self.config = load_config()
        self.endpoint = self.config.get("auth_endpoint", "YOUR_GOOGLE_APPS_SCRIPT_WEBAPP_URL")
        self.username = self.config.get("auth_user", "")
        self.session_token = self.config.get("auth_session", "")
        self.hwid = get_machine_hwid()
        
    def _save_session(self, username, token):
        self.username = username
        self.session_token = token
        self.config["auth_user"] = username
        self.config["auth_session"] = token
        save_config(self.config)
        
    def _clear_session(self):
        self.username = ""
        self.session_token = ""
        self.config["auth_user"] = ""
        self.config["auth_session"] = ""
        save_config(self.config)
        
    def is_setup(self):
        return self.endpoint != "YOUR_GOOGLE_APPS_SCRIPT_WEBAPP_URL" and self.endpoint.startswith("https://")
        
    def _post(self, payload: dict) -> dict:
        if not self.is_setup():
            return {"status": "ERROR", "message": "Endpoint not configured. Running in Demo Mode."}
        try:
            res = requests.post(self.endpoint, json=payload, verify=True, timeout=10)
            return res.json()
        except requests.exceptions.RequestException as e:
            return {"status": "ERROR", "message": f"Network error: {str(e)}"}
        except ValueError:
            return {"status": "ERROR", "message": "Invalid response from server"}

    def register(self, username, password):
        res = self._post({"action": "REGISTER", "username": username, "password": password})
        return res

    def login(self, username, password):
        res = self._post({
            "action": "LOGIN", 
            "username": username, 
            "password": password, 
            "hwid": self.hwid,
            "ip": "auto"
        })
        if res.get("status") == "SUCCESS":
            self._save_session(username, res.get("session_token"))
        return res

    def verify_session(self) -> dict:
        if not self.is_setup():
            return {"status": "SUCCESS", "message": "Demo mode active"}
        if not self.username or not self.session_token:
            return {"status": "INVALID_SESSION", "message": "No active session"}
            
        res = self._post({
            "action": "VALIDATE_SESSION",
            "username": self.username,
            "session_token": self.session_token,
            "hwid": self.hwid
        })
        
        if res.get("status") == "INVALID_SESSION":
            self._clear_session()
        return res

    def logout(self):
        if self.is_setup() and self.username and self.session_token:
            self._post({
                "action": "LOGOUT",
                "username": self.username,
                "session_token": self.session_token
            })
        self._clear_session()
