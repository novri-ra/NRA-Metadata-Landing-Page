import csv
import os

def fmt_str(s: str, max_len: int) -> str:
    return s[:max_len]

def fmt_kw(s: str) -> str:
    return ", ".join([k.strip() for k in s.split(",") if k.strip()])

def is_illus(fname: str) -> str:
    return "yes" if fname.lower().endswith(('.svg', '.eps', '.ai', '.png')) else "no"

def generate_microstock_csvs(out_dir: str):
    master = os.path.join(out_dir, "metadata_output.csv")
    if not os.path.exists(master): return

    with open(master, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    
    if not rows: return

    def write_csv(name, header, row_fn):
        with open(os.path.join(out_dir, name), 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for r in rows: writer.writerow(row_fn(r))

    write_csv("adobe_stock_export.csv", ["Filename", "Title", "Keywords", "Category", "Releases"], 
              lambda r: [r["Filename"], fmt_str(r.get("Title", r.get("Description", "")), 180), fmt_kw(r["Keywords"]), "8", ""])
              
    write_csv("shutterstock_export.csv", ["Filename", "Description", "Keywords", "Categories", "Editorial", "Mature content", "illustration"], 
              lambda r: [r["Filename"], fmt_str(r.get("Description", r.get("Title", "")), 180), fmt_kw(r["Keywords"]), "Backgrounds/Textures", "no", "", is_illus(r["Filename"])])
              
    write_csv("vecteezy_export.csv", ["Filename", "Title", "Description", "Keywords", "License", "Id"], 
              lambda r: [r["Filename"], r.get("Title", ""), r.get("Description", ""), fmt_kw(r["Keywords"]), "pro", ""])
              
    write_csv("miri_canvas_export.csv", ["fileName", "uniqueId", "elementName", "keywords", "tier", "contentType"], 
              lambda r: [os.path.splitext(r["Filename"])[0], "", r.get("Title", ""), fmt_kw(r["Keywords"]), "Premium", ""])
              
    write_csv("depositphotos_export.csv", ["Filename", "description", "Keywords", "Nudity", "Editorial"], 
              lambda r: [r["Filename"], r.get("Description", ""), fmt_kw(r["Keywords"]), "no", "no"])
              
    write_csv("123rf_export.csv", ["oldfilename", "123rf_filename", "description", "keywords", "country"], 
              lambda r: [r["Filename"], "", r.get("Description", ""), fmt_kw(r["Keywords"]), "ID"])

    write_csv("freepik_export.csv", ["File name", "Title", "Tags"], 
              lambda r: [r["Filename"], fmt_str(r.get("Title", r.get("Description", "")), 100), fmt_kw(r["Keywords"])])

