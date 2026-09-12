import argparse
import os
import shutil
from concurrent.futures import ThreadPoolExecutor

from backend.ai.provider_router import AIService
from backend.processors.exiftool_client import ExifToolClient
from backend.processors.media_converter import extract_preview_image
from packages.shared_utils.logger import CSVLogger, logger


def process_file(file_path, out_dir, ai, processor, min_kw, max_kw, csv_logger):
    logger.info(f"Processing {os.path.basename(file_path)}")
    preview = extract_preview_image(file_path)
    if not preview:
        logger.warning(f"Skipped {os.path.basename(file_path)}: no preview")
        return

    meta = ai.generate_metadata(preview, min_kw, max_kw)
    try:
        os.remove(preview)
    except OSError:
        pass

    out_path = os.path.join(out_dir, os.path.basename(file_path))
    shutil.copy2(file_path, out_path)

    title = meta.get("title", "")
    desc = meta.get("description", "")
    keywords = meta.get("keywords", [])

    if processor.embed_metadata(out_path, title, desc, keywords, "Copyright Text"):
        logger.info(f"Success {os.path.basename(file_path)}")
        csv_logger.log(os.path.basename(file_path), title, desc, keywords)
    else:
        logger.error(f"Failed {os.path.basename(file_path)}")


def main():
    parser = argparse.ArgumentParser(description="Headless Batch Runner")
    parser.add_argument("--input", required=True, help="Input directory")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument(
        "--provider", required=True, choices=["Gemini", "OpenAI", "Mistral"]
    )
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--min-kw", type=int, default=5)
    parser.add_argument("--max-kw", type=int, default=20)
    parser.add_argument("--workers", type=int, default=2)

    args = parser.parse_args()

    files = [
        os.path.join(args.input, f)
        for f in os.listdir(args.input)
        if os.path.isfile(os.path.join(args.input, f))
    ]
    if not files:
        logger.error("No files found.")
        return

    ai = AIService(args.provider, args.api_key)
    processor = MediaProcessor()
    csv_logger = CSVLogger(os.path.join(args.output, "metadata_output.csv"))

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for file in files:
            executor.submit(
                process_file,
                file,
                args.output,
                ai,
                processor,
                args.min_kw,
                args.max_kw,
                csv_logger,
            )


if __name__ == "__main__":
    main()
