import csv
import os
from packages.shared_utils.taxonomy import get_adobe_category_code

def fmt_str(s: str, max_len: int) -> str:
    if len(s) <= max_len: return s
    idx = s.rfind(' ', 0, max_len)
    if idx > 0: return s[:idx]
    return s[:max_len]

def fmt_kw(s: str) -> str:
    return ", ".join([k.strip() for k in s.split(",") if k.strip()])

def fmt_kw_limited(s: str, max_count: int) -> str:
    kws = [k.strip() for k in s.split(",") if k.strip()]
    return ", ".join(kws[:max_count])

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
                  lambda r: [r["Filename"], r.get("Title", ""), r.get("Description", ""), fmt_kw(r["Keywords"])])

    if "Adobe Stock" in platforms:
        write_csv("adobe_stock_export.csv", ["Filename", "Title", "Keywords", "Category", "Releases"], 
                  lambda r: [r["Filename"], fmt_str(r.get("Title", r.get("Description", "")), 200), fmt_kw_limited(r.get("Keywords", ""), 49), str(get_adobe_category_code(r.get("PrimaryCategory", "Graphic Resources"))), ""])
              
    if "Shutterstock" in platforms:
        write_csv("shutterstock_export.csv", ["Filename", "Description", "Keywords", "Categories", "Editorial", "Mature content", "illustration"], 
                  lambda r: [r["Filename"], fmt_str(r.get("Description", r.get("Title", "")), 180), fmt_kw(r["Keywords"]), r.get("PrimaryCategory", "Backgrounds/Textures"), "no", "", is_illus(r["Filename"])])
              
    if "Vecteezy" in platforms:
        write_csv("vecteezy_export.csv", ["Filename", "Title", "Description", "Keywords", "License", "Id"], 
                  lambda r: [r["Filename"], r.get("Title", ""), r.get("Description", ""), fmt_kw(r["Keywords"]), "pro", ""])
              
    if "Freepik" in platforms:
        write_csv("freepik_export.csv", ["File name", "Title", "Tags"], 
                  lambda r: [r["Filename"], fmt_str(r.get("Title", r.get("Description", "")), 100), fmt_kw(r["Keywords"])])
