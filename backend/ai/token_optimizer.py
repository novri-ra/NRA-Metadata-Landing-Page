"""Token-saver pipeline for vision models and text-asset fallbacks.

``encode_image`` downscales any asset to at most 1024x1024 and encodes it as
base64 JPEG (quality 85) so the AI payload stays small. ``read_text_asset``
is used for SVG fallback (raw text inspection instead of rasterized image).
"""

import base64
import io

from PIL import Image


def encode_image(image_path: str) -> str:
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        # Token-saver pipeline: limit to 1024x1024
        img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        # Quality 85 for AI vision, saves massive payload size
        img.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")


def read_text_asset(image_path: str) -> str:
    with open(image_path, "r", encoding="utf-8") as f:
        return f.read()[:20000]