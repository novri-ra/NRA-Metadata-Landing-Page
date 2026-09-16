import csv
import os
import tempfile
import unittest

from packages.shared_utils.csv_exporter import (
    fmt_kw,
    generate_microstock_csvs,
    sanitize_text,
    ss_categories,
)
from packages.shared_utils.filter import PLATFORM_RULES


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
            ],
        )
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


class FmtKwTest(unittest.TestCase):
    def test_no_filler_padding_below_min(self):
        out = fmt_kw("parrot, bird", min_count=7, max_count=50)
        self.assertNotIn("background", out)
        self.assertEqual(len(out.split(",")), 2)

    def test_truncates_to_max_count(self):
        kws = ", ".join(f"kw{i}" for i in range(60))
        out = fmt_kw(kws, min_count=0, max_count=50)
        self.assertEqual(len(out.split(",")), 50)


class SanitizeTextTest(unittest.TestCase):
    def test_freepik_does_not_swap_semicolon_to_comma(self):
        self.assertEqual(sanitize_text("a;b", semi=" "), "a b")
        self.assertEqual(sanitize_text("a, b", semi=" "), "a, b")

    def test_default_keeps_old_replacement(self):
        self.assertEqual(sanitize_text("a;b"), "a,b")


class FreepikCsvTest(unittest.TestCase):
    def test_semicolon_delimiter_and_tags_intact(self):
        tmp = tempfile.mkdtemp()
        _write_master(
            tmp,
            [
                {
                    "Filename": "red_ball.eps",
                    "Title": "Red, shiny ball",
                    "Description": "D",
                    "Keywords": "red, ball, shiny",
                    "PrimaryCategory": "Animals",
                    "SecondaryCategory": "",
                }
            ],
        )
        generate_microstock_csvs(tmp, {"Freepik"})
        out = os.path.join(tmp, "freepik_export.csv")
        self.assertTrue(os.path.exists(out))
        with open(out, "r", encoding="utf-8") as f:
            rows = list(csv.reader(f, delimiter=";"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], ["File name", "Title", "Tags"])
        self.assertEqual(rows[1][0], "red_ball.eps")
        self.assertEqual(rows[1][1], "Red, shiny ball")
        self.assertEqual(rows[1][2], "red, ball, shiny")


class ShutterstockCategoriesTest(unittest.TestCase):
    def test_maps_valid_named_categories(self):
        self.assertEqual(
            ss_categories("Animals/Wildlife", "", "x.jpg"), "Animals/Wildlife"
        )
        self.assertEqual(
            ss_categories("Animals/Wildlife", "Nature", "x.jpg"),
            "Animals/Wildlife,Nature",
        )

    def test_aliases_normalized(self):
        self.assertEqual(
            ss_categories("Food and drink", "", "x.jpg"), "Food and Drink"
        )

    def test_invalid_falls_back_to_arts_for_vectors(self):
        self.assertEqual(ss_categories("", "", "icon.eps"), "Arts")
        self.assertEqual(ss_categories("", "", "icon.svg"), "Arts")
        self.assertEqual(
            ss_categories("Not a real cat", "", "icon.ai"), "Arts"
        )

    def test_raster_default_unchanged(self):
        self.assertEqual(ss_categories("", "", "photo.jpg"), "Backgrounds/Textures")

    def test_export_uses_valid_category(self):
        tmp = tempfile.mkdtemp()
        _write_master(
            tmp,
            [
                {
                    "Filename": "icon.eps",
                    "Title": "t",
                    "Description": "a nice description here",
                    "Keywords": "one",
                    "PrimaryCategory": "",
                    "SecondaryCategory": "",
                }
            ],
        )
        generate_microstock_csvs(tmp, {"Shutterstock"})
        with open(os.path.join(tmp, "shutterstock_export.csv"), encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]["Categories"], "Arts")
        self.assertEqual(rows[0]["Keywords"], "one")


class VecteezyLimitTest(unittest.TestCase):
    def test_platform_rules_cap_at_50(self):
        rules = PLATFORM_RULES["Vecteezy"]
        self.assertEqual(rules["kw_max"], 50)
        self.assertEqual(rules["kw_min"], 5)

    def test_vecteezy_export_slices_to_50_keywords(self):
        tmp = tempfile.mkdtemp()
        kws = ", ".join(f"keyword{i}" for i in range(60))
        _write_master(
            tmp,
            [
                {
                    "Filename": "icon.eps",
                    "Title": "t",
                    "Description": "a nice description here",
                    "Keywords": kws,
                    "PrimaryCategory": "",
                    "SecondaryCategory": "",
                }
            ],
        )
        generate_microstock_csvs(tmp, {"Vecteezy"})
        out = os.path.join(tmp, "vecteezy_export.csv")
        self.assertTrue(os.path.exists(out))
        with open(out, "r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)
        exported_kws = [k.strip() for k in rows[0]["Keywords"].split(",")]
        self.assertEqual(len(exported_kws), 50)
        self.assertEqual(exported_kws[0], "keyword0")
        self.assertEqual(exported_kws[-1], "keyword49")


if __name__ == "__main__":
    unittest.main()