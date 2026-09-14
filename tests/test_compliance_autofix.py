import os
import tempfile
import unittest
from unittest import mock

from backend.ai.provider_router import build_metadata_prompt
from backend.core.worker_pool import FileWorkerPool
from packages.shared_utils.csv_exporter import is_illus
from packages.shared_utils.filter import autofix_compliance, validate_compliance


class AutofixRecoveryTest(unittest.TestCase):
    def test_recovers_placeholder_title_from_filename(self):
        title, _ = autofix_compliance(
            "Unknown Title", "A red ball", ["ball"], "Adobe Stock",
            "icon_20250101_xyz.eps",
        )
        self.assertNotEqual(title, "Unknown Title")
        self.assertIn("Icon", title)
        self.assertNotIn("20250101", title)

    def test_pads_keywords_below_platform_min(self):
        title, kws = autofix_compliance(
            "Red Ball",
            "A shiny red spherical ball for sports, rubber material used for tennis match practice",
            ["ball"],
            "Shutterstock",
            "x.jpg",
        )
        self.assertGreaterEqual(len(kws), 7)
        self.assertFalse(any(k.lower() in ("error", "fallback") for k in kws))
        self.assertTrue(all(k for k in kws))
        self.assertTrue(title)

    def test_strips_fallback_keyword_tokens(self):
        _, kws = autofix_compliance("Nice Title", "some words", ["error", "fallback", "ball"], "Adobe Stock")
        self.assertNotIn("error", kws)
        self.assertNotIn("fallback", kws)
        self.assertIn("ball", kws)


class DescriptionValidationTest(unittest.TestCase):
    KWS = ["one", "two", "three", "four", "five", "six", "seven"]

    def test_short_description_flagged(self):
        res = validate_compliance(
            "A title with enough words here", "short desc", self.KWS, "Shutterstock"
        )
        self.assertFalse(res["valid"])
        self.assertTrue(any("Description" in e for e in res["errors"]))

    def test_empty_description_flagged(self):
        res = validate_compliance(
            "A title with enough words here", "", self.KWS, "Shutterstock"
        )
        self.assertFalse(res["valid"])
        self.assertTrue(any("Description" in e for e in res["errors"]))

    def test_valid_description_passes(self):
        res = validate_compliance(
            "A title with enough words here",
            "An informative description with several words",
            self.KWS,
            "Shutterstock",
        )
        self.assertTrue(res["valid"])


class VectorDetectionTest(unittest.TestCase):
    def test_png_not_vector(self):
        self.assertEqual(is_illus("photo.png"), "no")

    def test_vector_extensions_yes(self):
        self.assertEqual(is_illus("icon.eps"), "yes")
        self.assertEqual(is_illus("icon.svg"), "yes")
        self.assertEqual(is_illus("icon.ai"), "yes")
        self.assertEqual(is_illus("photo.jpg"), "no")


class PromptExtraContextTest(unittest.TestCase):
    def test_extra_prompt_interpolated(self):
        prompt = build_metadata_prompt(
            49, "Balanced visual description for general stock assets.",
            "Focus on pastel colors",
        )
        self.assertIn("Focus on pastel colors", prompt)
        self.assertIn("Analyze this image", prompt)

    def test_extra_prompt_absent_when_empty(self):
        prompt = build_metadata_prompt(49, "Guide text", "")
        self.assertNotIn("Additional Context", prompt)


class TargetKwPassThroughTest(unittest.TestCase):
    def _run_process(self, options):
        class FakeAI:
            def __init__(self):
                self.kw = None

            def generate_metadata(self, preview, target_kw, *args, **kwargs):
                self.kw = target_kw
                return {"fail_reason": "auth", "error": True}

        pool = FileWorkerPool()
        pool._emit = lambda name, *a: None
        tmp = tempfile.mkdtemp()
        preview = os.path.join(tmp, "preview.jpg")
        open(preview, "w").close()
        ai = FakeAI()
        with mock.patch(
            "backend.core.worker_pool.extract_preview_image", return_value=preview
        ):
            pool._process_file(os.path.join(tmp, "x.eps"), tmp, ai, options, object())
        return ai.kw

    def test_target_kw_passed_to_generate_metadata(self):
        options = {"platform": "Shutterstock", "target_kw": 32,
                   "style_preset": "General Commercial",
                   "extra_prompt": "", "custom_kw": "", "custom_kw_pos": "Start (Priority)"}
        self.assertEqual(self._run_process(options), 32)


if __name__ == "__main__":
    unittest.main()