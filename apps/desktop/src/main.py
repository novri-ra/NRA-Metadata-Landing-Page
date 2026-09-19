import os

from ui.main_window import AppWindow

from backend.core.config_manager import (
    get_config_dir,
    load_config,
    set_config_dir,
)


def main():
    set_config_dir()
    os.makedirs(get_config_dir(), exist_ok=True)
    app = AppWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
