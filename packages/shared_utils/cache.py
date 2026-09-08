import sqlite3
import hashlib
import json
import os

DB_PATH = os.path.join(os.getcwd(), "cache.db")
cache_hits = 0

def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS metadata_cache (hash TEXT PRIMARY KEY, metadata TEXT)")
    return conn

def get_file_hash(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
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
        row = conn.execute("SELECT metadata FROM metadata_cache WHERE hash = ?", (file_hash,)).fetchone()
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
        conn.execute("INSERT OR REPLACE INTO metadata_cache (hash, metadata) VALUES (?, ?)", (file_hash, json.dumps(metadata)))

def get_cache_hits() -> int:
    return cache_hits
