import csv
import os
import re
import threading
from datetime import UTC, datetime

from packages.shared_utils.taxonomy import (
    get_adobe_category_code,
)

_csv_lock = threading.RLock()


def sanitize_text(s: str, semi: str = ",") -> str:
    if not s:
        return ""
    s = re.sub(r"[\r\n\t]+", " ", s)
    s = s.replace('"', "'")
    if semi is not None:
        s = s.replace(";", semi)
    s = s.strip()
    # CSV formula injection: a leading =, +, - or @ is treated as a formula
    # by Excel/Google Sheets. Prefix with a single quote to force text mode.
    if s[:1] in ("=", "+", "-", "@"):
        s = "'" + s
    return s


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


_SS_CATEGORY_ALIASES = {
    "Food and drink": "Food and Drink",
    "Health care": "Healthcare/Medical",
    "Art": "The Arts",
    "Arts": "The Arts",
}


def ss_categories(primary: str, secondary: str, filename: str, title: str = "", keywords: list | None = None) -> str:
    from packages.shared_utils.taxonomy import map_to_agency_category
    
    cats = []
    for name in (primary, secondary):
        if not name:
            continue
        norm = map_to_agency_category(name, "shutterstock", title=title, keywords=keywords)
        if norm and norm not in cats:
            cats.append(norm)
            
    # If no AI category could be determined, or it's empty, use filename fallback
    if not cats:
        if str(filename).lower().endswith((".svg", ".eps", ".ai")):
            cats.append("The Arts")
        else:
            cats.append("Backgrounds/Textures")
            
    return ",".join(cats[:2])


def fmt_kw(s: str, min_count: int = 0, max_count: int = 50, semi: str = ",", term_max: int = 0) -> str:
    # min_count is a compliance floor already upheld upstream (prompt + clean_metadata).
    # Never inject filler keywords here - platforms reject spammed/repeated terms.
    s = sanitize_text(s, semi)
    kws = [k.strip() for k in s.split(",") if k.strip()]
    if term_max:
        # iStock/Getty reject individual free-text terms longer than 64 chars.
        kws = [k[:term_max] for k in kws]
    return ", ".join(kws[:max_count])


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


def _row_is_editorial(r: dict) -> bool:
    return str(r.get("IsEditorial", "") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _parse_editorial_date(raw: str) -> datetime | None:
    """Parse ``YYYY-MM-DD`` / ``YYYY/MM/DD`` / 8-digit ``YYYYMMDD``."""
    raw = (raw or "").strip()
    m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", raw)
    if not m:
        m = re.match(r"^(\d{4})(\d{2})(\d{2})$", raw)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=UTC)
    except ValueError:
        return None


def format_editorial_date(date_created: str) -> str:
    """Render a date as editorial caption format ``MONTH DAY, YEAR``."""
    d = _parse_editorial_date(date_created)
    return d.strftime("%B %d, %Y") if d else (date_created or "").strip()


def build_editorial_caption(
    description: str,
    city: str = "",
    country: str = "",
    date_created: str = "",
) -> str:
    """Compose the Getty/iStock 5W editorial caption prefix.

    ``[CITY, COUNTRY - MONTH DAY, YEAR: <factual description>]``.  Missing
    parts degrade gracefully; a blank location and date returns the raw
    description unchanged.
    """
    loc = ", ".join(x.strip() for x in (city, country) if x and x.strip())
    date = format_editorial_date(date_created)
    if not loc and not date:
        return description
    return f"[{loc} - {date}: {description}]" if loc and date else f"[{loc or date}: {description}]"


def upsert_metadata_csv(
    master_path: str, filename: str, title: str, description: str, keywords: list
) -> None:
    """Update-or-append a single file's row in metadata_output.csv.

    Reads any existing rows, replaces the matching filename entry (if present),
    or appends a new row — so saving one file no longer wipes other files.
    """
    with _csv_lock:
        rows: list[list[str]] = []
        if os.path.exists(master_path):
            with open(master_path, "r", encoding="utf-8", newline="") as f:
                rows = list(csv.reader(f))
        if not rows:
            rows = [["Filename", "Title", "Description", "Keywords", "IsAI", "IsEditorial", "City", "Country", "CountryCode", "DateCreated", "Category", "PrimaryCategory", "SecondaryCategory"]]
        row = [filename, title, description, ",".join(keywords), "0", "0", "", "", "", "", "", "", ""]
        for r in rows[1:]:
            if r and r[0] == filename:
                r[:] = row
                break
        else:
            rows.append(row)
        with open(master_path, "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(rows)


def upsert_editorial_csv(
    master_path: str,
    filename: str,
    title: str,
    description: str,
    keywords: list,
    is_editorial: bool = False,
    city: str = "",
    country: str = "",
    country_code: str = "",
    date_created: str = "",
) -> None:
    """Update-or-append a single file's row with the editorial columns."""
    with _csv_lock:
        rows: list[list[str]] = []
        if os.path.exists(master_path):
            with open(master_path, "r", encoding="utf-8", newline="") as f:
                rows = list(csv.reader(f))
        if not rows:
            rows = [["Filename", "Title", "Description", "Keywords",
                     "IsAI", "IsEditorial", "City", "Country", "CountryCode", "DateCreated", 
                     "Category", "PrimaryCategory", "SecondaryCategory"]]
        row = [
            filename,
            title,
            description,
            ",".join(keywords),
            "0",
            "1" if is_editorial else "0",
            city,
            country,
            country_code,
            date_created,
            "",
            "",
            "",
        ]
        for r in rows[1:]:
            if r and r[0] == filename:
                r.extend("" for _ in range(len(row) - len(r)))
                r[: len(row)] = row
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
                        r.get("PrimaryCategory", "Graphic Resources"),
                        title=r.get("Title", ""),
                        keywords=[k.strip() for k in r.get("Keywords", "").split(",") if k.strip()]
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
                    title=r.get("Title", ""),
                    keywords=[k.strip() for k in r.get("Keywords", "").split(",") if k.strip()]
                ),
                "yes" if _row_is_editorial(r) else "no",
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
                fmt_kw(r["Keywords"], 5, 50),
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
            ["Filename", "Title", "Description", "Keywords", "Editorial"],
            lambda r: [
                r["Filename"],
                sanitize_text(r.get("Title", "")),
                apply_ai_disclosure(
                    sanitize_text(r.get("Description", "")), _row_is_ai(r)
                ),
                fmt_kw(r["Keywords"], 0, 50),
                "yes" if _row_is_editorial(r) else "no",
            ],
        )

    editorial_rows = [r for r in rows if _row_is_editorial(r)]
    if editorial_rows:
        write_csv(
            "getty_editorial_export.csv",
            [
                "Filename",
                "Title",
                "Description",
                "Keywords",
                "City",
                "Country",
                "CountryCode",
                "DateCreated",
            ],
            lambda r: [
                r["Filename"],
                sanitize_text(r.get("Title", "")),
                sanitize_text(r.get("Description", "")),
                fmt_kw(r.get("Keywords", ""), 0, 999, term_max=64),
                sanitize_text(r.get("City", "")),
                sanitize_text(r.get("Country", "")),
                sanitize_text(r.get("CountryCode", "")),
                sanitize_text(r.get("DateCreated", "")),
            ],
        )
