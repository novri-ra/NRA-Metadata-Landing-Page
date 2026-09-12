import hashlib
import sys
import uuid

import requests
import urllib3

from backend.core.config_manager import load_config, save_config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

AUTH_API_URL = "https://script.google.com/macros/s/AKfycbx53YwYauTCoda5MrigOUyP9vsDBmw2VOOR3-dz1H7vdfG4JAM_3Zo_AOLe9UbZdJ8/exec"


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

    def _save_session(self, username, token, user_id=None):
        self.username = username
        self.session_token = token
        self.config["auth_user"] = username
        self.config["auth_session"] = token
        if user_id:
            self.config["auth_user_id"] = str(user_id)
        save_config(self.config)

    def _clear_session(self):
        self.username = ""
        self.session_token = ""
        self.config["auth_user"] = ""
        self.config["auth_session"] = ""
        save_config(self.config)

    def _post(self, payload: dict) -> dict:
        try:
            res = self.session.post(
                self.endpoint,
                json=payload,
                verify=True,
                timeout=(15.0, 45.0),
                allow_redirects=True,
            )
            try:
                return res.json()
            except ValueError as e:
                print(
                    f"[AUTH] Non-JSON response (HTTP {res.status_code}): {res.text[:200]}",
                    file=sys.stderr,
                )
                return {"status": "ERROR", "message": "Respon server tidak valid."}
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

    def register(self, username, password):
        clean_user = str(username).strip().lower()
        return self._post(
            {
                "action": "REGISTER",
                "identifier": clean_user,
                "username": clean_user,
                "password": str(password),
                "hwid": self.get_hwid(),
                "ip": self.get_client_ip(),
            }
        )

    def login(self, identifier, password):
        """Login via username — backend handles lookup."""
        clean_user = str(identifier).strip().lower()
        res = self._post(
            {
                "action": "LOGIN",
                "identifier": clean_user,
                "username": clean_user,
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
            # Offline tolerance if credentials already match the saved session
            return {"status": "SUCCESS", "username": self.username, "session_token": self.session_token, "message": "Offline mode"}
        return res

    def validate_session(self) -> tuple[bool, str]:
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
            }
        )

        status = res.get("status")
        msg = res.get("message", "Error")

        if status in ["SUCCESS", "VALID"]:
            return True, msg
        elif status == "INVALID_SESSION" or status == "KICKED":
            self._clear_session()
            return False, "KICKED"
        elif status == "ERROR" and res.get("network"):
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
