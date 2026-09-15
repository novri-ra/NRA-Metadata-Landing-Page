import os
import tempfile
import time
import unittest
from unittest import mock

from backend.ai.provider_router import build_metadata_prompt
from backend.core.worker_pool import FileWorkerPool
from packages.shared_utils.filter import clean_metadata


class PromptExactCountTest(unittest.TestCase):
    def test_prompt_enforces_exact_49_keywords(self):
        prompt = build_metadata_prompt(49, "Guide", "")
        self.assertIn("EXACTLY 49 keywords separated by commas", prompt)
        self.assertIn("Not 48, not 50, but EXACTLY 49 keywords", prompt)

    def test_prompt_reflects_custom_target(self):
        prompt = build_metadata_prompt(30, "Guide", "")
        self.assertIn("EXACTLY 30 keywords", prompt)

    def test_prompt_has_title_and_description_specs(self):
        prompt = build_metadata_prompt(49, "Guide", "")
        self.assertIn("50 to 90 characters", prompt)
        self.assertIn("150 to 200 characters", prompt)
        self.assertIn('{"title"', prompt)


class CleanMetadataExactTargetTest(unittest.TestCase):
    def test_trims_to_exact_target(self):
        meta = {"title": "T", "description": "D", "keywords": [f"kw{i}" for i in range(60)]}
        cleaned = clean_metadata(meta, target_kw=49)
        self.assertEqual(len(cleaned["keywords"]), 49)

    def test_pads_to_exact_target_from_context(self):
        meta = {
            "title": "Colorful Parrot",
            "description": (
                "A colorful parrot perched on a branch with vivid feathers "
                "in a tropical jungle background"
            ),
            "keywords": ["parrot", "bird"],
        }
        cleaned = clean_metadata(meta, target_kw=8)
        self.assertEqual(len(cleaned["keywords"]), 8)


class FileStatusEventTest(unittest.TestCase):
    def test_event_sequence_processing_then_done(self):
        events = []

        class FakeAI:
            def generate_metadata(self, *args, **kwargs):
                return {
                    "title": "Red Ball",
                    "description": "A red ball for sports and play.",
                    "keywords": ["ball", "red", "sport"],
                }

        pool = FileWorkerPool()
        pool._emit = lambda name, *a: (
            events.append((name,) + tuple(a)) if name == "file_status" else None
        )
        pool.processor.embed_metadata = mock.Mock(return_value=True)

        tmp = tempfile.mkdtemp()
        preview = os.path.join(tmp, "preview.jpg")
        open(preview, "w").close()
        src = os.path.join(tmp, "x.eps")
        open(src, "w").close()

        with mock.patch(
            "backend.core.worker_pool.extract_preview_image", return_value=preview
        ), mock.patch("backend.core.worker_pool.get_file_hash", return_value="h1"), mock.patch(
            "backend.core.worker_pool.get_cached_metadata", return_value=None
        ):
            pool._process_file(
                src,
                tmp,
                FakeAI(),
                {"target_kw": 49, "style_preset": "Standard", "extra_prompt": ""},
                mock.Mock(),
            )

        states = [e[2] for e in events]
        self.assertEqual(states[0], "processing")
        self.assertEqual(states[-1], "done")

    def test_error_path_emits_failed(self):
        events = []

        class FakeAI:
            def generate_metadata(self, *args, **kwargs):
                return {"error": True, "error_details": "boom"}

        pool = FileWorkerPool()
        pool._emit = lambda name, *a: (
            events.append((name,) + tuple(a)) if name == "file_status" else None
        )

        tmp = tempfile.mkdtemp()
        preview = os.path.join(tmp, "preview.jpg")
        open(preview, "w").close()

        with mock.patch(
            "backend.core.worker_pool.extract_preview_image", return_value=preview
        ), mock.patch("backend.core.worker_pool.get_file_hash", return_value="h1"), mock.patch(
            "backend.core.worker_pool.get_cached_metadata", return_value=None
        ):
            pool._process_file(
                os.path.join(tmp, "x.eps"),
                tmp,
                FakeAI(),
                {"target_kw": 49, "style_preset": "Standard", "extra_prompt": ""},
                mock.Mock(),
            )

        self.assertEqual(events[-1][2], "failed")

    def test_embed_failure_emits_failed_not_done(self):
        events = []

        class FakeAI:
            def generate_metadata(self, *args, **kwargs):
                return {"title": "Red Ball", "description": "A red ball.", "keywords": ["red"]}

        pool = FileWorkerPool()
        pool._emit = lambda name, *a: (
            events.append((name,) + tuple(a)) if name == "file_status" else None
        )
        pool.processor.embed_metadata = mock.Mock(return_value=False)

        tmp = tempfile.mkdtemp()
        preview = os.path.join(tmp, "preview.jpg")
        open(preview, "w").close()
        src = os.path.join(tmp, "x.eps")
        open(src, "w").close()

        with mock.patch(
            "backend.core.worker_pool.extract_preview_image", return_value=preview
        ), mock.patch("backend.core.worker_pool.get_file_hash", return_value="h1"), mock.patch(
            "backend.core.worker_pool.get_cached_metadata", return_value=None
        ):
            pool._process_file(
                src,
                tmp,
                FakeAI(),
                {"target_kw": 49, "style_preset": "Standard", "extra_prompt": ""},
                mock.Mock(),
            )

        states = [e[2] for e in events]
        self.assertEqual(states[-1], "failed")

    def test_cancel_branch_emits_failed_not_done(self):
        events = []

        class FakeAI:
            def __init__(self, pool):
                self._pool = pool

            def generate_metadata(self, *args, **kwargs):
                self._pool.cancel_flag = True
                return {"title": "Red Ball", "description": "A red ball.", "keywords": ["red"]}

        pool = FileWorkerPool()
        pool._emit = lambda name, *a: (
            events.append((name,) + tuple(a)) if name == "file_status" else None
        )

        tmp = tempfile.mkdtemp()
        preview = os.path.join(tmp, "preview.jpg")
        open(preview, "w").close()
        src = os.path.join(tmp, "x.eps")
        open(src, "w").close()

        with mock.patch(
            "backend.core.worker_pool.extract_preview_image", return_value=preview
        ), mock.patch("backend.core.worker_pool.get_file_hash", return_value="h1"), mock.patch(
            "backend.core.worker_pool.get_cached_metadata", return_value=None
        ):
            pool._process_file(
                src,
                tmp,
                FakeAI(pool),
                {"target_kw": 49, "style_preset": "Standard", "extra_prompt": ""},
                mock.Mock(),
            )

        self.assertEqual(events[-1][2], "failed")


class CooldownFullDelayTest(unittest.TestCase):
    def test_cooldown_waits_full_user_delay_uninterrupted(self):
        started = time.monotonic()
        done = {"v": False}

        def fake_embed(*a, **k):
            return True

        class FakeAI:
            def generate_metadata(self, *args, **kwargs):
                done["v"] = True
                return {
                    "title": "Red Ball",
                    "description": "A red ball for sports and play.",
                    "keywords": ["ball"],
                }

        pool = FileWorkerPool()
        pool.processor.embed_metadata = mock.Mock(side_effect=fake_embed)

        tmp = tempfile.mkdtemp()
        preview = os.path.join(tmp, "preview.jpg")
        open(preview, "w").close()
        src = os.path.join(tmp, "x.eps")
        open(src, "w").close()

        with mock.patch(
            "backend.core.worker_pool.extract_preview_image", return_value=preview
        ), mock.patch("backend.core.worker_pool.get_file_hash", return_value="h1"), mock.patch(
            "backend.core.worker_pool.get_cached_metadata", return_value=None
        ):
            pool._process_file(
                src,
                tmp,
                FakeAI(),
                {"target_kw": 49, "style_preset": "Standard", "extra_prompt": "", "delay": 0.4},
                mock.Mock(),
            )

        # Full delay honored (no 5s cap, but also not truncated to 5s)
        elapsed = time.monotonic() - started
        self.assertGreaterEqual(elapsed, 0.35)

    def test_cooldown_interruptible_by_cancel(self):
        pool = FileWorkerPool()

        class FakeAI:
            def generate_metadata(self, *args, **kwargs):
                return {"title": "T", "description": "D", "keywords": ["k"]}

        pool.processor.embed_metadata = mock.Mock(return_value=True)

        tmp = tempfile.mkdtemp()
        preview = os.path.join(tmp, "preview.jpg")
        open(preview, "w").close()
        src = os.path.join(tmp, "x.eps")
        open(src, "w").close()
        pool.cancel()

        started = time.monotonic()
        with mock.patch(
            "backend.core.worker_pool.extract_preview_image", return_value=preview
        ), mock.patch("backend.core.worker_pool.get_file_hash", return_value="h1"), mock.patch(
            "backend.core.worker_pool.get_cached_metadata", return_value=None
        ):
            pool._process_file(
                src,
                tmp,
                FakeAI(),
                {"target_kw": 49, "style_preset": "Standard", "extra_prompt": "", "delay": 5},
                mock.Mock(),
            )
        self.assertLess(time.monotonic() - started, 3)


class AiSystemNameFlowTest(unittest.TestCase):
    def test_model_from_options_flows_to_embed_metadata(self):
        captured = {}

        def fake_embed(path, title, desc, kws, *a, **kw):
            captured.update(kw)
            return True

        class FakeAI:
            def generate_metadata(self, *args, **kwargs):
                return {
                    "title": "Red Ball",
                    "description": "A red ball.",
                    "keywords": ["ball"],
                }

        pool = FileWorkerPool()
        pool.processor.embed_metadata = mock.Mock(side_effect=fake_embed)

        tmp = tempfile.mkdtemp()
        preview = os.path.join(tmp, "preview.jpg")
        open(preview, "w").close()
        src = os.path.join(tmp, "x.eps")
        open(src, "w").close()

        with mock.patch(
            "backend.core.worker_pool.extract_preview_image", return_value=preview
        ), mock.patch("backend.core.worker_pool.get_file_hash", return_value="h1"), mock.patch(
            "backend.core.worker_pool.get_cached_metadata", return_value=None
        ):
            pool._process_file(
                src,
                tmp,
                FakeAI(),
                {
                    "target_kw": 49,
                    "style_preset": "Standard",
                    "extra_prompt": "",
                    "model": "gemini-2.5-flash",
                },
                mock.Mock(),
            )
        self.assertEqual(captured.get("ai_system_name"), "gemini-2.5-flash")

    def test_missing_model_defaults_to_gemini(self):
        captured = {}

        def fake_embed(path, title, desc, kws, *a, **kw):
            captured.update(kw)
            return True

        class FakeAI:
            def generate_metadata(self, *args, **kwargs):
                return {"title": "T", "description": "D.", "keywords": ["k"]}

        pool = FileWorkerPool()
        pool.processor.embed_metadata = mock.Mock(side_effect=fake_embed)

        tmp = tempfile.mkdtemp()
        preview = os.path.join(tmp, "preview.jpg")
        open(preview, "w").close()
        src = os.path.join(tmp, "x.eps")
        open(src, "w").close()

        with mock.patch(
            "backend.core.worker_pool.extract_preview_image", return_value=preview
        ), mock.patch("backend.core.worker_pool.get_file_hash", return_value="h1"), mock.patch(
            "backend.core.worker_pool.get_cached_metadata", return_value=None
        ):
            pool._process_file(src, tmp, FakeAI(), {"style_preset": "Standard"}, mock.Mock())
        self.assertEqual(captured.get("ai_system_name"), "Gemini")


if __name__ == "__main__":
    unittest.main()