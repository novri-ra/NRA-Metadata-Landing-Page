import os
import tempfile
import unittest

from backend.ai.provider_router import _mask_secret, build_metadata_prompt
from packages.shared_utils.filter import (
    PLATFORM_RULES,
    blacklist_path,
    clean_metadata,
    is_placeholder_title,
    sanitize_keywords,
)


class PromptPlatformLimitTest(unittest.TestCase):
    def _prompt(self, platform):
        return build_metadata_prompt(49, "Guide text", "", platform=platform)

    def test_freepik_title_limit_100(self):
        self.assertIn("(max 100 characters):", self._prompt("Freepik"))

    def test_shutterstock_title_limit_150(self):
        self.assertIn("(max 150 characters):", self._prompt("Shutterstock"))

    def test_defaults_when_platform_unknown(self):
        self.assertIn("(max 180 characters):", self._prompt("Unknown Platform"))

    def test_matches_platform_rules(self):
        for plat, rules in PLATFORM_RULES.items():
            p = self._prompt(plat)
            self.assertIn(f"(max {rules['title_max_chars']} characters):", p, plat)
            self.assertIn(f"(max {rules['desc_max_chars']} characters):", p, plat)


class FallbackTokenStripTest(unittest.TestCase):
    def test_clean_metadata_strips_fallback_tokens(self):
        meta = {
            "title": "Red Ball",
            "description": "A red ball for sports",
            "category": "Objects",
            "keywords": ["ball", "error", "fallback", "Error", "Fallback", "toy"],
        }
        cleaned = clean_metadata(meta, target_kw=10)
        lowered = [k.lower() for k in cleaned["keywords"]]
        self.assertNotIn("error", lowered)
        self.assertNotIn("fallback", lowered)
        self.assertIn("ball", lowered)
        self.assertIn("toy", lowered)

    def test_sanitize_keywords_strips_fallback(self):
        kws = sanitize_keywords(["sun", "error", "fallback", "sky"], target_kw=10)
        self.assertEqual(kws, ["sun", "sky"])

    def test_placeholder_title_blocks_embed(self):
        # save_manual refuses to embed when the title is empty/placeholder.
        self.assertTrue(is_placeholder_title(""))
        self.assertTrue(is_placeholder_title("   "))
        self.assertTrue(is_placeholder_title("Unknown Title"))
        self.assertFalse(is_placeholder_title("Red Ball"))
        self.assertFalse(is_placeholder_title("Red"))


class KeywordOrderTest(unittest.TestCase):
    def test_dedup_preserves_first_occurrence_order(self):
        kws = sanitize_keywords(["ball", "sport", "ball", "red", "sport"], target_kw=10)
        self.assertEqual(kws, ["ball", "sport", "red"])

    def test_clean_metadata_keeps_ai_order_padding_last(self):
        meta = {
            "title": "Colorful Parrot",
            "description": (
                "A colorful parrot perched on a branch, vivid feathers, tropical jungle"
            ),
            "category": "Animals",
            "keywords": ["parrot", "bird", "tropical"],
        }
        cleaned = clean_metadata(meta, target_kw=8)
        # AI keywords stay first, in order; padding is appended after them.
        self.assertEqual(cleaned["keywords"][:3], ["parrot", "bird", "tropical"])
        self.assertGreaterEqual(len(cleaned["keywords"]), 6)
        self.assertLessEqual(len(cleaned["keywords"]), 8)


class BlacklistPathTest(unittest.TestCase):
    def test_path_is_absolute_and_config_anchored(self):
        from backend.core import config_manager

        self.assertEqual(
            blacklist_path(),
            os.path.join(config_manager.get_config_dir(), "blacklist.txt"),
        )
        self.assertTrue(os.path.isabs(blacklist_path()))

    def test_path_unaffected_by_cwd(self):
        from backend.core import config_manager

        cfg_dir = config_manager.get_config_dir()
        before = blacklist_path()
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            self.assertEqual(blacklist_path(), before)
            self.assertEqual(
                blacklist_path(), os.path.join(cfg_dir, "blacklist.txt")
            )
        finally:
            os.chdir(cwd)


class SecretMaskTest(unittest.TestCase):
    def test_mask_secret_redacts_api_key(self):
        msg = "url https://generativelanguage.googleapis.com/v1beta/models?key=SECRET123"
        self.assertNotIn("SECRET123", _mask_secret(msg, "SECRET123"))
        self.assertIn("***", _mask_secret(msg, "SECRET123"))

    def test_mask_secret_handles_absent_secret(self):
        self.assertEqual(_mask_secret("plain message", ""), "plain message")


if __name__ == "__main__":
    unittest.main()