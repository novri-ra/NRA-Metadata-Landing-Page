import hashlib
import hmac
import sys
import time
import uuid
import os

import requests

from backend.core.config_manager import load_config, save_config

AUTH_API_URL = "https://script.google.com/macros/s/AKfycbyCQ_YsbTnjwgr1nBzPlOzyaiYv5BpfT6HDG72D9RsZRTAvK3axT5fagSV2we7Mkju9/exec"

OFFLINE_SESSION_MAX_AGE_SECONDS = 3 * 24 * 3600


def get_machine_hwid() -> str:
    components = []
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
            ) as key:
                guid = winreg.QueryValueEx(key, "MachineGuid")[0]
                components.append(guid)
        except OSError:
            pass
    if not components:
        components.append(str(uuid.getnode()))

    raw_id = "-".join(components)
    return hashlib.sha256(raw_id.encode()).hexdigest()


def get_public_ip() -> str:
    try:
        res = requests.get("https://api.ipify.org", timeout=3)
        if res.status_code == 200:
            return res.text.strip()
    except (requests.exceptions.RequestException, OSError):
        pass
    return "Unknown"


class AuthClient:
    def __init__(self):
        self.config = load_config()
        self.endpoint = AUTH_API_URL
        self.username = self.config.get("auth_user", "")
        self.session_token = self.config.get("auth_session", "")
        self.offline_mode = bool(self.config.get("auth_offline"))
        self.hwid = get_machine_hwid()

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def get_hwid(self) -> str:
        return self.hwid

    def get_client_ip(self) -> str:
        return get_public_ip()

    def _hwid_signature(self) -> str:
        return hmac.new(
            self.session_token.encode(), self.hwid.encode(), hashlib.sha256
        ).hexdigest()

    def _save_session(self, username, token, user_id=None):
        self.username = username
        self.session_token = token
        self.config["auth_user"] = username
        self.config["auth_session"] = token
        if user_id:
            self.config["auth_user_id"] = str(user_id)
        self._stamp_last_valid()
        save_config(self.config)

    def _clear_session(self):
        self.username = ""
        self.session_token = ""
        self.config["auth_user"] = ""
        self.config["auth_session"] = ""
        save_config(self.config)

    def _stamp_last_valid(self):
        self.config["auth_last_valid"] = str(int(time.time()))
        save_config(self.config)

    def _is_dev_mode(self) -> bool:
        # ponytail: Auto-Fallback Dev Mode
        if os.environ.get("DEBUG") == "1":
            return True
        if os.path.exists(".dev_mode"):
            return True
        return False

    def _offline_allowed(self) -> bool:
        raw = self.config.get("auth_last_valid")
        if not raw:
            return False
        try:
            ts = int(raw)
        except (TypeError, ValueError):
            return False
        return (time.time() - ts) <= OFFLINE_SESSION_MAX_AGE_SECONDS

    def _post(self, payload: dict) -> dict:
        try:
            res = self.session.post(
                self.endpoint,
                json=payload,
                verify=True,
                timeout=(15.0, 45.0),
                allow_redirects=True,
            )
            text = res.text
            content_type = res.headers.get("Content-Type", "").lower()
            if "text/html" in content_type or text.lstrip().startswith(
                ("<!DOCTYPE", "<html")
            ):
                print(
                    f"[AUTH ERROR] (HTTP {res.status_code}) Apps Script deployment "
                    "tidak menjawab dengan JSON: URL Web App salah atau belum "
                    "di-deploy dengan akses 'Anyone'. Server mengembalikan HTML.",
                    file=sys.stderr,
                )
                return {
                    "status": "ERROR",
                    "message": "Apps Script belum di-deploy sebagai Web App dengan akses 'Anyone' (atau URL salah). Gunakan Mode Offline.",
                    "network": True,
                }
            try:
                return res.json()
            except ValueError:
                print(
                    f"[AUTH ERROR] (HTTP {res.status_code}) Server Apps Script "
                    "mengembalikan respons yang bukan JSON. Periksa deployment "
                    "Web App (akses 'Anyone') dan URL yang digunakan.",
                    file=sys.stderr,
                )
                return {
                    "status": "ERROR",
                    "message": "Apps Script deployment misconfigured",
                    "network": True,
                }
        except requests.exceptions.ConnectTimeout as e:
            print(f"[AUTH] Connect timeout: {e!r}", file=sys.stderr)
            return {"status": "ERROR", "message": "Connect timeout. GAS redirect lambat.", "network": True}
        except requests.exceptions.ReadTimeout as e:
            print(f"[AUTH] Read timeout: {e!r}", file=sys.stderr)
            return {"status": "ERROR", "message": "Read timeout. Server tidak merespons.", "network": True}
        except requests.exceptions.SSLError as e:
            print(f"[AUTH] SSL error: {e!r}", file=sys.stderr)
            return {"status": "ERROR", "message": "SSL error: sertifikat tidak valid.", "network": True}
        except requests.exceptions.ConnectionError as e:
            cause = e.__cause__ or e
            print(
                f"[AUTH] Connection error: {type(cause).__name__}: {cause}",
                file=sys.stderr,
            )
            return {"status": "ERROR", "message": "Connection error.", "network": True}
        except requests.exceptions.RequestException as e:
            print(
                f"[AUTH] HTTP request error: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
            return {"status": "ERROR", "message": f"Request error: {type(e).__name__}", "network": True}
        except OSError as e:
            print(
                f"[AUTH] Network error: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
            return {"status": "ERROR", "message": f"Network error: {e!s}", "network": True}
        except Exception as e:
            print(
                f"[AUTH] Unexpected error: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
            return {"status": "ERROR", "message": f"Unexpected error: {e!s}", "network": True}

    def enable_offline_mode(self):
        self.offline_mode = True
        self.config["auth_offline"] = True
        save_config(self.config)

    def register(self, username, password, email="", wa="", fullname=""):
        clean_user = str(username).strip().lower()
        return self._post(
            {
                "action": "REGISTER",
                "identifier": clean_user,
                "username": clean_user,
                "password": str(password),
                "email": email,
                "whatsapp": wa,
                "full_name": fullname,
                "hwid": self.get_hwid(),
                "ip": self.get_client_ip(),
            }
        )

    def login(self, identifier, password):
        """Login via username ?" backend handles lookup."""
        if self._is_dev_mode():
            print("[DEV MODE] Bypassing login auth...", file=sys.stderr)
            self._save_session("dev_user", "dev_token_123", "dev_id_1")
            return {"status": "SUCCESS", "username": "dev_user", "session_token": "dev_token_123", "message": "Dev mode bypass"}

        clean_user = str(identifier).strip().lower()
        res = self._post(
            {
                "action": "LOGIN",
                "identifier": clean_user,
                "password": str(password),
                "hwid": self.get_hwid(),
                "ip": self.get_client_ip(),
            }
        )
        if res.get("status") == "SUCCESS":
            actual_user = res.get("username", clean_user)
            self._save_session(actual_user, res.get("session_token"), res.get("user_id"))
        elif (
            res.get("status") == "ERROR"
            and res.get("network")
            and self.session_token
            and (self.username == clean_user or self.config.get("auth_email") == clean_user)
        ):
            if not self._offline_allowed():
                return {
                    "status": "ERROR",
                    "message": "Offline session expired. Re-login required.",
                }
            # Offline tolerance if credentials already match the saved session
            return {"status": "SUCCESS", "username": self.username, "session_token": self.session_token, "message": "Offline mode"}
        return res

    def validate_session(self) -> tuple[bool, str]:
        if self._is_dev_mode():
            print("[DEV MODE] Bypassing session validation...", file=sys.stderr)
            return True, "Dev mode bypass"

        if self.offline_mode:
            return True, "Offline mode"
        if not self.username or not self.session_token:
            return False, "No active session"

        res = self._post(
            {
                "action": "VALIDATE_SESSION",
                "identifier": self.username.strip().lower(),
                "username": self.username.strip().lower(),
                "session_token": self.session_token,
                "hwid": self.get_hwid(),
                "hwid_sig": self._hwid_signature(),
            }
        )

        status = res.get("status")
        msg = res.get("message", "Error")

        if status in ["SUCCESS", "VALID"]:
            self._stamp_last_valid()
            return True, msg
        elif status == "INVALID_SESSION" or status == "KICKED":
            self._clear_session()
            return False, "KICKED"
        elif status == "ERROR" and res.get("network"):
            if not self._offline_allowed():
                return False, "Offline session expired"
            return True, "Offline mode"
        return False, msg

    def logout(self):
        if self.username and self.session_token:
            self._post(
                {
                    "action": "LOGOUT",
                    "username": self.username,
                    "session_token": self.session_token,
                }
            )
        self._clear_session()
