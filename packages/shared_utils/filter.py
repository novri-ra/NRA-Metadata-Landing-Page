import os
import re

BLACKLIST_FILE = os.path.join(os.getcwd(), "blacklist.txt")
_blacklist = set()

def _load_blacklist() -> set:
    bl = {"apple", "nike", "disney", "photoshop", "lego", "coca cola"}
    if os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE, 'r', encoding='utf-8') as f:
            bl.update(line.strip().lower() for line in f if line.strip())
    return bl

def get_blacklist() -> set:
    global _blacklist
    if not _blacklist:
        _blacklist = _load_blacklist()
    return _blacklist

def add_to_blacklist(words: list[str]):
    global _blacklist
    _blacklist = get_blacklist()
    for w in words:
        if w.strip():
            _blacklist.add(w.strip().lower())
    _save_blacklist()

def remove_from_blacklist(word: str):
    global _blacklist
    _blacklist = get_blacklist()
    w = word.strip().lower()
    if w in _blacklist:
        _blacklist.remove(w)
    _save_blacklist()

def _save_blacklist():
    global _blacklist
    # Save custom ones out, we don't necessarily have to separate built-ins, just dump all
    with open(BLACKLIST_FILE, 'w', encoding='utf-8') as f:
        for w in sorted(list(get_blacklist())):
            f.write(f"{w}\n")

def filter_text(text: str) -> str:
    if not text: return text
    bl = get_blacklist()
    for word in bl:
        text = re.sub(rf'\b{re.escape(word)}\b', '', text, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', text).strip()

def sanitize_keywords(keywords: list[str], max_kw: int = 50) -> list[str]:
    seen = set()
    cleaned = []
    for kw in keywords:
        kw_clean = re.sub(r'^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$', '', kw).strip()
        if not kw_clean: continue
        
        filtered = filter_text(kw_clean)
        if not filtered: continue
        
        kw_lower = filtered.lower()
        if kw_lower not in seen:
            seen.add(kw_lower)
            cleaned.append(filtered)
            if len(cleaned) >= max_kw:
                break
    return cleaned

def clean_metadata(meta: dict, max_kw: int = 50) -> dict:
    return {
        "title": filter_text(meta.get("title", "")),
        "description": filter_text(meta.get("description", "")),
        "category": filter_text(meta.get("category", "")),
        "keywords": sanitize_keywords(meta.get("keywords", []), max_kw)
    }