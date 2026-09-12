"""Backend configuration & cache management.

Encrypted config persistence (DPAPI on Windows) and local metadata cache
(SQLite keyed by SHA-256 file hash). Merged from the former
``packages/shared_utils/config.py`` and ``packages/shared_utils/cache.py``
with the same public API so UI/CLI layers only need an import change.
"""

import ctypes
import ctypes.wintypes
import hashlib
import json
import os
import sqlite3
import sys

CONFIG_FILE = os.path.join(os.getcwd(), "config.json")
CONFIG_FILE_ENC = os.path.join(os.getcwd(), "config.enc")

DB_PATH = os.path.join(os.getcwd(), "cache.db")
cache_hits = 0


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _dpapi_encrypt(data: bytes) -> bytes:
    if sys.platform != "win32":
        raise RuntimeError("DPAPI encryption requires Windows")
    try:
        crypt32 = ctypes.windll.crypt32
        blob_in = DATA_BLOB(len(data), ctypes.cast(data, ctypes.POINTER(ctypes.c_char)))
        blob_out = DATA_BLOB()
        if crypt32.CryptProtectData(
            ctypes.byref(blob_in), None, None, None, None, 1, ctypes.byref(blob_out)
        ):
            res = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return res
    except (OSError, RuntimeError) as e:
        raise RuntimeError(f"CryptProtectData exception: {e}")
    raise RuntimeError("CryptProtectData failed")


def _dpapi_decrypt(data: bytes) -> bytes:
    if sys.platform != "win32":
        raise RuntimeError("DPAPI decryption requires Windows")
    try:
        crypt32 = ctypes.windll.crypt32
        blob_in = DATA_BLOB(len(data), ctypes.cast(data, ctypes.POINTER(ctypes.c_char)))
        blob_out = DATA_BLOB()
        if crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 1, ctypes.byref(blob_out)
        ):
            res = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return res
    except (OSError, RuntimeError) as e:
        raise RuntimeError(f"CryptUnprotectData exception: {e}")
    raise RuntimeError("CryptUnprotectData failed")


def load_config() -> dict:
    # Migrate old plain config.json if exists
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Remove plain config and save as encrypted
            save_config(data)
            try:
                os.remove(CONFIG_FILE)
            except OSError:
                pass
            return data if isinstance(data, dict) else {}
        except OSError:
            pass

    if os.path.exists(CONFIG_FILE_ENC):
        try:
            with open(CONFIG_FILE_ENC, "rb") as f:
                enc_data = f.read()
            dec_data = _dpapi_decrypt(enc_data)
            data = json.loads(dec_data.decode("utf-8"))
            if not isinstance(data, dict):
                data = {}
        except OSError:
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
        json_data = json.dumps(config).encode("utf-8")
        enc_data = _dpapi_encrypt(json_data)
        with open(CONFIG_FILE_ENC, "wb") as f:
            f.write(enc_data)
    except (OSError, RuntimeError) as e:
        print(f"Error saving encrypted config: {e}")


def _get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS metadata_cache (hash TEXT PRIMARY KEY, metadata TEXT)"
    )
    return conn


def get_file_hash(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def _is_invalid_cache_entry(data: dict) -> bool:
    """Return True if cached metadata is fallback/corrupted and should be evicted."""
    if data.get("is_fallback"):
        return True
    if data.get("title") == "Unknown Title":
        return True
    desc = data.get("description", "")
    if "Metadata generation failed" in desc:
        return True
    kw = data.get("keywords", [])
    if isinstance(kw, list):
        if len(kw) < 5:
            return True
        if any("fallback" in k.lower() for k in kw):
            return True
    return False


def get_cached_metadata(file_hash: str) -> dict | None:
    global cache_hits
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT metadata FROM metadata_cache WHERE hash = ?", (file_hash,)
        ).fetchone()
        if row:
            data = json.loads(row[0])
            if _is_invalid_cache_entry(data):
                conn.execute("DELETE FROM metadata_cache WHERE hash = ?", (file_hash,))
                return None
            cache_hits += 1
            return data
        return None


def set_cached_metadata(file_hash: str, metadata: dict):
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO metadata_cache (hash, metadata) VALUES (?, ?)",
            (file_hash, json.dumps(metadata)),
        )


def get_cache_hits() -> int:
    return cache_hits