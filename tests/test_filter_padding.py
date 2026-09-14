import unittest

from packages.shared_utils.filter import _context_keyword_candidates, clean_metadata


class MinKwPaddingTest(unittest.TestCase):
    def test_pads_short_keyword_list_from_title_and_description(self):
        meta = {
            "title": "Colorful Parrot",
            "description": (
                "A colorful parrot perched on a branch, vivid feathers, tropical jungle background"
            ),
            "category": "Animals",
            "keywords": ["parrot", "bird"],
        }
        cleaned = clean_metadata(meta, max_kw=8, min_kw=6)
        self.assertGreaterEqual(len(cleaned["keywords"]), 6)
        self.assertLessEqual(len(cleaned["keywords"]), 8)
        self.assertIn("parrot", cleaned["keywords"])

    def test_no_padding_when_already_at_or_above_min(self):
        meta = {
            "title": "Parrot",
            "description": "A colorful parrot",
            "category": "Animals",
            "keywords": ["parrot", "bird", "tropical", "feathers", "jungle", "vivid"],
        }
        cleaned = clean_metadata(meta, max_kw=8, min_kw=6)
        self.assertEqual(len(cleaned["keywords"]), 6)
        self.assertEqual(cleaned["keywords"][0], "parrot")

    def test_candidates_skip_stopwords_and_blacklisted(self):
        existing = {"parrot"}
        candidates = _context_keyword_candidates(
            "The and a but at with the colorful tropical red parrot perches on a branch", existing, 3
        )
        self.assertNotIn("the", candidates)
        self.assertNotIn("with", candidates)
        self.assertNotIn("parrot", candidates)
        self.assertEqual(len(candidates), 3)