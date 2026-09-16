"""API key parsing, file loading, and OpenAI-compatible client factory."""

import json
import os
import re

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


def mask_api_key(key: str) -> str:
    """Mask an API key, showing only the first 5 characters and replacing the rest with asterisks."""
    key = key.strip()
    if not key:
        return ""
    if len(key) <= 5:
        return key
    return key[:5] + "*" * (len(key) - 5)

def parse_api_keys(raw_input: str) -> list[str]:
    """Extract API keys from a flexible raw input string.

    Supports: newline-separated, comma/semicolon/pipe-separated, quoted lists,
    JSON arrays, numbered/bullet lists, and .env key-value pairs.
    """
    if not raw_input or not raw_input.strip():
        return []
    keys = []
    seen = set()
    for line in raw_input.splitlines():
        line = line.strip()
        if not line:
            continue
        # .env format: KEY=value or KEY="value"
        env_match = re.match(r'^[A-Za-z_][A-Za-z0-9_]*\s*=\s*["\']?(.+?)["\']?\s*$', line)
        if env_match:
            val = env_match.group(1).strip().strip("\"'")
            if val and len(val) >= 8 and val.lower() not in seen:
                keys.append(val)
                seen.add(val.lower())
            continue
        # Numbered/bullet list: "1. key" or "- key" or "• key"
        bullet_match = re.match(r'^(?:\d+\.\s*|[-•]\s+)(.+)', line)
        if bullet_match:
            line = bullet_match.group(1).strip()
        # Strip surrounding quotes
        line = line.strip("\"'[]")
        # Split on comma, semicolon, pipe
        parts = re.split(r'[,;|]', line)
        for part in parts:
            part = part.strip().strip("\"' ")
            if not part:
                continue
            # Reject overly short (not a real key)
            if len(part) < 8:
                continue
            if part.lower() not in seen:
                keys.append(part)
                seen.add(part.lower())
    return keys


def load_keys_from_file(filepath: str) -> list[str]:
    """Read API keys from a file. Supports .txt, .csv, .json, .env."""
    if not os.path.isfile(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return []
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".json":
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return [str(k) for k in data if k and len(str(k)) >= 8]
            if isinstance(data, dict):
                # Flatten all string values
                flat = []
                for v in data.values():
                    if isinstance(v, str) and len(v) >= 8:
                        flat.append(v)
                    elif isinstance(v, list):
                        flat.extend(str(k) for k in v if k and len(str(k)) >= 8)
                return flat
        except json.JSONDecodeError:
            pass
    return parse_api_keys(content)


def build_openai_compatible_client(
    base_url: str, api_key: str, model_name: str = "", timeout: float = 120
):
    """Factory returning a preconfigured OpenAI SDK client for custom endpoints.

    Raises ImportError if the openai package is not installed.
    """
    if OpenAI is None:
        raise ImportError("The openai package is required for custom endpoints")
    return OpenAI(
        base_url=base_url or "https://api.openai.com/v1",
        api_key=api_key,
        timeout=timeout,
    )
