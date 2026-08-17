import os
import json
from pathlib import Path

CONFIG_FILE = os.path.join(os.getcwd(), "config.json")

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_config(config: dict):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)
