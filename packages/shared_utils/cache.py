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

def get_cached_metadata(file_hash: str) -> dict | None:
    global cache_hits
    with _get_conn() as conn:
        row = conn.execute("SELECT metadata FROM metadata_cache WHERE hash = ?", (file_hash,)).fetchone()
        if row:
            cache_hits += 1
            return json.loads(row[0])
        return None

def set_cached_metadata(file_hash: str, metadata: dict):
    with _get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO metadata_cache (hash, metadata) VALUES (?, ?)", (file_hash, json.dumps(metadata)))

def get_cache_hits() -> int:
    return cache_hits
