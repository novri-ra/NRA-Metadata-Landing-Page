import os
import tempfile
import time
import unittest
from unittest import mock

from backend.ai.provider_router import _interruptible_sleep
from backend.core.worker_pool import FileWorkerPool


class InterruptibleSleepTest(unittest.TestCase):
    def test_completes_when_not_cancelled(self):
        started = time.monotonic()
        self.assertTrue(_interruptible_sleep(0.1, step=0.05))
        self.assertGreaterEqual(time.monotonic() - started, 0.09)

    def test_aborts_early_when_cancelled(self):
        flag = {"cancel": False}

        def cancel_check():
            return flag["cancel"]

        started = time.monotonic()
        self.assertTrue(_interruptible_sleep(0.5, cancel_check, step=0.05))
        flag["cancel"] = True
        self.assertFalse(_interruptible_sleep(0.5, cancel_check, step=0.05))
        self.assertLess(time.monotonic() - started, 0.9)


class WorkerPoolCancelTest(unittest.TestCase):
    def test_cancel_sets_flag_and_clears_pause(self):
        pool = FileWorkerPool()
        pool.pause_event.clear()
        pool.cancel()
        self.assertTrue(pool.cancel_flag)
        self.assertTrue(pool.pause_event.is_set())

    def test_process_file_aborts_when_cancelled_during_generation(self):
        class FakeAI:
            def __init__(self, pool):
                self._pool = pool

            def generate_metadata(self, *args, cancel_check=None, **kwargs):
                self._pool.cancel_flag = True
                assert cancel_check is not None
                return {"fail_reason": "cancelled", "error": True}

        pool = FileWorkerPool()
        logs = []
        pool._emit = (
            lambda name, *a: logs.append((name,) + tuple(a)) if name == "log" else None
        )

        tmp = tempfile.mkdtemp()
        preview = os.path.join(tmp, "preview.jpg")
        open(preview, "w").close()

        with mock.patch(
            "backend.core.worker_pool.extract_preview_image", return_value=preview
        ):
            options = {"min_kw": 25, "max_kw": 49, "style_preset": "Standard",
                       "extra_prompt": "", "custom_kw": "", "custom_kw_pos": "Start (Priority)"}
            pool._process_file(os.path.join(tmp, "x.eps"), tmp, FakeAI(pool), options, object())

        self.assertFalse(os.path.exists(preview))
        self.assertTrue(any("Stopped: batch cancelled" in str(l) for l in logs))
        self.assertEqual(pool.stats["error"], 0)


if __name__ == "__main__":
    unittest.main()