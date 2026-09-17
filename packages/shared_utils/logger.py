import csv
import logging
import sys
import threading

SUCCESS = logging.INFO + 5
logging.addLevelName(SUCCESS, "SUCCESS")

# ANSI colors for console tags; auto-disabled when stdout is not a TTY.
_LEVEL_COLOR = {
    "DEBUG": "\x1b[90m",  # gray
    "INFO": "\x1b[94m",  # bright blue
    "SUCCESS": "\x1b[92m",  # green
    "WARNING": "\x1b[93m",  # yellow
    "ERROR": "\x1b[91m",  # bright red
    "CRITICAL": "\x1b[91;1m",  # bright red bold
}
_RESET = "\x1b[0m"


def log_success(message: str, *args, **kwargs):
    logger.log(SUCCESS, message, *args, **kwargs)


class _ColorFormatter(logging.Formatter):
    """Bracket-and-color each level tag: ``[INFO]``, ``[SUCCESS]``, ..."""

    def format(self, record):
        name = record.levelname
        color = _LEVEL_COLOR.get(name)
        if color and sys.stdout.isatty():
            record.levelname = f"{color}[{name}]{_RESET}"
        else:
            record.levelname = f"[{name}]"
        return super().format(record)


logger = logging.getLogger("NRA-Metadata")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setFormatter(_ColorFormatter("%(levelname)s %(message)s"))
logger.addHandler(ch)
logger.propagate = False


class CSVLogger:
    def __init__(self, filepath):
        self.filepath = filepath
        self.lock = threading.Lock()
        with open(self.filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Filename",
                    "Title",
                    "Description",
                    "Keywords",
                    "IsAI",
                    "IsEditorial",
                    "City",
                    "Country",
                    "CountryCode",
                    "DateCreated",
                    "Category",
                    "PrimaryCategory",
                    "SecondaryCategory",
                ]
            )

    def log(
        self,
        filename,
        title,
        description,
        keywords,
        category="",
        primary_category="",
        secondary_category="",
        is_ai_generated=False,
        is_editorial=False,
        city="",
        country="",
        country_code="",
        date_created="",
    ):
        with self.lock, open(self.filepath, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    filename,
                    title,
                    description,
                    ",".join(keywords),
                    "1" if is_ai_generated else "0",
                    "1" if is_editorial else "0",
                    city,
                    country,
                    country_code,
                    date_created,
                    category,
                    primary_category,
                    secondary_category,
                ]
            )
