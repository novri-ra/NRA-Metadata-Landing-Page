import csv
import os

def import_csv_metadata(csv_path: str) -> dict:
    """Import and parse metadata from a standard Microstock CSV format.
    Expected headers: Filename, Title, Description, Keywords
    """
    results = {}
    if not os.path.exists(csv_path):
        return results
        
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                filename = row.get("Filename", "").strip()
                if filename:
                    # Clean up and normalize
                    title = row.get("Title", "").strip()
                    desc = row.get("Description", "").strip()
                    kws = row.get("Keywords", "")
                    
                    # Parse keywords into a list
                    if kws:
                        kw_list = [k.strip() for k in kws.split(",") if k.strip()]
                    else:
                        kw_list = []
                        
                    results[filename] = {
                        "Title": title,
                        "Description": desc,
                        "Keywords": kw_list
                    }
    except Exception as e:
        print(f"Failed to import CSV: {e}")
        
    return results