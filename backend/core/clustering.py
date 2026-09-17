"""Smart Batch Deduplication and Perceptual Clustering Module.

Uses 64-bit difference hash (dHash) and filename heuristics to group similar
assets in a batch. Cluster variants inherit metadata from the Cluster Leader,
saving 100% of AI vision tokens for similar set variants.
"""

import copy
import re
import threading
from PIL import Image


def compute_dhash(image_path: str) -> int:
    """Compute a 64-bit difference hash (dHash) from image using Pillow."""
    with Image.open(image_path) as img:
        # 9 columns x 8 rows grayscale for 8x8=64 horizontal differences
        resized = img.convert("L").resize((9, 8), Image.Resampling.BILINEAR)
        get_data_fn = getattr(resized, "get_flattened_data", resized.getdata)
        pixels = [p for p in get_data_fn()]

    diff = 0
    for row in range(8):
        row_start = row * 9
        for col in range(8):
            left = int(pixels[row_start + col]) # type: ignore
            right = int(pixels[row_start + col + 1]) # type: ignore
            diff = (diff << 1) | (1 if left > right else 0)
    return diff


def hamming_distance(hash1: int, hash2: int) -> int:
    """Count differing bits between two 64-bit hashes."""
    return bin(hash1 ^ hash2).count("1")


def normalize_asset_name(filename: str) -> str:
    """Strip extensions, numerical counters, and style variation tags from asset name."""
    name = re.sub(r"\.[^.]+$", "", filename).lower()
    patterns = [
        r"[-_](?:v?\d+|color|black|white|mono|outline|filled|silhouette|line|flat|isolated)$",
        r"[-_]\d+$",
        r"[-_][a-z]$",
    ]
    changed = True
    while changed:
        changed = False
        for p in patterns:
            new_name = re.sub(p, "", name)
            if new_name != name:
                name = new_name
                changed = True
    return name


def adapt_metadata_for_variant(leader_meta: dict, leader_name: str, variant_name: str) -> dict:
    """Adapt leader's metadata to variant specific filename cues without calling AI."""
    meta = copy.deepcopy(leader_meta)
    styles = [
        "outline", "silhouette", "black", "white", "color",
        "colored", "flat", "line", "linear", "glyph", "gradient", "sketch"
    ]
    variant_lower = variant_name.lower()
    leader_lower = leader_name.lower()

    detected_v = [s for s in styles if s in variant_lower and s not in leader_lower]
    detected_l = [s for s in styles if s in leader_lower and s not in variant_lower]

    if detected_v:
        v_tag = detected_v[0].title()
        title = meta.get("title", "")
        if detected_l:
            pattern = re.compile(re.escape(detected_l[0]), re.IGNORECASE)
            new_title = pattern.sub(v_tag, title)
            meta["title"] = new_title if new_title != title else f"{title} {v_tag}"
        else:
            meta["title"] = f"{title} {v_tag}"

        kws = meta.get("keywords", [])
        v_kw = detected_v[0]
        if v_kw not in [k.lower() for k in kws]:
            meta["keywords"] = [v_kw] + kws

    return meta


class ClusterCoordinator:
    """Coordinates batch similarity deduplication across worker threads."""

    def __init__(self, threshold: int = 4, enabled: bool = True):
        self.threshold = threshold
        self.enabled = enabled
        self.lock = threading.Lock()
        self.leaders = []  # list of dicts with leader metadata and synchronization event
        self.file_map = {}  # file_path -> leader info

    def register_asset(
        self, file_path: str, preview_path: str, name: str
    ) -> tuple[bool, threading.Event | None, str | None]:
        """Register an asset. Returns (is_leader, event_to_wait_on, leader_name)."""
        if not self.enabled:
            return True, None, None

        try:
            dhash = compute_dhash(preview_path)
        except Exception:
            return True, None, None

        norm_name = normalize_asset_name(name)

        with self.lock:
            for leader in self.leaders:
                dist = hamming_distance(dhash, leader["dhash"])
                # Match if perceptual hash is close OR normalized name matches and dhash <= 8
                if dist <= self.threshold or (norm_name == leader["norm_name"] and dist <= 8):
                    self.file_map[file_path] = leader
                    return False, leader["event"], leader["name"]

            # New leader
            event = threading.Event()
            leader_info = {
                "name": name,
                "path": file_path,
                "dhash": dhash,
                "norm_name": norm_name,
                "meta": None,
                "event": event,
            }
            self.leaders.append(leader_info)
            self.file_map[file_path] = leader_info
            return True, event, None

    def set_leader_metadata(self, file_path: str, meta: dict) -> None:
        """Publish generated metadata for all cluster variants to inherit."""
        with self.lock:
            leader = self.file_map.get(file_path)
            if leader and leader["path"] == file_path:
                leader["meta"] = meta
                leader["event"].set()

    def get_leader_metadata(
        self, file_path: str, timeout: float = 60.0
    ) -> tuple[dict | None, str]:
        """Variant waits for its leader's metadata."""
        leader = self.file_map.get(file_path)
        if not leader:
            return None, ""
        if leader["event"].wait(timeout=timeout):
            return leader.get("meta"), leader["name"]
        return None, leader["name"]
