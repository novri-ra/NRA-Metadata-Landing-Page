import os
import sys
import json
import ctypes
import ctypes.wintypes
from pathlib import Path

CONFIG_FILE = os.path.join(os.getcwd(), "config.json")
CONFIG_FILE_ENC = os.path.join(os.getcwd(), "config.enc")

class DATA_BLOB(ctypes.Structure):
    _fields_ = [('cbData', ctypes.wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]

def _dpapi_encrypt(data: bytes) -> bytes:
    if sys.platform != 'win32': raise RuntimeError("DPAPI encryption requires Windows")
    try:
        crypt32 = ctypes.windll.crypt32
        blob_in = DATA_BLOB(len(data), ctypes.cast(data, ctypes.POINTER(ctypes.c_char)))
        blob_out = DATA_BLOB()
        if crypt32.CryptProtectData(ctypes.byref(blob_in), None, None, None, None, 1, ctypes.byref(blob_out)):
            res = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return res
    except Exception as e:
        raise RuntimeError(f"CryptProtectData exception: {e}")
    raise RuntimeError("CryptProtectData failed")

def _dpapi_decrypt(data: bytes) -> bytes:
    if sys.platform != 'win32': raise RuntimeError("DPAPI decryption requires Windows")
    try:
        crypt32 = ctypes.windll.crypt32
        blob_in = DATA_BLOB(len(data), ctypes.cast(data, ctypes.POINTER(ctypes.c_char)))
        blob_out = DATA_BLOB()
        if crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 1, ctypes.byref(blob_out)):
            res = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return res
    except Exception as e:
        raise RuntimeError(f"CryptUnprotectData exception: {e}")
    raise RuntimeError("CryptUnprotectData failed")

def load_config() -> dict:
    # Migrate old plain config.json if exists
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Remove plain config and save as encrypted
            save_config(data)
            try: os.remove(CONFIG_FILE)
            except: pass
            return data if isinstance(data, dict) else {}
        except Exception:
            pass

    if os.path.exists(CONFIG_FILE_ENC):
        try:
            with open(CONFIG_FILE_ENC, 'rb') as f:
                enc_data = f.read()
            dec_data = _dpapi_decrypt(enc_data)
            data = json.loads(dec_data.decode('utf-8'))
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
    else:
        data = {}

    # Sanitize 9router and invalid providers
    valid_providers = ["Gemini", "Mistral", "Groq", "OpenAI"]
    provider = data.get("provider")
    if not provider or provider not in valid_providers or provider == "9router":
        data["provider"] = "Gemini"
        data["model"] = "gemini-2.5-flash"
    
    # Sanitize api_keys dictionary
    api_keys = data.get("api_keys", {})
    if isinstance(api_keys, dict) and "9router" in api_keys:
        api_keys.pop("9router")
    data["api_keys"] = api_keys
    
    return data

def save_config(config: dict):
    try:
        json_data = json.dumps(config).encode('utf-8')
        enc_data = _dpapi_encrypt(json_data)
        with open(CONFIG_FILE_ENC, 'wb') as f:
            f.write(enc_data)
    except Exception as e:
        print(f"Error saving encrypted config: {e}")
