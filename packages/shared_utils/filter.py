import os
import re

BLACKLIST_FILE = os.path.join(os.getcwd(), "blacklist.txt")
_blacklist = set()


def _load_blacklist() -> set:
    bl = {"apple", "nike", "disney", "photoshop", "lego", "coca cola"}
    if os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE, "r", encoding="utf-8") as f:
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
    _blacklist = get_blacklist()
    w = word.strip().lower()
    if w in _blacklist:
        _blacklist.remove(w)
    _save_blacklist()


def _save_blacklist():
    # Save custom ones out, we don't necessarily have to separate built-ins, just dump all
    with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
        f.writelines(f"{w}\n" for w in sorted(get_blacklist()))


def filter_text(text: str) -> str:
    if not text:
        return text
    bl = get_blacklist()
    for word in bl:
        text = re.sub(rf"\b{re.escape(word)}\b", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def sanitize_keywords(keywords: list[str], max_kw: int = 50) -> list[str]:
    seen = set()
    cleaned = []
    for kw in keywords:
        kw_clean = re.sub(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$", "", kw).strip()
        if not kw_clean:
            continue

        filtered = filter_text(kw_clean)
        if not filtered:
            continue

        kw_lower = filtered.lower()
        if kw_lower not in seen:
            seen.add(kw_lower)
            cleaned.append(filtered)
            if len(cleaned) >= max_kw:
                break
    return cleaned


def _context_keyword_candidates(text: str, existing: set, needed: int) -> list[str]:
    """Derive keyword candidates from title/description content words.

    Falls back to contextual terms from the AI's own prose when the AI's
    keyword list comes up short, so a thin keyword array still reaches the
    target count instead of being truncated by the min_kw floor.
    """
    seen_phrase = {k.lower() for k in existing}
    candidates = []
    for tok in re.split(r"[^a-zA-Z0-9']+", text.lower()):
        tok = tok.strip("'").strip()
        if len(tok) < 3 or not re.search(r"[a-zA-Z]", tok):
            continue
        if tok in seen_phrase or tok in _COMMON_WORDS:
            continue
        if not filter_text(tok):
            continue
        seen_phrase.add(tok)
        candidates.append(tok)
        if len(candidates) >= needed:
            break
    return candidates


def clean_metadata(meta: dict, max_kw: int = 50, min_kw: int = 0) -> dict:
    title = filter_text(meta.get("title", ""))
    description = filter_text(meta.get("description", ""))
    keywords = sanitize_keywords(meta.get("keywords", []), max_kw)
    if min_kw and len(keywords) < min_kw and len(keywords) < max_kw:
        needed = min(min_kw, max_kw) - len(keywords)
        context = f"{title} {description}"
        keywords += _context_keyword_candidates(context, set(keywords), needed)
    return {
        "title": title,
        "description": description,
        "category": filter_text(meta.get("category", "")),
        "keywords": keywords,
    }


PLATFORM_RULES = {
    "Adobe Stock": {
        "title_max_chars": 200,
        "title_min_words": 3,
        "desc_min_words": 5,
        "desc_max_chars": 200,
        "kw_min": 5,
        "kw_max": 49,
    },
    "Shutterstock": {
        "title_max_chars": 150,
        "title_min_words": 5,
        "desc_min_words": 5,
        "desc_max_chars": 200,
        "kw_min": 7,
        "kw_max": 50,
    },
    "Freepik": {
        "title_max_chars": 100,
        "title_min_words": 3,
        "desc_min_words": 5,
        "desc_max_chars": 200,
        "kw_min": 5,
        "kw_max": 50,
    },
    "Vecteezy": {
        "title_max_chars": 150,
        "title_min_words": 3,
        "desc_min_words": 5,
        "desc_max_chars": 200,
        "kw_min": 5,
        "kw_max": 50,
    },
}


def validate_compliance(title: str, keywords: list[str], platform: str) -> dict:
    rules = PLATFORM_RULES.get(platform)
    if not rules:
        return {"valid": True, "errors": []}

    errors = []

    # Title validation
    if len(title) > rules["title_max_chars"]:
        errors.append(f"Title exceeds {rules['title_max_chars']} chars")

    word_count = len([w for w in title.split() if w.strip()])
    if word_count < rules["title_min_words"]:
        errors.append(f"Title has {word_count} words (min {rules['title_min_words']})")

    # Description validation
    if "desc_min_words" in rules:
        len(
            [w for w in (title or "").split() if w.strip()]
        )  # reuse title if desc not passed
        # Note: validate_compliance doesn't receive desc, so this is future-ready

    # Keywords validation
    kw_count = len(keywords)
    if kw_count < rules["kw_min"]:
        errors.append(f"Has {kw_count} keywords (min {rules['kw_min']})")
    elif kw_count > rules["kw_max"]:
        errors.append(f"Has {kw_count} keywords (max {rules['kw_max']})")

    return {"valid": len(errors) == 0, "errors": errors}


def autofix_compliance(
    title: str, keywords: list[str], platform: str
) -> tuple[str, list[str]]:
    rules = PLATFORM_RULES.get(platform)
    if not rules:
        return title, keywords

    # Detect fallback metadata - cannot be fixed by string manipulation
    _is_fallback = (
        title == "Unknown Title"
        or any(k.lower() in ("error", "fallback") for k in keywords)
        or len(keywords) < rules.get("kw_min", 5)
    )
    if _is_fallback:
        print(
            "[WARN] Auto-fix skipped: metadata is AI fallback/error. Re-generate from AI instead."
        )
        return title, keywords

    # Fix Title
    fixed_title = title
    if len(fixed_title) > rules["title_max_chars"]:
        # truncate while keeping whole words if possible
        fixed_title = fixed_title[: rules["title_max_chars"]].rsplit(" ", 1)[0]
        # fallback if single word was > max chars
        if len(fixed_title) > rules["title_max_chars"]:
            fixed_title = fixed_title[: rules["title_max_chars"]]

    # Fix Keywords
    fixed_keywords = list(keywords)
    if platform == "Freepik":
        # Freepik only letters and spaces
        fixed_keywords = [re.sub(r"[^a-zA-Z\s]", "", k).strip() for k in fixed_keywords]
        fixed_keywords = [k for k in fixed_keywords if k]

    if len(fixed_keywords) > rules["kw_max"]:
        fixed_keywords = fixed_keywords[: rules["kw_max"]]

    return fixed_title, fixed_keywords


# ── Case Formatting Utilities ─────────────────────────────────────────────
_TITLE_CASE_MINOR = {
    "a",
    "an",
    "the",
    "and",
    "but",
    "or",
    "nor",
    "for",
    "yet",
    "so",
    "in",
    "on",
    "at",
    "to",
    "by",
    "of",
    "up",
    "as",
    "is",
    "if",
    "it",
    "with",
    "from",
    "into",
    "over",
    "after",
    "between",
    "under",
    "about",
}


def to_title_case(text: str) -> str:
    """Capitalize first letter of each word, except minor words (unless first/last), preserving internal uppercase."""
    if not text:
        return text
    words = text.split()
    result = []
    for i, w in enumerate(words):
        if i == 0 or i == len(words) - 1 or w.lower() not in _TITLE_CASE_MINOR:
            result.append(w[0].upper() + w[1:] if w else "")
        else:
            result.append(w.lower())
    return " ".join(result)


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
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$", "", text).strip()
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

        # Plurals
        if w.endswith("ies") and len(w) > 5:
            return w[:-3] + "y"
        if (
            w.endswith("es")
            and len(w) > 4
            and not w.endswith("hes")
            and not w.endswith("sses")
            and w[-3] not in "aeiou"
        ):
            return w[:-2]
        if w.endswith("s") and len(w) > 3 and not w.endswith("ss"):
            return w[:-1]

        # Gerunds
        if w.endswith("ing") and len(w) > 5:
            stem = w[:-3]
            # Handle doubled consonant (but not doubled vowels like 'ee' in treeing)
            if len(stem) >= 2 and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
                stem = stem[:-1]
            return stem

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
    for kws in groups.values():
        # Keep the shortest by length
        kept = min(kws, key=len)
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


# ── Metadata Quality & Spam Score ─────────────────────────────────────
_COMMON_WORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "is",
    "it",
    "as",
    "be",
    "are",
    "was",
    "this",
    "that",
    "not",
    "no",
    "so",
    "if",
    "up",
    "out",
    "do",
    "has",
}

_SPAM_WORDS = {
    "best",
    "free",
    "amazing",
    "incredible",
    "awesome",
    "perfect",
    "ultimate",
    "exclusive",
    "guaranteed",
    "viral",
    "trending",
    "click",
    "buy",
    "cheap",
    "discount",
    "sale",
    "offer",
    "#1",
}


def calculate_quality_score(title: str, description: str, keywords: list) -> dict:
    """
    Returns dict with:
      score: 0-100
      issues: list of strings describing problems
    """
    # Detect fallback/error metadata early
    if title == "Unknown Title" or "generation failed" in (description or "").lower():
        return {
            "score": 0,
            "status": "Error — Fallback Metadata",
            "issues": ["Metadata generation failed — AI fallback detected"],
        }
    if isinstance(keywords, list) and (
        {k.lower() for k in keywords} == {"error", "fallback"}
        or "error" in [k.lower() for k in keywords]
    ):
        return {
            "score": 0,
            "status": "Error — Fallback Metadata",
            "issues": ["Metadata generation failed — AI fallback detected"],
        }

    issues = []
    points = 0
    max_points = 0

    # ── Title quality (30 pts) ──
    max_points += 30
    title_words = title.split() if title else []
    tw_count = len(title_words)
    if tw_count == 0:
        issues.append("Title is empty")
    elif tw_count < 3:
        issues.append("Title too short (< 3 words)")
        points += 10
    elif tw_count > 25:
        issues.append("Title too long (> 25 words)")
        points += 15
    else:
        points += 30

    # Check title word repetition
    if tw_count > 0:
        title_lower = [w.lower() for w in title_words]
        unique_ratio = len(set(title_lower)) / len(title_lower)
        if unique_ratio < 0.6:
            issues.append("Too many repeated words in title")

    # ── Description quality (20 pts) ──
    max_points += 20
    desc_words = description.split() if description else []
    dw_count = len(desc_words)
    if dw_count == 0:
        issues.append("Description is empty")
    elif dw_count < 5:
        issues.append("Description too short (< 5 words)")
        points += 8
    elif dw_count > 200:
        issues.append("Description too long (> 200 words)")
        points += 12
    else:
        points += 20

    # ── Keyword count (20 pts) ──
    max_points += 20
    kw_count = len(keywords)
    if kw_count == 0:
        issues.append("No keywords")
    elif kw_count < 5:
        issues.append(f"Too few keywords ({kw_count}, min 5)")
        points += 5
    elif kw_count > 49:
        issues.append(f"Too many keywords ({kw_count}, max 49)")
        points += 10
    else:
        points += 20

    # ── Keyword variety (15 pts) ──
    max_points += 15
    if kw_count > 0:
        kw_lower = [k.lower().strip() for k in keywords]
        unique_kws = set(kw_lower)
        dup_count = kw_count - len(unique_kws)
        if dup_count > 0:
            issues.append(f"{dup_count} duplicate keyword(s)")
            points += 5
        else:
            points += 15

        # Check how many are just common/stop words
        common_kws = [k for k in kw_lower if k in _COMMON_WORDS]
        if len(common_kws) > kw_count * 0.3:
            issues.append("Too many generic/common keywords")

    # ── Spam detection (15 pts) ──
    max_points += 15
    spam_found = []
    all_text = (title + " " + description + " " + " ".join(keywords)).lower()
    for sw in _SPAM_WORDS:
        if sw in all_text:
            spam_found.append(sw)
    if spam_found:
        issues.append(f"Spammy words detected: {', '.join(spam_found[:5])}")
        points += max(0, 15 - len(spam_found) * 3)
    else:
        points += 15

    score = round((points / max_points) * 100) if max_points > 0 else 0
    if score >= 85:
        status = "Excellent"
    elif score >= 60:
        status = "Good"
    else:
        status = "Needs Improvement"
    return {"score": score, "status": status, "issues": issues}
