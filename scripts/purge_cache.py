"""One-shot script to purge corrupted/fallback records from cache.db."""
import sqlite3, os, json

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache.db")

def _is_invalid(metadata_json: str) -> bool:
    try:
        d = json.loads(metadata_json)
    except Exception:
        return True
    if d.get("is_fallback"):
        return True
    if d.get("title") == "Unknown Title":
        return True
    desc = d.get("description", "")
    if "Metadata generation failed" in desc:
        return True
    kw = d.get("keywords", [])
    if isinstance(kw, list) and (len(kw) < 5 or any("fallback" in k.lower() for k in kw)):
        return True
    if isinstance(kw, str) and ("fallback" in kw.lower()):
        return True
    return False

def main():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT hash, metadata FROM metadata_cache").fetchall()
    deleted = 0
    for h, m in rows:
        if _is_invalid(m):
            conn.execute("DELETE FROM metadata_cache WHERE hash = ?", (h,))
            deleted += 1
    conn.commit()
    remaining = conn.execute("SELECT COUNT(*) FROM metadata_cache").fetchone()[0]
    conn.close()
    print(f"Purged {deleted} invalid record(s). Remaining: {remaining}")

if __name__ == "__main__":
    main()
