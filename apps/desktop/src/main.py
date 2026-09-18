import os

from ui.main_window import AppWindow

from backend.core.config_manager import (
    get_config_dir,
    import_rj_config,
    load_config,
    set_config_dir,
)


def _migrate_rj_keys():
    cfg = load_config()
    if cfg.get("api_keys"):
        return None
    summary = import_rj_config()
    print(
        f"[config] Data directory: {get_config_dir()}"
    )
    if summary.get("imported"):
        added = summary.get("providers_added", {})
        print(
            f"[config] Imported API keys from RJ Auto Metadata: "
            f"{', '.join(added) if added else 'none usable'}"
        )
    else:
        print(f"[config] RJ Auto Metadata sync skipped: {summary.get('reason')}")
    return summary


def main():
    set_config_dir()
    os.makedirs(get_config_dir(), exist_ok=True)
    _migrate_rj_keys()
    app = AppWindow()
    app.mainloop()


if __name__ == "__main__":
    main()