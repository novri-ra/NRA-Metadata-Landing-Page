import unittest
from unittest.mock import patch, MagicMock

from backend.core.worker_pool import FileWorkerPool, AdaptiveCooldown

class TestWorkerPoolCancel(unittest.TestCase):
    @patch('backend.core.worker_pool.get_file_hash', return_value='fakehash')
    @patch('backend.core.worker_pool.get_cached_metadata', return_value=None)
    @patch('backend.core.worker_pool.set_cached_metadata')
    @patch('backend.core.worker_pool.extract_preview_image', return_value='fake_preview.jpg')
    @patch('backend.core.worker_pool.os.remove')
    @patch('backend.core.worker_pool.Image')
    @patch('backend.core.worker_pool.shutil.move')
    def test_cancel_caches_inflight_metadata(self, mock_move, mock_image, mock_remove, mock_extract, mock_set_cache, mock_get_cache, mock_hash):
        pool = FileWorkerPool()
        
        # Simulate AI generation that succeeds, but sets cancel_flag before returning to simulate racing
        def fake_generate(*args, **kwargs):
            pool.cancel_flag = True
            return {"title": "Test", "keywords": ["k1"], "fail_reason": None}
            
        mock_ai = MagicMock()
        mock_ai.generate_metadata.side_effect = fake_generate
        
        res = pool._process_file_inner("test.jpg", "out_dir", mock_ai, {"style_preset": "none"}, MagicMock(), "test.jpg", 49, False, {
            "city": "", "country": "", "country_code": "", "date_created": ""
        })
        
        self.assertEqual(res, "cancelled")
        mock_set_cache.assert_called_once()

    def test_start_waits_for_stale_thread(self):
        pool = FileWorkerPool()
        pool.is_running = True
        
        # A thread that is still running
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        pool._batch_thread = mock_thread
        
        # start should try to join it
        started = pool.start([], "in", {})
        
        self.assertFalse(started)
        mock_thread.join.assert_called_once_with(timeout=2.0)

    def test_adaptive_cooldown_respects_ui_delay(self):
        cooldown = AdaptiveCooldown(base_min=10.0, base_max=11.0)
        cooldown.update(True)  # multiplier becomes 2.0
        
        mock_log = MagicMock()
        mock_event = MagicMock()
        mock_event.wait.return_value = False
        
        with patch('backend.core.worker_pool.random.uniform', return_value=10.5):
            cooldown.wait(mock_log, mock_event)
            
        mock_event.wait.assert_called_once_with(timeout=21.0)
        
if __name__ == '__main__':
    unittest.main()
