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
            options = {"target_kw": 49, "style_preset": "Standard",
                       "extra_prompt": "", "custom_kw": "", "custom_kw_pos": "Start (Priority)"}
            pool._process_file(os.path.join(tmp, "x.eps"), tmp, FakeAI(pool), options, object())

        self.assertFalse(os.path.exists(preview))
        self.assertTrue(any("Stopped: batch cancelled" in str(l) for l in logs))
        self.assertEqual(pool.stats["error"], 0)


class CancelReentrancyTest(unittest.TestCase):
    """Restart after cancel must not be blocked by a stale is_running flag."""

    _OPTIONS = {  # noqa: RUF012
        "provider": "Gemini",
        "api_keys": {},
        "model": "gemini-2.5-flash",
        "temperature": 0.3,
        "target_kw": 49,
        "style_preset": "Standard",
        "extra_prompt": "",
        "workers": 1,
        "delay": 0,
    }

    def test_start_recovers_from_stale_flag(self):
        pool = FileWorkerPool()
        pool.is_running = True
        pool._batch_thread = None

        class FakeService:
            def __init__(self, *a, **k):
                pass

        with mock.patch(
            "backend.core.worker_pool.AIService", FakeService
        ), mock.patch(
            "backend.core.worker_pool.extract_preview_image", return_value=None
        ):
            started = pool.start(["a.jpg", "b.jpg"], tempfile.mkdtemp(), dict(self._OPTIONS))
        self.assertTrue(started, "start() must survive an orphaned is_running flag")
        deadline = time.time() + 10
        while pool.is_running and time.time() < deadline:
            time.sleep(0.02)
        self.assertFalse(pool.is_running)

    def test_cancel_does_not_block_when_thread_absent(self):
        pool = FileWorkerPool()
        t0 = time.monotonic()
        pool.cancel()
        self.assertLess(time.monotonic() - t0, 1.0)
        self.assertTrue(pool.cancel_flag)
        self.assertTrue(pool.pause_event.is_set())


if __name__ == "__main__":
    unittest.main()