import unittest
import os
import csv
from packages.shared_utils.taxonomy import get_adobe_category_code, ADOBE_CATEGORY_MAP
from packages.shared_utils.csv_exporter import generate_microstock_csvs
from packages.ai_engine.service import normalize_base_url
from packages.shared_utils.cost_tracker import CostTracker
from packages.shared_utils.updater import APP_VERSION

class TestCostTracker(unittest.TestCase):
    def test_cost_calculation(self):
        tracker = CostTracker()
        cost = tracker.calculate("OpenAI", "gpt-4o-mini", 4000, 400)
        self.assertTrue(cost > 0)
        self.assertEqual(tracker.estimated_cost_usd, cost)
        
        cost2 = tracker.calculate("9router", "9router/auto", 100, 100)
        self.assertEqual(cost2, 0.0)

class TestVersionCompare(unittest.TestCase):
    def test_app_version_exists(self):
        self.assertTrue(isinstance(APP_VERSION, str))
        self.assertTrue(len(APP_VERSION.split('.')) >= 2)


class TestTaxonomy(unittest.TestCase):
    def test_adobe_category_code_valid(self):
        self.assertEqual(get_adobe_category_code("Animals"), 1)
        self.assertEqual(get_adobe_category_code("Technology"), 19)
        self.assertEqual(get_adobe_category_code("Travel"), 21)
        self.assertEqual(get_adobe_category_code("The Environment"), 5)

    def test_adobe_category_code_fallback(self):
        self.assertEqual(get_adobe_category_code("Unknown"), 8)
        self.assertEqual(get_adobe_category_code(""), 8)
        self.assertEqual(get_adobe_category_code(None), 8)

    def test_adobe_category_map_completeness(self):
        self.assertEqual(len(ADOBE_CATEGORY_MAP), 21)
        self.assertEqual(set(ADOBE_CATEGORY_MAP.values()), set(range(1, 22)))

class TestNormalizeBaseUrl(unittest.TestCase):
    def test_append_v1(self):
        self.assertEqual(normalize_base_url("http://127.0.0.1:20128"), "http://127.0.0.1:20128/v1")

    def test_strip_trailing_slash(self):
        self.assertEqual(normalize_base_url("http://localhost:8080/v1/"), "http://localhost:8080/v1")

    def test_double_trailing_slash(self):
        self.assertEqual(normalize_base_url("http://localhost:8080/v1//"), "http://localhost:8080/v1")

    def test_already_correct(self):
        self.assertEqual(normalize_base_url("https://api.9router.com/v1"), "https://api.9router.com/v1")

    def test_whitespace(self):
        self.assertEqual(normalize_base_url("  http://test.com  "), "http://test.com/v1")

    def test_empty_fallback(self):
        self.assertEqual(normalize_base_url(""), "https://api.9router.com/v1")
        self.assertEqual(normalize_base_url(None), "https://api.9router.com/v1")

class TestAdobeStockCsvExport(unittest.TestCase):
    def setUp(self):
        self.out_dir = "."
        with open("metadata_output.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Filename", "Title", "Description", "Keywords", "PrimaryCategory"])
            writer.writeheader()
            writer.writerow({
                "Filename": "test_image.jpg",
                "Title": "A " * 120,
                "Description": "Desc",
                "Keywords": ",".join([f"kw{i}" for i in range(60)]),
                "PrimaryCategory": "Animals"
            })

    def tearDown(self):
        for f in ["metadata_output.csv", "adobe_stock_export.csv"]:
            if os.path.exists(f):
                os.remove(f)

    def test_header(self):
        generate_microstock_csvs(self.out_dir, platforms={"Adobe Stock"})
        with open("adobe_stock_export.csv", "r", encoding="utf-8") as f:
            reader = list(csv.reader(f))
            self.assertEqual(reader[0], ["Filename", "Title", "Keywords", "Category", "Releases"])

    def test_category_is_numeric(self):
        generate_microstock_csvs(self.out_dir, platforms={"Adobe Stock"})
        with open("adobe_stock_export.csv", "r", encoding="utf-8") as f:
            reader = list(csv.reader(f))
            cat = reader[1][3]
            self.assertEqual(cat, "1")

    def test_title_max_200(self):
        generate_microstock_csvs(self.out_dir, platforms={"Adobe Stock"})
        with open("adobe_stock_export.csv", "r", encoding="utf-8") as f:
            reader = list(csv.reader(f))
            self.assertTrue(len(reader[1][1]) <= 200)

    def test_keywords_max_49(self):
        generate_microstock_csvs(self.out_dir, platforms={"Adobe Stock"})
        with open("adobe_stock_export.csv", "r", encoding="utf-8") as f:
            reader = list(csv.reader(f))
            keywords = [k.strip() for k in reader[1][2].split(",") if k.strip()]
            self.assertLessEqual(len(keywords), 49)

if __name__ == '__main__':
    unittest.main()
