import csv
import os
import re

from packages.shared_utils.taxonomy import get_adobe_category_code


def sanitize_text(s: str, semi: str = ",") -> str:
    if not s:
        return ""
    s = re.sub(r"[\r\n\t]+", " ", s)
    s = s.replace('"', "'")
    if semi is not None:
        s = s.replace(";", semi)
    return s.strip()


def fmt_str(s: str, max_len: int, min_len: int = 0, semi: str = ",") -> str:
    s = sanitize_text(s, semi)
    if len(s) < min_len:
        s = s.ljust(min_len, ".")
    if len(s) <= max_len:
        return s
    idx = s.rfind(" ", 0, max_len)
    if idx > 0:
        return s[:idx]
    return s[:max_len]


def fmt_desc(s: str, max_len: int = 2000, semi: str = ",") -> str:
    """Description formatter - sanitizes and word-cuts, never dot-pads.

    Microstock description floors are word-based (e.g. Shutterstock needs a
    5-word prose sentence), so a character pad with '.' would poison the text;
    word-level compliance is enforced upstream by validate_compliance.
    """
    s = sanitize_text(s, semi)
    if len(s) <= max_len:
        return s
    idx = s.rfind(" ", 0, max_len)
    return s[:idx] if idx > 0 else s[:max_len]


# Shutterstock photos (and EPS vectors) use *named* categories, up to 2 per file.
SHUTTERSTOCK_CATEGORIES = [
    "Abstract",
    "Animals/Wildlife",
    "Arts",
    "Backgrounds/Textures",
    "Beauty/Fashion",
    "Buildings/Landmarks",
    "Business/Finance",
    "Celebrities",
    "Education",
    "Food and Drink",
    "Healthcare/Medical",
    "Holidays",
    "Industrial",
    "Interiors",
    "Miscellaneous",
    "Nature",
    "Objects",
    "Parks/Outdoor",
    "People",
    "Religion",
    "Science",
    "Signs/Symbols",
    "Sports/Recreation",
    "Technology",
    "Transportation",
    "Vintage",
]

_SS_CATEGORY_ALIASES = {
    "Food and drink": "Food and Drink",
    "Health care": "Healthcare/Medical",
    "Art": "Arts",
}


def ss_categories(primary: str, secondary: str, filename: str) -> str:
    cats = []
    for name in (primary, secondary):
        if not name:
            continue
        name = name.strip()
        norm = (
            name
            if name in SHUTTERSTOCK_CATEGORIES
            else _SS_CATEGORY_ALIASES.get(name, "")
        )
        if norm and norm not in cats:
            cats.append(norm)
    if cats:
        return ",".join(cats)
    # Vector/illustration assets default to Arts, never to Backgrounds/Textures.
    if str(filename).lower().endswith((".svg", ".eps", ".ai")):
        return "Arts"
    return "Backgrounds/Textures"


def fmt_kw(s: str, min_count: int = 0, max_count: int = 50, semi: str = ",") -> str:
    # min_count is a compliance floor already upheld upstream (prompt + clean_metadata).
    # Never inject filler keywords here - platforms reject spammed/repeated terms.
    s = sanitize_text(s, semi)
    kws = [k.strip() for k in s.split(",") if k.strip()]
    return ", ".join(kws[:max_count])


def fmt_kw_limited(s: str, max_count: int) -> str:
    return fmt_kw(s, 0, max_count)


def is_illus(fname: str) -> str:
    return "yes" if fname.lower().endswith((".svg", ".eps", ".ai")) else "no"


AI_DISCLOSURE = "Generative AI illustration."


def apply_ai_disclosure(description: str, is_ai_generated: bool = False) -> str:
    """Prepend the Dreamstime-required generative-AI provenance statement.

    Dreamstime asks contributors to state generative-AI provenance in the
    description text; the flag rides the master CSV's IsAI column (written by
    the processing pipeline via CSVLogger).
    """
    if not is_ai_generated or not description:
        return description
    if description.lstrip().lower().startswith(AI_DISCLOSURE.lower()):
        return description
    return f"{AI_DISCLOSURE} {description}"


def _row_is_ai(r: dict) -> bool:
    return str(r.get("IsAI", "")).strip().lower() in {"1", "true", "yes"}


def upsert_metadata_csv(
    master_path: str, filename: str, title: str, description: str, keywords: list
) -> None:
    """Update-or-append a single file's row in metadata_output.csv.

    Reads any existing rows, replaces the matching filename entry (if present),
    or appends a new row — so saving one file no longer wipes other files.
    """
    rows: list[list[str]] = []
    if os.path.exists(master_path):
        with open(master_path, "r", encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
    if not rows:
        rows = [["Filename", "Title", "Description", "Keywords"]]
    row = [filename, title, description, ",".join(keywords)]
    for r in rows[1:]:
        if r and r[0] == filename:
            r[:] = row
            break
    else:
        rows.append(row)
    with open(master_path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)


def generate_microstock_csvs(out_dir: str, platforms: set | None = None):
    master = os.path.join(out_dir, "metadata_output.csv")
    if not os.path.exists(master):
        return

    with open(master, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return
    if platforms is None:
        platforms = {
            "Generic",
            "Adobe Stock",
            "Shutterstock",
            "Vecteezy",
            "Freepik",
            "Dreamstime",
        }

    def write_csv(name, header, row_fn, delimiter=","):
        with open(os.path.join(out_dir, name), "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=delimiter)
            writer.writerow(header)
            for r in rows:
                writer.writerow(row_fn(r))

    if "Generic" in platforms:
        write_csv(
            "generic_export.csv",
            ["Filename", "Title", "Description", "Keywords"],
            lambda r: [
                r["Filename"],
                sanitize_text(r.get("Title", "")),
                sanitize_text(r.get("Description", "")),
                fmt_kw(r["Keywords"], 0, 999),
            ],
        )

    if "Adobe Stock" in platforms:
        write_csv(
            "adobe_stock_export.csv",
            ["Filename", "Title", "Keywords", "Category", "Releases"],
            lambda r: [
                r["Filename"],
                fmt_str(r.get("Title", r.get("Description", "")), 200),
                fmt_kw(r.get("Keywords", ""), 5, 49),
                str(
                    get_adobe_category_code(
                        r.get("PrimaryCategory", "Graphic Resources")
                    )
                ),
                "",
            ],
        )

    if "Shutterstock" in platforms:
        write_csv(
            "shutterstock_export.csv",
            [
                "Filename",
                "Description",
                "Keywords",
                "Categories",
                "Editorial",
                "Mature content",
                "illustration",
            ],
            lambda r: [
                r["Filename"],
                fmt_desc(r.get("Description", r.get("Title", "")), 2000),
                fmt_kw(r["Keywords"], 7, 50),
                ss_categories(
                    r.get("PrimaryCategory", ""),
                    r.get("SecondaryCategory", ""),
                    r["Filename"],
                ),
                "no",
                "",
                is_illus(r["Filename"]),
            ],
        )

    if "Vecteezy" in platforms:
        write_csv(
            "vecteezy_export.csv",
            ["Filename", "Title", "Description", "Keywords", "License", "Id"],
            lambda r: [
                r["Filename"],
                sanitize_text(r.get("Title", "")),
                sanitize_text(r.get("Description", "")),
                fmt_kw(r["Keywords"], 10, 30),
                "pro",
                "",
            ],
        )

    if "Freepik" in platforms:
        # Freepik/Magnific expects ';' as column separator; keep ',' inside tags.
        write_csv(
            "freepik_export.csv",
            ["File name", "Title", "Tags"],
            lambda r: [
                r["Filename"],
                fmt_str(
                    r.get("Title", r.get("Description", "")),
                    200,
                    semi=" ",
                ),
                fmt_kw(r["Keywords"], 5, 50, semi=" "),
            ],
            delimiter=";",
        )

    if "Dreamstime" in platforms:
        write_csv(
            "dreamstime_export.csv",
            ["Filename", "Title", "Description", "Keywords"],
            lambda r: [
                r["Filename"],
                sanitize_text(r.get("Title", "")),
                apply_ai_disclosure(
                    sanitize_text(r.get("Description", "")), _row_is_ai(r)
                ),
                fmt_kw(r["Keywords"], 0, 50),
            ],
        )
