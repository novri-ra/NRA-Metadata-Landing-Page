import hashlib
import sys
import uuid

import requests
import urllib3

from backend.core.config_manager import load_config, save_config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

AUTH_API_URL = "https://script.google.com/macros/s/AKfycbw3Gqwu5Q31OJpr_Vyzq_8V5SaRsXR1RGeKXs-VI1M2MFeWIFTCoAk0P8RExl70S32G/exec"


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

    def _post(self, payload: dict) -> dict:
        try:
            res = requests.post(
                self.endpoint,
                json=payload,
                verify=True,
                timeout=10,
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
        except requests.exceptions.Timeout as e:
            print(f"[AUTH] Network timeout: {e!r}", file=sys.stderr)
            return {"status": "ERROR", "message": "Network timeout. Koneksi lambat.", "network": True}
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
        return self._post(
            {
                "action": "REGISTER",
                "username": username,
                "password": password,
                "email": email,
                "wa": wa,
                "fullname": fullname,
            }
        )

    def login(self, username, password):
        """Login via username OR email — backend handles lookup."""
        res = self._post(
            {
                "action": "LOGIN",
                "username": username,
                "password": password,
                "hwid": self.hwid,
                "ip": get_public_ip(),
            }
        )
        if res.get("status") == "SUCCESS":
            actual_user = res.get("username", username)
            self._save_session(actual_user, res.get("session_token"))
        elif (
            res.get("status") == "ERROR"
            and res.get("network")
            and self.session_token
            and (self.username == username or self.config.get("auth_email") == username)
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
                "username": self.username,
                "session_token": self.session_token,
                "hwid": self.hwid,
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
