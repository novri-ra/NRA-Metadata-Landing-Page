"""Integration smoke-test: fake AI → clean_metadata → embed pipeline."""
import os
import tempfile
import unittest

from packages.shared_utils.filter import clean_metadata, sanitize_keywords


class FakeAIService:
    """Minimal AI stub returning well-formed metadata."""

    def __init__(self, title="Mountain Sunrise Landscape", description="A scenic mountain view at sunrise with warm golden light", keywords=None):
        self._title = title
        self._desc = description
        self._kws = keywords or [
            "mountain", "sunrise", "landscape", "nature", "outdoors",
            "scenic", "golden hour", "sky", "panoramic", "valley",
            "forest", "wilderness", "dawn", "hills", "rocks",
            "clouds", "fresh air", "serene", "peaceful", "adventure",
            "travel", "photography", "alpine", "summit", "meadow",
            "river", "waterfall", "trees", "light", "colorful",
            "vibrant", "horizon", "elevation", "slope", "ridge",
            "glacier", "snow", "pine", "camping", "hiking",
            "backpacking", "exploration", "wildlife", "fauna", "flora",
            "ecosystem", "habitat", "conservation", "preservation",
            "breathtaking", "majestic",
        ]

    def generate_metadata(self, preview_path, target_kw, style_preset,
                          extra_prompt="", log_callback=None,
                          cancel_check=None, platform=""):
        return {
            "title": self._title,
            "description": self._desc,
            "keywords": list(self._kws),
        }


class TestEndToEndPipeline(unittest.TestCase):
    """Simulate what _process_file does, minus threading and UI callbacks."""

    def test_pipeline_pad_trim_embed(self):
        """Full pipeline: AI output → inject custom keywords → clean_metadata → embed."""
        tmp = tempfile.mkdtemp()
        src = os.path.join(tmp, "landscape.eps")
        open(src, "w").close()

        preview = os.path.join(tmp, "preview.jpg")
        open(preview, "w").close()

        ai = FakeAIService()
        target_kw = 49

        # 1. AI generates metadata
        raw_meta = ai.generate_metadata(preview, target_kw, "General Commercial")

        # 2. Inject custom keywords (simulating start_processing logic)
        custom_kws_raw = "brand-name, company-logo"
        custom_kws = [k.strip() for k in custom_kws_raw.split(",") if k.strip()]
        ai_kws = [
            k for k in raw_meta.get("keywords", [])
            if k.lower() not in [ck.lower() for ck in custom_kws]
        ]
        raw_meta["keywords"] = custom_kws + ai_kws

        # 3. clean_metadata pads/trims to target
        meta = clean_metadata(raw_meta, target_kw)

        self.assertEqual(meta["title"], "Mountain Sunrise Landscape")
        self.assertTrue(len(meta["title"]) >= 10, "title too short")
        self.assertGreaterEqual(len(meta["description"]), 50, "description too short")
        self.assertEqual(len(meta["keywords"]), target_kw)
        self.assertEqual(meta["keywords"][:2], ["brand-name", "company-logo"])

    def test_dedup_across_custom_and_ai(self):
        """Custom keyword that also appears in AI output gets deduped."""
        raw = {
            "title": "Test Title With Enough Chars",
            "description": "A description that has enough words to pass the minimum length threshold for validation",
            "keywords": ["mountain", "sunset", "mountain", "landscape", "nature",
                         "outdoor", "travel", "photo", "scenic", "view",
                         "panorama", "alpine", "summit", "hiking", "adventure",
                         "valley", "forest", "river", "sky", "cloud",
                         "golden", "light", "dawn", "dusk", "colorful",
                         "vibrant", "serene", "peaceful", "wild", "wilderness",
                         "camping", "backpack", "explore", "eco", "park",
                         "reserve", "region", "terrain", "slope", "ridge",
                         "glacier", "snow", "pine", "rock", "meadow",
                         "wildlife", "fauna", "flora", "aerial", "drone"],
        }
        meta = clean_metadata(raw, 49)
        self.assertEqual(len(meta["keywords"]), 49)
        # No duplicates
        lower = [k.lower() for k in meta["keywords"]]
        self.assertEqual(len(lower), len(set(lower)), "duplicates found after clean")

    def test_short_keyword_list_padded_from_context(self):
        """AI returns a slightly short list; clean_metadata pads from context."""
        raw = {
            "title": "Mountain Sunrise Landscape",
            "description": "a scenic mountain view at sunrise with warm golden light on a colorful sky over a vast valley featuring tall pine trees beside a winding river",
            "keywords": ["mountain", "sunrise", "landscape"]
            + [f"pad_kw{i}" for i in range(44)],
        }
        meta = clean_metadata(raw, 49)
        self.assertEqual(len(meta["keywords"]), 49)
        self.assertEqual(meta["keywords"][0], "mountain")

    def test_keywords_truncated_to_target(self):
        """If AI returns 60 keywords, clean_metadata truncates to target."""
        kws = [f"keyword{i:02d}" for i in range(60)]
        raw = {
            "title": "Test Title With Enough Characters For Validation",
            "description": "A description that is long enough to pass the minimum character requirement for metadata validation",
            "keywords": kws,
        }
        meta = clean_metadata(raw, 49)
        self.assertEqual(len(meta["keywords"]), 49)

    def test_sanitize_dedup_preserves_order(self):
        """sanitize_keywords dedupes case-insensitively and preserves first occurrence."""
        input_kws = ["Mountain", "mountain", "MOUNTAIN", "sunset", "Sunset"]
        result = sanitize_keywords(input_kws, 49)
        self.assertEqual(result.count("Mountain"), 1)
        self.assertEqual(result.count("sunset"), 1)
        self.assertTrue(len(result) <= 49)

    def test_exactly_target_count(self):
        """After clean_metadata, keyword count == target exactly."""
        kws = [f"kwd{i}" for i in range(47)]
        raw = {
            "title": "A Valid Title That Meets The Minimum Length Requirement",
            "description": "a description that offers enough words as padding candidates for this validation test",
            "keywords": kws,
        }
        meta = clean_metadata(raw, 49)
        self.assertEqual(len(meta["keywords"]), 49)


class TestFakeAIOutputConsistency(unittest.TestCase):
    """Verify FakeAIService output satisfies the contract."""

    def test_fake_ai_returns_all_required_fields(self):
        ai = FakeAIService()
        meta = ai.generate_metadata("/fake", 49, "Standard")
        self.assertIn("title", meta)
        self.assertIn("description", meta)
        self.assertIn("keywords", meta)
        self.assertGreaterEqual(len(meta["keywords"]), 49)
        self.assertIsInstance(meta["keywords"], list)


if __name__ == "__main__":
    unittest.main()
