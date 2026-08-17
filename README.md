# NRA-Metadata

AI-Powered Microstock Metadata Generator & Embedder.

## Architecture
Monorepo structure:
- `apps/desktop/`: GUI application.
- `apps/cli/`: CLI entry point.
- `packages/ai_engine/`: AI prompt and generation logic.
- `packages/media_processor/`: Image previews and ExifTool/SVG embedding.
- `packages/shared_utils/`: Caching, logging, keyword filtering, and CSV exporters.

## Features
- Vision AI metadata generation
- In-place subfolder isolation
- Auto-zip vector bundler
- Multi-platform CSV exporters (Adobe Stock, Shutterstock, Vecteezy, etc.)
- SQLite cache
- Blacklist keyword filtering & sanitization
- Offline CSV re-tagger pipeline

## Installation
```bash
pip install -r nra_metadata.egg-info/requires.txt
```

## Run
```bash
python apps/desktop/src/main.py
```

## Build Standalone (.exe)
Use the provided build batch files. For desktop:
```cmd
apps\desktop\build_desktop.bat
```
