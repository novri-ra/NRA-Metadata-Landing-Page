"""Backend configuration & cache management.

Encrypted config persistence (DPAPI on Windows) and local metadata cache
(SQLite keyed by SHA-256 file hash). Merged from the former
``packages/shared_utils/config.py`` and ``packages/shared_utils/cache.py``
with the same public API so UI/CLI layers only need an import change.

Storage location is configurable and mirrors the reference application's
convention: on Windows it defaults to ``%USERPROFILE%\\Documents\\NRA
Metadata`` (the reference stores its own data in ``Documents\\RJ Auto
Metadata``). Override with ``set_config_dir()`` or the ``NRA_CONFIG_DIR``
environment variable; non-Windows falls back to the current directory.
"""

import base64
import ctypes
import ctypes.wintypes
import hashlib
import json
import os
import sqlite3
import sys

cache_hits = 0

# Obfuscated-config fallback for platforms without DPAPI.
_OBFUSCATION_TAG = b"NRA_OBF_1:"
_XOR_KEY = b"NRA!meta"
_DPAPI_HEADER = b"\x01\x00\x00\x00"

# RJ Auto Metadata (reference application) keeps its plaintext config under
# the user's Documents folder. NRA-Metadata keeps the same provider API keys
# but stores them encrypted.
_RJ_DOCS_FOLDER = "RJ Auto Metadata"
_NRA_DOCS_FOLDER = "NRA Metadata"
_RJ_PROVIDER_MAPPING = {"Gemini", "OpenAI", "Groq", "Mistral"}


def _default_data_dir():
    """Resolve where the encrypted config/cache should live."""
    env_dir = os.environ.get("NRA_CONFIG_DIR")
    if env_dir:
        return env_dir
    if sys.platform == "win32":
        profile = os.environ.get("USERPROFILE")
        if profile:
            docs = os.path.join(profile, "Documents", _NRA_DOCS_FOLDER)
            try:
                os.makedirs(docs, exist_ok=True)
            except OSError:
                return os.getcwd()
            return docs
    return os.getcwd()


def set_config_dir(path=None) -> str:
    """Point config/cache storage at an explicit directory. Returns the dir.

    Defaults to the platform data dir (``Documents\\NRA Metadata`` on
    Windows, current directory elsewhere) unless ``NRA_CONFIG_DIR`` is set.
    """
    global CONFIG_FILE, CONFIG_FILE_ENC, DB_PATH
    data_dir = path or _default_data_dir()
    os.makedirs(data_dir, exist_ok=True)
    CONFIG_FILE = os.path.join(data_dir, "config.json")
    CONFIG_FILE_ENC = os.path.join(data_dir, "config.enc")
    DB_PATH = os.path.join(data_dir, "cache.db")
    return data_dir


def get_config_dir() -> str:
    return os.path.dirname(CONFIG_FILE)


set_config_dir()


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


def _obfuscate(data: bytes) -> bytes:
    """XOR + base64 so config still persists on non-Windows hosts.

    ponytail: obfuscation, not encryption — swap for a keyring integration
    when non-Windows persistence becomes a real deployment target.
    """
    xored = bytes(b ^ _XOR_KEY[i % len(_XOR_KEY)] for i, b in enumerate(data))
    return _OBFUSCATION_TAG + base64.b64encode(xored)


def _deobfuscate(data: bytes) -> bytes:
    xored = base64.b64decode(data[len(_OBFUSCATION_TAG):])
    return bytes(b ^ _XOR_KEY[i % len(_XOR_KEY)] for i, b in enumerate(xored))


def _decrypt_store(raw: bytes) -> dict:
    """Decode config.enc regardless of how it was written.

    Accepts obfuscated (non-Windows) stores, legacy plaintext JSON, and
    real DPAPI blobs so old/misplaced plaintext configs keep loading.
    """
    if raw.startswith(_OBFUSCATION_TAG):
        dec = _deobfuscate(raw)
    elif sys.platform == "win32" and raw.startswith(_DPAPI_HEADER):
        dec = _dpapi_decrypt(raw)
    else:
        dec = raw
    data = json.loads(dec.decode("utf-8"))
    return data if isinstance(data, dict) else {}


def load_config() -> dict:
    # Migrate old plain config.json if exists
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Remove plain config only once encrypted save succeeded
            if save_config(data):
                try:
                    os.remove(CONFIG_FILE)
                except OSError:
                    pass
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            pass

    if os.path.exists(CONFIG_FILE_ENC):
        try:
            with open(CONFIG_FILE_ENC, "rb") as f:
                enc_data = f.read()
            data = _decrypt_store(enc_data)
        except (OSError, RuntimeError, ValueError) as e:
            print(f"Warning: could not read config store: {e}")
            data = {}
    else:
        data = {}

    # Sanitize invalid providers
    valid_providers = ["Gemini", "Mistral", "Groq", "OpenAI", "Custom"]
    provider = data.get("provider")
    if not provider or provider not in valid_providers:
        data["provider"] = "Gemini"
        data["model"] = "gemini-2.5-flash"

    # Deprecated model normalisation
    if data.get("provider") == "Gemini" and data.get("model") == "gemini-2.5-pro":
        data["model"] = "gemini-2.5-flash"
    if data.get("model") == "9router/auto":
        data["model"] = "gpt-4o-mini"

    return data


def save_config(config: dict) -> bool:
    try:
        json_data = json.dumps(config).encode("utf-8")
        if sys.platform == "win32":
            enc_data = _dpapi_encrypt(json_data)
        else:
            enc_data = _obfuscate(json_data)
        atomic_write_bytes(CONFIG_FILE_ENC, enc_data)
        return True
    except (OSError, RuntimeError) as e:
        print(f"Error saving encrypted config: {e}")
        return False


def atomic_write_bytes(path: str, data: bytes) -> None:
    """Write via temp file + fsync + ``os.replace`` so a crash mid-write never
    truncates the real store (config.enc / presets / exported CSVs)."""
    tmp = f"{path}.tmp"
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def atomic_write_text(path: str, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def _get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
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


# ---------------------------------------------------------------------------
# RJ Auto Metadata interoperability
# ---------------------------------------------------------------------------


def find_rj_config(path=None) -> str | None:
    """Locate the reference application's plaintext config.json.

    Defaults to ``Documents\\RJ Auto Metadata\\config.json`` on Windows.
    Returns None when the file does not exist.
    """
    if path:
        return path if os.path.exists(path) else None
    if sys.platform == "win32":
        profile = os.environ.get("USERPROFILE")
        if profile:
            candidate = os.path.join(profile, "Documents", _RJ_DOCS_FOLDER, "config.json")
            if os.path.exists(candidate):
                return candidate
    return None


def import_rj_config(path=None, merge=True) -> dict:
    """Import API keys and model preferences from RJ Auto Metadata.

    Reads the reference app's plaintext ``config.json`` (unencrypted by
    design upstream) and merges provider keys into the encrypted NRA store.
    Keys already present in the NRA store are never overwritten unless
    ``merge=False``. Sensitive material only ever leaves/enters the NRA side
    through ``save_config`` (DPAPI-encrypted on Windows).

    Returns a summary dict with keys: ``imported``, ``source``,
    ``providers_added``, ``skipped_providers``, ``models``, ``hints``.
    """
    rj_path = find_rj_config(path)
    if not rj_path:
        return {"imported": False, "reason": "RJ Auto Metadata config.json not found"}
    try:
        with open(rj_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return {"imported": False, "reason": str(e)}
    if not isinstance(raw, dict):
        return {"imported": False, "reason": "RJ config malformed (not an object)"}

    cfg = load_config()
    api_keys = cfg.get("api_keys")
    if not isinstance(api_keys, dict):
        api_keys = {}

    by_provider = raw.get("api_keys_by_provider")
    if not isinstance(by_provider, dict):
        flat = raw.get("api_keys")
        by_provider = {"Gemini": flat} if isinstance(flat, list) else {}

    added, skipped = {}, []
    for provider, keys in by_provider.items():
        if not isinstance(keys, list) or not any(isinstance(k, str) and k for k in keys):
            continue
        if provider not in _RJ_PROVIDER_MAPPING:
            skipped.append(provider)
            continue
        current = api_keys.get(provider)
        if merge and current and str(current).strip():
            continue
        api_keys[provider] = "\n".join(k for k in keys if isinstance(k, str))
        added[provider] = sum(1 for k in keys if isinstance(k, str))
    cfg["api_keys"] = api_keys

    models = raw.get("models_by_provider", {})
    selected = raw.get("selected_model_by_provider", {})
    merged_models = {}
    for provider in _RJ_PROVIDER_MAPPING:
        if provider not in api_keys or not str(api_keys[provider]).strip():
            continue
        model = selected.get(provider)
        if not model and isinstance(models.get(provider), list) and models[provider]:
            model = models[provider][0]
        if model:
            merged_models[provider] = model

    hints = {}
    if raw.get("model"):
        hints["rj_default_model"] = raw["model"]
    if raw.get("priority"):
        hints["rj_priority"] = raw["priority"]
    if raw.get("keyword_count"):
        hints["rj_keyword_count"] = raw["keyword_count"]
    if raw.get("embedding"):
        hints["rj_embedding"] = raw["embedding"]
    if raw.get("custom_base_url"):
        hints["rj_custom_base_url"] = raw["custom_base_url"]

    provider = raw.get("provider")
    if provider in _RJ_PROVIDER_MAPPING and not cfg.get("provider"):
        cfg["provider"] = provider
        cfg["model"] = merged_models.get(provider) or raw.get("model", "")

    if merged_models:
        cfg.setdefault("models_by_provider", {}).update(merged_models)

    cfg.update({k: v for k, v in hints.items() if v not in (None, "")})
    save_config(cfg)

    return {
        "imported": True,
        "source": rj_path,
        "providers_added": added,
        "skipped_providers": skipped,
        "models": merged_models,
        "hints": hints,
    }