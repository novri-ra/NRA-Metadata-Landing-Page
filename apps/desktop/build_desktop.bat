@echo off
set PYTHONPATH=%CD%
pyinstaller --noconfirm --onedir --windowed --name "AutoMetadata-GUI" --add-data "tools;tools" --hidden-import "customtkinter" --hidden-import "google.generativeai" --hidden-import "openai" --hidden-import "PIL" apps/desktop/src/main.py
echo GUI Build complete.