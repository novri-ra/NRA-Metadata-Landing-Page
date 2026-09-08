import os
import sys

# Ensure packages can be found
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from packages.shared_utils.config import (
    CONFIG_FILE,
    CONFIG_FILE_ENC,
    load_config,
    save_config,
)


def provision_default_config():
    if not os.path.exists(CONFIG_FILE) and not os.path.exists(CONFIG_FILE_ENC):
        print("[*] No existing configuration found. Creating default config...")
        default_config = {
            "api_keys": {"Gemini": "", "Groq": "", "Mistral": "", "OpenAI": ""},
            "provider": "Gemini",
            "model": "gemini-2.5-flash",
            "temperature": 0.3,
            "workers": 4,
            "min_kw": 25,
            "max_kw": 49,
            "style_preset": "General Commercial",
            "extra_prompt": "",
            "mandatory_kw": "",
            "window_geometry": "1280x760",
        }
        try:
            save_config(default_config)
            print("[*] Default configuration created.")
        except OSError as e:
            print(f"[!] Failed to create default config: {e}")
    else:
        # Check if migration to api_keys is needed
        config = load_config()
        if "api_keys" not in config:
            config["api_keys"] = {"Gemini": "", "Groq": "", "Mistral": "", "OpenAI": ""}
            if "api_key" in config:
                provider = config.get("provider", "Gemini")
                config["api_keys"][provider] = config.pop("api_key")
            save_config(config)
            print("[*] Configuration updated to new format.")


if __name__ == "__main__":
    provision_default_config()
