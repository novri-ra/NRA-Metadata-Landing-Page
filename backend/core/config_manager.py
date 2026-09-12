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

import ctypes
import ctypes.wintypes
import hashlib
import json
import os
import sqlite3
import sys

cache_hits = 0

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