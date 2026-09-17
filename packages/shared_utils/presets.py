import json
import os

from backend.core.config_manager import atomic_write_text, get_config_dir


def presets_path() -> str:
    """Resolve the presets file under the stable config dir, not the cwd."""
    return os.path.join(get_config_dir(), "keyword_presets.json")


def _load_presets() -> dict:
    presets = {}
    if os.path.exists(presets_path()):
        try:
            with open(presets_path(), "r", encoding="utf-8") as f:
                presets = json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
            
    if not isinstance(presets, dict) or not presets:
        return {"Default": []}
    
    if "Default" not in presets:
        presets["Default"] = []
        
    return presets


def _save_presets(presets: dict):
    atomic_write_text(
        presets_path(), json.dumps(presets, indent=2, ensure_ascii=False)
    )


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
    atomic_write_text(filepath, json.dumps(presets, indent=2, ensure_ascii=False))


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
