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

PLATFORM_RULES = {
    "Adobe Stock": {"title_max_chars": 200, "title_min_words": 1, "kw_min": 5, "kw_max": 49},
    "Shutterstock": {"title_max_chars": 150, "title_min_words": 5, "kw_min": 7, "kw_max": 50},
    "Freepik": {"title_max_chars": 100, "title_min_words": 1, "kw_min": 5, "kw_max": 50},
    "Vecteezy": {"title_max_chars": 150, "title_min_words": 1, "kw_min": 5, "kw_max": 50}
}

def validate_compliance(title: str, keywords: list[str], platform: str) -> dict:
    rules = PLATFORM_RULES.get(platform)
    if not rules: return {"valid": True, "errors": []}
    
    errors = []
    
    # Title validation
    if len(title) > rules["title_max_chars"]:
        errors.append(f"Title exceeds {rules['title_max_chars']} chars")
    
    word_count = len([w for w in title.split() if w.strip()])
    if word_count < rules["title_min_words"]:
        errors.append(f"Title has {word_count} words (min {rules['title_min_words']})")
    
    # Keywords validation
    kw_count = len(keywords)
    if kw_count < rules["kw_min"]:
        errors.append(f"Has {kw_count} keywords (min {rules['kw_min']})")
    elif kw_count > rules["kw_max"]:
        errors.append(f"Has {kw_count} keywords (max {rules['kw_max']})")
        
    return {"valid": len(errors) == 0, "errors": errors}

def autofix_compliance(title: str, keywords: list[str], platform: str) -> tuple[str, list[str]]:
    rules = PLATFORM_RULES.get(platform)
    if not rules: return title, keywords
    
    # Fix Title
    fixed_title = title
    if len(fixed_title) > rules["title_max_chars"]:
        # truncate while keeping whole words if possible
        fixed_title = fixed_title[:rules["title_max_chars"]].rsplit(' ', 1)[0]
        # fallback if single word was > max chars
        if len(fixed_title) > rules["title_max_chars"]:
            fixed_title = fixed_title[:rules["title_max_chars"]]
            
    # Fix Keywords
    fixed_keywords = list(keywords)
    if platform == "Freepik":
        # Freepik only letters and spaces
        fixed_keywords = [re.sub(r'[^a-zA-Z\s]', '', k).strip() for k in fixed_keywords]
        fixed_keywords = [k for k in fixed_keywords if k]
        
    if len(fixed_keywords) > rules["kw_max"]:
        fixed_keywords = fixed_keywords[:rules["kw_max"]]
        
    return fixed_title, fixed_keywords

# ── Case Formatting Utilities ─────────────────────────────────────────────
_TITLE_CASE_MINOR = {
    'a', 'an', 'the', 'and', 'but', 'or', 'nor', 'for', 'yet', 'so',
    'in', 'on', 'at', 'to', 'by', 'of', 'up', 'as', 'is', 'if', 'it',
    'with', 'from', 'into', 'over', 'after', 'between', 'under', 'about',
}

def to_title_case(text: str) -> str:
    """Capitalize first letter of each word, except minor words (unless first/last), preserving internal uppercase."""
    if not text:
        return text
    words = text.split()
    result = []
    for i, w in enumerate(words):
        if i == 0 or i == len(words) - 1 or w.lower() not in _TITLE_CASE_MINOR:
            result.append(w[0].upper() + w[1:] if w else '')
        else:
            result.append(w.lower())
    return ' '.join(result)

def to_sentence_case(text: str) -> str:
    """Capitalize only the first character of the string, preserving rest of casing."""
    if not text:
        return text
    return text[0].upper() + text[1:]

def to_uppercase(text: str) -> str:
    return text.upper() if text else text

def to_lowercase(text: str) -> str:
    return text.lower() if text else text

def lowercase_keywords(keywords: list[str]) -> list[str]:
    """Lowercase all keywords for microstock consistency."""
    return [k.lower() for k in keywords]

def trim_spacing(text: str) -> str:
    """Remove double spaces and invalid non-alphanumeric edge characters."""
    if not text:
        return text
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$', '', text).strip()
    return text

def trim_keywords(keywords: list[str]) -> list[str]:
    """Trim spacing on each keyword."""
    return [trim_spacing(k) for k in keywords if trim_spacing(k)]

def detect_redundant_keywords(keywords: list[str]) -> dict[str, list[str]]:
    """
    Detects similar keywords using simple stemming (plurals, -ing, -er).
    Returns a dict mapping a root form to the list of duplicate variations.
    """
    groups = {}
    
    def simple_stem(word: str) -> str:
        w = word.lower().strip()
        # Longer suffixes first (need longer word)
        if len(w) > 5:
            if w.endswith('ies'): return w[:-3] + 'y'
            if w.endswith('ing'):
                stem = w[:-3]
                # Handle doubled consonant: running -> runn -> run
                if len(stem) >= 2 and stem[-1] == stem[-2]:
                    stem = stem[:-1]
                return stem
            if w.endswith('tion'): return w[:-4]
        if len(w) > 4:
            if w.endswith('es'): return w[:-2]
            if w.endswith('er'): return w[:-2]
            if w.endswith('ed'): return w[:-2]
        # Simple plural: word > 3 chars and ends with 's' (not 'ss')
        if len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
            return w[:-1]
        return w

    for kw in keywords:
        root = simple_stem(kw)
        if root not in groups:
            groups[root] = []
        groups[root].append(kw)

    # Return only groups with >1 item
    return {root: kws for root, kws in groups.items() if len(kws) > 1}

def remove_redundant_keywords(keywords: list[str]) -> list[str]:
    """
    Given a list of keywords, keep only the shortest form from each redundancy group
    and maintain the original order for the first occurrence.
    """
    groups = detect_redundant_keywords(keywords)
    # Map each keyword to its kept form
    keep_map = {}
    for root, kws in groups.items():
        # Keep the shortest by length
        kept = sorted(kws, key=len)[0]
        for k in kws:
            keep_map[k] = kept
    
    seen = set()
    cleaned = []
    for kw in keywords:
        actual_kw = keep_map.get(kw, kw)
        if actual_kw.lower() not in seen:
            seen.add(actual_kw.lower())
            cleaned.append(actual_kw)
            
    return cleaned


def clean_metadata(meta: dict, max_kw: int = 50) -> dict:
    return {
        "title": filter_text(meta.get("title", "")),
        "description": filter_text(meta.get("description", "")),
        "category": filter_text(meta.get("category", "")),
        "keywords": sanitize_keywords(meta.get("keywords", []), max_kw)
    }