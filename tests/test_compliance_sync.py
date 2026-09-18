import csv
import os
import tempfile
import unittest

from backend.ai.provider_router import build_metadata_prompt
from packages.shared_utils.csv_exporter import (
    fmt_kw,
    generate_microstock_csvs,
)
from packages.shared_utils.filter import autofix_compliance, validate_compliance


def _write_master(out_dir, rows):
    path = os.path.join(out_dir, "metadata_output.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "Filename",
                "Title",
                "Description",
                "Keywords",
                "PrimaryCategory",
                "SecondaryCategory",
                "IsEditorial",
            ],
        )
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


class AdobeTitleSoftCapTest(unittest.TestCase):
    import typing
    KWS: typing.ClassVar[list] = ["cat", "kitten", "ball", "wool", "furry"]

    def test_title_71_200_warns_but_stays_valid(self):
        res = validate_compliance(
            "Cute cartoon cat character playing with a wool ball vector art",  # ~60
            "a description with enough words here",
            self.KWS,
            "Adobe Stock",
        )
        self.assertTrue(res["valid"])
        self.assertEqual(res["warnings"], [])

    def test_short_title_no_warning(self):
        res = validate_compliance(
            "Cute cartoon cat", "a description with enough words here", self.KWS, "Adobe Stock"
        )
        self.assertTrue(res["valid"])
        self.assertEqual(res["warnings"], [])

    def test_long_title_warns_not_fatal(self):
        title = "Cute cartoon cat " + ("friendly " * 12)  # ~160 chars, multiple words
        res = validate_compliance(
            title, "a description with enough words here", self.KWS, "Adobe Stock"
        )
        self.assertTrue(res["valid"])
        self.assertTrue(any("70" in w for w in res["warnings"]))
        self.assertEqual(res["errors"], [])

    def test_autofix_truncates_to_word_boundary(self):
        title = "Cute cartoon cat " + ("friendly " * 12)  # ~160 chars
        fixed, _ = autofix_compliance(
            title, "a description", self.KWS, "Adobe Stock", "cat.eps"
        )
        self.assertLessEqual(len(fixed), 70)
        self.assertTrue(fixed.endswith("friendly"))
        self.assertIn("friendly", fixed)

    def test_shutterstock_no_soft_warning(self):
        res = validate_compliance(
            "Cute cartoon cat " + ("friendly " * 12),
            "a description with enough words here",
            self.KWS,
            "Shutterstock",
        )
        self.assertEqual(res["warnings"], [])


class DynamicDescriptionPromptTest(unittest.TestCase):
    def test_shutterstock_expanded_desc(self):
        prompt = build_metadata_prompt(49, "Guide", "", platform="Shutterstock")
        self.assertIn("250 to 800 characters", prompt)
        self.assertIn("avoiding keyword stuffing", prompt)

    def test_adobe_keeps_concise_desc(self):
        prompt = build_metadata_prompt(49, "Guide", "", platform="Adobe Stock")
        self.assertIn("150 to 200 characters, concise and factual", prompt)

    def test_default_platform_concise(self):
        prompt = build_metadata_prompt(49, "Guide", "")
        self.assertIn("150 to 200 characters, concise and factual", prompt)


class IStockTermCapTest(unittest.TestCase):
    def test_fmt_kw_truncates_single_long_term(self):
        long_term = "x" * 80
        out = fmt_kw(long_term, 0, 999, term_max=64)
        self.assertEqual(len(out.split(",")[0]), 64)

    def test_fmt_kw_leaves_short_terms_untouched(self):
        out = fmt_kw("sunset, sky, horizon", 0, 999, term_max=64)
        self.assertEqual(out, "sunset, sky, horizon")

    def test_fmt_kw_without_term_max_unchanged(self):
        out = fmt_kw("x" * 80, 0, 999)
        self.assertEqual(len(out), 80)

    def test_getty_export_caps_terms(self):
        tmp = tempfile.mkdtemp()
        _write_master(
            tmp,
            [
                {
                    "Filename": "news.jpg",
                    "Title": "City hall rally",
                    "Description": "A rally outside city hall.",
                    "Keywords": "rally, " + ("y" * 90),
                    "PrimaryCategory": "",
                    "SecondaryCategory": "",
                    "IsEditorial": "1",
                }
            ],
        )
        generate_microstock_csvs(tmp)
        with open(os.path.join(tmp, "getty_editorial_export.csv"), encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        terms = rows[0]["Keywords"].split(",")
        self.assertTrue(all(len(t.strip()) <= 64 for t in terms))
        self.assertIn("rally", terms[0])


if __name__ == "__main__":
    unittest.main()