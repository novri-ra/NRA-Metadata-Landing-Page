import csv
import logging
import threading

logger = logging.getLogger("NRA-Metadata")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
logger.addHandler(ch)


class CSVLogger:
    def __init__(self, filepath):
        self.filepath = filepath
        self.lock = threading.Lock()
        with open(self.filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Filename", "Title", "Description", "Keywords"])

    def log(self, filename, title, description, keywords):
        with self.lock, open(self.filepath, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([filename, title, description, ",".join(keywords)])
