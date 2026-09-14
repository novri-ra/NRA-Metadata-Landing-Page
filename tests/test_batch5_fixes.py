import csv
import os
import tempfile
import unittest

from backend.ai.provider_router import AIService
from backend.core.worker_pool import resolve_target_kw
from packages.shared_utils.csv_exporter import upsert_metadata_csv
from packages.shared_utils.filter import calculate_quality_score


class QualityScorePlatformTest(unittest.TestCase):
    def test_shutterstock_flags_4_word_title_freepik_accepts(self):
        # Shutterstock min title words = 5; Freepik raised to 5 words (M-A4),
        # so a 4-word title is now flagged for both platforms.
        ss = calculate_quality_score("Red Ball On Grass", "A red ball on green grass", ["ball"], "Shutterstock")
        fp = calculate_quality_score("Red Ball On Grass", "A red ball on green grass", ["ball"], "Freepik")
        self.assertTrue(
            any("Title too short (< 5 words)" in i for i in ss["issues"]),
            ss["issues"],
        )
        self.assertTrue(
            any("Title too short (< 5 words)" in i for i in fp["issues"]),
            fp["issues"],
        )

    def test_five_word_title_passes_both(self):
        title = "Red Ball On Green Grass"
        for platform in ("Shutterstock", "Freepik"):
            score = calculate_quality_score(
                title, "A red ball on green grass", ["ball", "sport", "outdoor", "red", "green"], platform
            )
            self.assertFalse(
                any("Title too short" in i for i in score["issues"]),
                (platform, score["issues"]),
            )

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


class TargetKwTest(unittest.TestCase):
    def test_default_target_kw_is_49(self):
        self.assertEqual(resolve_target_kw({}), 49)

    def test_target_kw_from_options(self):
        self.assertEqual(resolve_target_kw({"target_kw": 30}), 30)


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