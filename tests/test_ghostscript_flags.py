import unittest
from unittest.mock import patch, MagicMock
from backend.processors.ghostscript_preview import render_vector_preview

class GhostscriptFlagsTest(unittest.TestCase):
    @patch('backend.processors.ghostscript_preview.find_ghostscript_binary')
    @patch('backend.processors.ghostscript_preview.subprocess.run')
    @patch('backend.processors.ghostscript_preview.Path.exists')
    def test_gs_flags_eps_crop(self, mock_exists, mock_run, mock_find_gs):
        mock_find_gs.return_value = 'gswin64c.exe'
        mock_exists.return_value = True
        
        mock_run.return_value = MagicMock(returncode=1, stderr=b"Mock error") # force fail to just check args
        
        render_vector_preview('test_image.eps', 'out.jpg', None)
        
        args = mock_run.call_args_list[0][0][0]
        self.assertIn('-sDEVICE=jpeg', args)
        self.assertIn('-dEPSCrop', args)
        self.assertNotIn('-dEPSFitPage', args)

    @patch('backend.processors.ghostscript_preview.find_ghostscript_binary')
    @patch('backend.processors.ghostscript_preview.subprocess.run')
    @patch('backend.processors.ghostscript_preview.Path.exists')
    def test_gs_flags_ai_fit(self, mock_exists, mock_run, mock_find_gs):
        mock_find_gs.return_value = 'gswin64c.exe'
        mock_exists.return_value = True
        
        mock_run.return_value = MagicMock(returncode=1, stderr=b"Mock error") # force fail
        
        render_vector_preview('test_image.ai', 'out.jpg', None)
        
        args = mock_run.call_args_list[0][0][0]
        self.assertIn('-sDEVICE=jpeg', args)
        self.assertIn('-dEPSFitPage', args)
        self.assertNotIn('-dEPSCrop', args)

if __name__ == '__main__':
    unittest.main()
