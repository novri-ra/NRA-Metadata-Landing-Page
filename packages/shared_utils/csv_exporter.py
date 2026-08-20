import csv
import os
import re
from packages.shared_utils.taxonomy import get_adobe_category_code

def sanitize_text(s: str) -> str:
    if not s: return ""
    s = re.sub(r'[\r\n\t]+', ' ', s)
    s = s.replace('"', "'")
    s = s.replace(';', ',')
    return s.strip()

def fmt_str(s: str, max_len: int, min_len: int = 0) -> str:
    s = sanitize_text(s)
    if len(s) < min_len:
        s = s.ljust(min_len, '.')
    if len(s) <= max_len: return s
    idx = s.rfind(' ', 0, max_len)
    if idx > 0: return s[:idx]
    return s[:max_len]

def fmt_kw(s: str, min_count: int = 0, max_count: int = 50) -> str:
    s = sanitize_text(s)
    kws = [k.strip() for k in s.split(",") if k.strip()]
    kws = kws[:max_count]
    while len(kws) < min_count:
        kws.append("background")
    return ", ".join(kws)

def fmt_kw_limited(s: str, max_count: int) -> str:
    return fmt_kw(s, 0, max_count)

def is_illus(fname: str) -> str:
    return "yes" if fname.lower().endswith(('.svg', '.eps', '.ai', '.png')) else "no"

def generate_microstock_csvs(out_dir: str, platforms: set = None):
    master = os.path.join(out_dir, "metadata_output.csv")
    if not os.path.exists(master): return

    with open(master, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    
    if not rows: return
    if platforms is None:
        platforms = {"Generic", "Adobe Stock", "Shutterstock", "Vecteezy", "Freepik"}

    def write_csv(name, header, row_fn):
        with open(os.path.join(out_dir, name), 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for r in rows: writer.writerow(row_fn(r))

    if "Generic" in platforms:
        write_csv("generic_export.csv", ["Filename", "Title", "Description", "Keywords"],
                  lambda r: [r["Filename"], sanitize_text(r.get("Title", "")), sanitize_text(r.get("Description", "")), fmt_kw(r["Keywords"], 0, 999)])

    if "Adobe Stock" in platforms:
        write_csv("adobe_stock_export.csv", ["Filename", "Title", "Keywords", "Category", "Releases"], 
                  lambda r: [r["Filename"], fmt_str(r.get("Title", r.get("Description", "")), 200), fmt_kw(r.get("Keywords", ""), 5, 49), str(get_adobe_category_code(r.get("PrimaryCategory", "Graphic Resources"))), ""])
              
    if "Shutterstock" in platforms:
        write_csv("shutterstock_export.csv", ["Filename", "Description", "Keywords", "Categories", "Editorial", "Mature content", "illustration"], 
                  lambda r: [
                      r["Filename"], 
                      fmt_str(r.get("Description", r.get("Title", "")), 200, 5), 
                      fmt_kw(r["Keywords"], 7, 50), 
                      (r.get("PrimaryCategory", "Backgrounds/Textures") + (f",{r.get('SecondaryCategory')}" if r.get("SecondaryCategory") else "")).strip(','), 
                      "no", "", is_illus(r["Filename"])
                  ])
              
    if "Vecteezy" in platforms:
        write_csv("vecteezy_export.csv", ["Filename", "Title", "Description", "Keywords", "License", "Id"], 
                  lambda r: [r["Filename"], sanitize_text(r.get("Title", "")), sanitize_text(r.get("Description", "")), fmt_kw(r["Keywords"], 5, 50), "pro", ""])
              
    if "Freepik" in platforms:
        write_csv("freepik_export.csv", ["File name", "Title", "Tags"], 
                  lambda r: [r["Filename"], fmt_str(r.get("Title", r.get("Description", "")), 100), fmt_kw(r["Keywords"], 5, 50)])
