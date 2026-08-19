import os
import json
from pathlib import Path

CONFIG_FILE = os.path.join(os.getcwd(), "config.json")

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}

def save_config(config: dict):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)
