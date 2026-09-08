import json
import os

_PRESETS_FILE = os.path.join(os.getcwd(), "keyword_presets.json")


def _load_presets() -> dict:
    if os.path.exists(_PRESETS_FILE):
        try:
            with open(_PRESETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _save_presets(presets: dict):
    with open(_PRESETS_FILE, "w", encoding="utf-8") as f:
        json.dump(presets, f, indent=2, ensure_ascii=False)


def get_preset_names() -> list[str]:
    return list(_load_presets().keys())


def get_preset(name: str) -> list[str]:
    return _load_presets().get(name, [])


def save_preset(name: str, keywords: list[str]):
    presets = _load_presets()
    presets[name] = keywords
    _save_presets(presets)


def delete_preset(name: str):
    presets = _load_presets()
    presets.pop(name, None)
    _save_presets(presets)


def export_presets(filepath: str):
    presets = _load_presets()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(presets, f, indent=2, ensure_ascii=False)


def import_presets(filepath: str) -> int:
    """Import presets from a JSON file. Returns count of imported presets."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return 0
    presets = _load_presets()
    count = 0
    for name, kws in data.items():
        if isinstance(kws, list):
            presets[name] = kws
            count += 1
    _save_presets(presets)
    return count
