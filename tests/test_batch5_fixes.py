import csv
import os
import tempfile
import unittest

from backend.ai.provider_router import AIService
from backend.core.worker_pool import resolve_kw_range
from packages.shared_utils.csv_exporter import upsert_metadata_csv
from packages.shared_utils.filter import calculate_quality_score


class QualityScorePlatformTest(unittest.TestCase):
    def test_shutterstock_flags_4_word_title_freepik_accepts(self):
        # Shutterstock min title words = 5, Freepik = 3.
        ss = calculate_quality_score("Red Ball On Grass", "A red ball on green grass", ["ball"], "Shutterstock")
        fp = calculate_quality_score("Red Ball On Grass", "A red ball on green grass", ["ball"], "Freepik")
        self.assertTrue(
            any("Title too short (< 5 words)" in i for i in ss["issues"]),
            ss["issues"],
        )
        self.assertFalse(
            any("Title too short" in i for i in fp["issues"]), fp["issues"]
        )
        self.assertLess(ss["score"], fp["score"])

    def test_shutterstock_flags_5_keywords_min7(self):
        kws = ["one", "two", "three", "four", "five"]
        ss = calculate_quality_score(
            "Five Simple Product Keywords", "A product with five keywords listed here in words", kws, "Shutterstock"
        )
        self.assertTrue(any("min 7" in i for i in ss["issues"]), ss["issues"])
        generic = calculate_quality_score(
            "Five Simple Product Keywords", "A product with five keywords listed here in words", kws
        )
        self.assertFalse(any("Too few keywords" in i for i in generic["issues"]))


class CsvUpsertTest(unittest.TestCase):
    def test_second_save_preserves_first_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            master = os.path.join(tmp, "metadata_output.csv")
            upsert_metadata_csv(master, "one.jpg", "First Title", "First desc", ["a", "b"])
            upsert_metadata_csv(master, "two.jpg", "Second Title", "Second desc", ["c", "d"])
            with open(master, "r", encoding="utf-8", newline="") as f:
                rows = list(csv.reader(f))
            self.assertEqual(len(rows), 3)  # header + 2 files
            self.assertEqual(rows[1][0], "one.jpg")
            self.assertEqual(rows[2][0], "two.jpg")
            self.assertEqual(rows[2][2], "Second desc")

    def test_resave_updates_row_not_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            master = os.path.join(tmp, "metadata_output.csv")
            upsert_metadata_csv(master, "one.jpg", "Old Title", "old", ["a"])
            upsert_metadata_csv(master, "two.jpg", "Two", "two", ["b"])
            upsert_metadata_csv(master, "one.jpg", "New Title", "new", ["x", "y"])
            with open(master, "r", encoding="utf-8", newline="") as f:
                rows = list(csv.reader(f))
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[1][0], "one.jpg")
            self.assertEqual(rows[1][1], "New Title")
            self.assertEqual(rows[1][3], "x,y")


class KwRangeLockTest(unittest.TestCase):
    def test_min_only_change_without_override_still_auto_aligns(self):
        options = {
            "platform": "Shutterstock",
            "min_kw": 20,  # user nudged the lower bound only
            "max_kw": 49,
            "kw_locked": False,  # no Custom Range override checked
        }
        min_kw, max_kw = resolve_kw_range(options)
        self.assertEqual((min_kw, max_kw), (7, 50), "platform auto-align stays active")

    def test_explicit_override_keeps_user_range(self):
        options = {
            "platform": "Shutterstock",
            "min_kw": 20,
            "max_kw": 49,
            "kw_locked": True,  # user checked Custom Range override
        }
        min_kw, max_kw = resolve_kw_range(options)
        self.assertEqual((min_kw, max_kw), (20, 49))


class VisionPatternTest(unittest.TestCase):
    @staticmethod
    def _router(provider="Mistral"):
        r = AIService.__new__(AIService)
        r.provider = provider
        return r

    def test_mistral_small_blocked_base_only(self):
        router = self._router("Mistral")
        self.assertFalse(router._is_vision_capable("mistral-small"))
        # Future vision variant of the same base name is NOT blocked.
        self.assertTrue(router._is_vision_capable("mistral-small-vision"))

    def test_old_substring_traps_still_blocked(self):
        router = self._router()
        self.assertFalse(router._is_vision_capable("dall-e-3"))
        self.assertFalse(router._is_vision_capable("gpt-3.5-turbo"))
        self.assertFalse(router._is_vision_capable("text-embedding-ada-002"))
        self.assertFalse(router._is_vision_capable("whisper-1"))


if __name__ == "__main__":
    unittest.main()