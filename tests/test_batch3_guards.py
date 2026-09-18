import csv
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent

from backend.ai.provider_router import AIService
from backend.core.worker_pool import FileWorkerPool
from backend.services.folder_watcher import FolderWatcher
from packages.shared_utils.csv_exporter import generate_microstock_csvs
from packages.shared_utils.filter import PLATFORM_RULES, validate_compliance


def _sample_metadata(path, title="Title here", description="a", keywords="k1,k2,k3,k4,k5"):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Filename", "Title", "Description", "Keywords"])
        w.writerow(["a.eps", title, description, keywords])


class WatcherLifecycleTest(unittest.TestCase):
    """T6: Auto-Watch drives the watcher without the login modal."""

    def _make_watcher(self):
        tmp = tempfile.mkdtemp()
        w = FolderWatcher(
            get_directory=lambda: tmp,
            is_allowed=lambda f: f.endswith((".eps", ".jpg")),
            is_busy=lambda: False,
            on_new_files=lambda files: None,
        )
        return w

    def test_watcher_start_stop_restart(self):
        w = self._make_watcher()
        w.start()
        self.assertTrue(w.running)
        w.stop()
        self.assertFalse(w.running)
        w.start()
        self.assertTrue(w.running)
        w.stop()
        self.assertFalse(w.running)

    def test_watcher_lifecycle_not_wired_into_login_modal(self):
        main_src = (ROOT / "apps/desktop/src/ui/main_window.py").read_text(encoding="utf-8")
        login_src = (ROOT / "apps/desktop/src/ui/dialogs/login_modal.py").read_text(encoding="utf-8")
        sidebar_src = (ROOT / "apps/desktop/src/ui/widgets/sidebar_panel.py").read_text(encoding="utf-8")
        # Shortcuts + watcher live on AppWindow now.
        self.assertIn('self.bind("<Control-z>"', main_src)
        self.assertIn('self.bind("<Control-y>"', main_src)
        self.assertIn("_apply_auto_watch_startup", main_src)
        self.assertIn("_toggle_auto_watch", main_src)
        self.assertIn("_toggle_auto_watch", sidebar_src)
        # Login modal no longer starts the watcher or binds undo/redo.
        self.assertNotIn("_watcher_loop", login_src)
        self.assertNotIn("<Control-z>", login_src)
        self.assertNotIn("<Control-y>", login_src)


class ReplaceDialogScopeTest(unittest.TestCase):
    """T7: batch replace exports only the checked platforms."""

    def test_replace_dialog_forwards_selected_platforms(self):
        src = (ROOT / "apps/desktop/src/ui/dialogs/batch_replace_dialog.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("app._get_selected_csv_platforms()", src)

    def test_csv_exporter_writes_only_selected_platform(self):
        tmp = tempfile.mkdtemp()
        _sample_metadata(os.path.join(tmp, "metadata_output.csv"))
        generate_microstock_csvs(tmp, {"Adobe Stock"})
        files = os.listdir(tmp)
        self.assertIn("adobe_stock_export.csv", files)
        for name in ("shutterstock_export.csv", "freepik_export.csv",
                     "vecteezy_export.csv", "generic_export.csv"):
            self.assertNotIn(name, files)


class ShutterstockDescLimitTest(unittest.TestCase):
    """S6: Shutterstock description quota raised 200 -> 2000 chars."""

    KWS = ["one", "two", "three", "four", "five", "six", "seven"]

    def test_desc_max_chars_raised_to_2000(self):
        self.assertEqual(PLATFORM_RULES["Shutterstock"]["desc_max_chars"], 2000)

    def test_validate_accepts_desc_up_to_2000(self):
        desc = " ".join(["parrot"] * 285)
        self.assertLessEqual(len(desc), 2000)
        res = validate_compliance("A title with enough words here", desc, self.KWS, "Shutterstock")
        self.assertTrue(res["valid"], res["errors"])

    def test_validate_rejects_desc_over_2000(self):
        desc = " ".join(["parrot"] * 300)
        self.assertGreater(len(desc), 2000)
        res = validate_compliance("A title with enough words here", desc, self.KWS, "Shutterstock")
        self.assertFalse(res["valid"])
        self.assertTrue(any("Description exceeds 2000 chars" in e for e in res["errors"]))

    def test_csv_exporter_keeps_long_desc(self):
        tmp = tempfile.mkdtemp()
        long_desc = " ".join(["parrot"] * 285)
        _sample_metadata(os.path.join(tmp, "metadata_output.csv"), description=long_desc)
        generate_microstock_csvs(tmp, {"Shutterstock"})
        with open(os.path.join(tmp, "shutterstock_export.csv"), encoding="utf-8") as f:
            row = next(iter(csv.DictReader(f)))
        self.assertEqual(row["Description"], long_desc)


class WorkerPoolExceptionSafetyTest(unittest.TestCase):
    """S9: is_running always resets even when the batch raises."""

    def test_is_running_reset_when_batch_raises(self):
        pool = FileWorkerPool()
        pool._emit = lambda *a, **k: None

        def boom(*a, **k):
            raise RuntimeError("ai service exploded")

        with mock.patch("backend.core.worker_pool.AIService", boom):
            pool.start(
                ["x.jpg"],
                tempfile.mkdtemp(),
                {
                    "provider": "Gemini",
                    "api_keys": {},
                    "model": "gemini-2.5-flash",
                    "temperature": 0.3,
                    "workers": 1,
                },
            )
        deadline = time.time() + 5
        while pool.is_running and time.time() < deadline:
            time.sleep(0.05)
        self.assertFalse(pool.is_running)


class ProviderFailoverTest(unittest.TestCase):
    """S10: failover forwards the logger and avoids shared-state mutation."""

    def test_failover_forwards_log_callback_and_cancel_check(self):
        captured = {}

        def fake_generate(self, image_path, target_kw=49, style_preset="Standard",
                          extra_prompt="", log_callback=None, cancel_check=None, **kw):
            captured["log_callback"] = log_callback
            captured["cancel_check"] = cancel_check
            return {"title": "ok"}

        def logger(msg, level):
            captured["msg"] = msg

        svc = AIService("Gemini", "primary-key", failover_providers={"OpenAI": "alt-key"})
        with mock.patch.object(AIService, "generate_metadata", fake_generate):
            res = svc._failover_call(
                "OpenAI", "alt-key", "x.jpg", 49, "General Commercial", "", logger, lambda: False
            )
        self.assertIs(captured.get("log_callback"), logger)
        self.assertIsNotNone(captured.get("cancel_check"))
        self.assertEqual(svc.provider, "Gemini")
        self.assertEqual(res["title"], "ok")

    def test_failover_does_not_mutate_shared_provider_state(self):
        src = (ROOT / "backend/ai/provider_router.py").read_text(encoding="utf-8")
        self.assertNotIn("self.provider = alt_provider", src)
        self.assertNotIn("failover.bind_provider(alt_provider)", src)
        self.assertNotIn("failover.replace_keys(alt_key)", src)


if __name__ == "__main__":
    unittest.main()