import csv
import os
import tempfile
import unittest

from backend.ai.provider_router import build_metadata_prompt
from packages.shared_utils.csv_exporter import (
    apply_ai_disclosure,
    fmt_desc,
    generate_microstock_csvs,
)
from packages.shared_utils.filter import (
    PLATFORM_RULES,
    clean_title,
    sanitize_keywords,
    validate_compliance,
)


def _write_master(out_dir, rows, fieldnames=None):
    path = os.path.join(out_dir, "metadata_output.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=fieldnames
            or [
                "Filename",
                "Title",
                "Description",
                "Keywords",
                "PrimaryCategory",
                "SecondaryCategory",
                "IsAI",
            ],
        )
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


class TitleCleaningTest(unittest.TestCase):
    def test_clean_title_strips_spam_prefixes(self):
        self.assertEqual(clean_title("Vector cute cat playing"), "cute cat playing")
        self.assertEqual(clean_title("Set of colorful flowers"), "colorful flowers")
        self.assertEqual(clean_title("Collection of vintage icons"), "vintage icons")
        self.assertEqual(clean_title("Illustration of a red kite"), "a red kite")
        self.assertEqual(clean_title("Isolated soccer ball on grass"), "soccer ball on grass")

    def test_clean_title_leaves_normal_titles_untouched(self):
        self.assertEqual(clean_title("Cute cat playing with wool ball"), "Cute cat playing with wool ball")

    def test_validator_flags_banned_prefix(self):
        res = validate_compliance(
            "Vector cute cat", "a description with enough words here", ["cat"], "Adobe Stock"
        )
        self.assertFalse(res["valid"])
        self.assertTrue(any("spam prefix" in e for e in res["errors"]))


class KeywordCleanupTest(unittest.TestCase):
    def test_stop_words_removed(self):
        kws = sanitize_keywords(["sunset", "and", "the", "of", "sky"], target_kw=10)
        self.assertNotIn("and", kws)
        self.assertNotIn("the", kws)
        self.assertNotIn("of", kws)
        self.assertEqual(kws, ["sunset", "sky"])

    def test_plural_singular_dedup_keeps_singular(self):
        kws = sanitize_keywords(["cats", "cat", "flowers", "flower"], target_kw=10)
        self.assertEqual(len(kws), 2)
        self.assertIn("cat", kws)
        self.assertNotIn("cats", kws)

    def test_dedup_still_truncates_to_target(self):
        kws = sanitize_keywords([f"kwd{i}" for i in range(60)], target_kw=49)
        self.assertEqual(len(kws), 49)


class ShutterstockDescTest(unittest.TestCase):
    def test_short_description_not_dot_padded(self):
        out = fmt_desc("short", 2000)
        self.assertEqual(out.rstrip("."), out)
        self.assertNotIn(".", out)

    def test_five_word_description_passes_validation(self):
        res = validate_compliance(
            "A title with enough words",
            "These five words exactly count",  # 5 words
            ["a", "b", "c", "d", "e", "f", "g"],
            "Shutterstock",
        )
        self.assertTrue(res["valid"])

    def test_four_word_description_fails_validation(self):
        res = validate_compliance(
            "A title with enough words",
            "Only four words here",  # 4 words
            ["a", "b", "c", "d", "e", "f", "g"],
            "Shutterstock",
        )
        self.assertFalse(res["valid"])
        self.assertTrue(any("Description" in e for e in res["errors"]))


class FreepikTitleTest(unittest.TestCase):
    def test_platform_rule_cap_raised_to_200(self):
        self.assertEqual(PLATFORM_RULES["Freepik"]["title_max_chars"], 200)

    def test_export_keeps_title_up_to_200_chars(self):
        tmp = tempfile.mkdtemp()
        title = "Cute " + "longword " * 30  # ~280 chars
        _write_master(
            tmp,
            [
                {
                    "Filename": "big.eps",
                    "Title": title,
                    "Description": "a nice description here",
                    "Keywords": "one",
                    "PrimaryCategory": "",
                    "SecondaryCategory": "",
                }
            ],
        )
        generate_microstock_csvs(tmp, {"Freepik"})
        with open(os.path.join(tmp, "freepik_export.csv"), encoding="utf-8") as f:
            rows = list(csv.reader(f, delimiter=";"))
        self.assertLessEqual(len(rows[1][1]), 200)


class AdobePromptTargetTest(unittest.TestCase):
    def test_adobe_prompt_targets_50_70_chars(self):
        prompt = build_metadata_prompt(49, "Guide", "", platform="Adobe Stock")
        self.assertIn("50 to 70 characters", prompt)

    def test_generic_prompt_keeps_legacy_target(self):
        prompt = build_metadata_prompt(49, "Guide", "")
        self.assertIn("50 to 90 characters", prompt)


class DreamstimeDisclosureTest(unittest.TestCase):
    def test_apply_disclosure_prepends_when_ai(self):
        self.assertEqual(
            apply_ai_disclosure("A cute cat.", True),
            "Generative AI illustration. A cute cat.",
        )

    def test_apply_disclosure_skips_non_ai_and_empty(self):
        self.assertEqual(apply_ai_disclosure("A cute cat.", False), "A cute cat.")
        self.assertEqual(apply_ai_disclosure("", True), "")

    def test_apply_disclosure_does_not_duplicate(self):
        out = apply_ai_disclosure("Generative AI illustration. A cute cat.", True)
        self.assertEqual(out.count("Generative AI illustration."), 1)

    def test_dreamstime_csv_carries_disclosure_for_ai_rows(self):
        tmp = tempfile.mkdtemp()
        _write_master(
            tmp,
            [
                {
                    "Filename": "ai_art.eps",
                    "Title": "Cute cat",
                    "Description": "A cute cartoon cat.",
                    "Keywords": "cat, cute",
                    "PrimaryCategory": "",
                    "SecondaryCategory": "",
                    "IsAI": "1",
                },
                {
                    "Filename": "photo.jpg",
                    "Title": "Sunset",
                    "Description": "A nice sunset.",
                    "Keywords": "sunset, sky",
                    "PrimaryCategory": "",
                    "SecondaryCategory": "",
                    "IsAI": "",
                },
            ],
        )
        generate_microstock_csvs(tmp, {"Dreamstime"})
        with open(os.path.join(tmp, "dreamstime_export.csv"), encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]["Description"].startswith("Generative AI illustration."))
        self.assertFalse(rows[1]["Description"].startswith("Generative AI illustration."))


if __name__ == "__main__":
    unittest.main()