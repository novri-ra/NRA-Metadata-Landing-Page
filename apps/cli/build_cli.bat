@echo off
set PYTHONPATH=%CD%
pyinstaller --noconfirm --onedir --console --name "AutoMetadata-CLI" --add-data "tools;tools" --collect-all "backend" --hidden-import "google.generativeai" --hidden-import "openai" --hidden-import "PIL" apps/cli/src/main.py
echo CLI Build complete.