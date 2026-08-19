import unittest
import os
import sys
import shutil
import base64
import json
from unittest.mock import patch

from packages.shared_utils.config import _dpapi_encrypt, _dpapi_decrypt
from packages.shared_utils.license_manager import get_machine_hwid, AuthClient
from packages.media_processor.embedder import MediaProcessor
from packages.media_processor.previews import extract_preview_image
from packages.shared_utils.csv_exporter import generate_microstock_csvs
from packages.shared_utils.csv_importer import import_csv_metadata
from packages.ai_engine.service import AIService

class TestNRAMetadataIntegration(unittest.TestCase):
    
    def setUp(self):
        self.test_dir = os.path.abspath('test_integration_env')
        os.makedirs(self.test_dir, exist_ok=True)
        
        self.dummy_jpg = os.path.join(self.test_dir, 'test_asset.jpg')
        with open(self.dummy_jpg, 'wb') as f:
            f.write(b'dummy_jpg_binary_content')
            
        self.dummy_csv = os.path.join(self.test_dir, 'metadata_output.csv')
        with open(self.dummy_csv, 'w', encoding='utf-8') as f:
            f.write('Filename,Title,Description,Keywords\n')
            f.write('test_asset.jpg,Test Title,Test Description,"key1, key2, key3"\n')
            
    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_dpapi_crypto(self):
        if sys.platform != 'win32':
            self.skipTest("DPAPI is Windows-only")
        
        plaintext = b'test_super_secret_payload'
        ciphertext = _dpapi_encrypt(plaintext)
        
        self.assertNotEqual(plaintext, ciphertext)
        self.assertGreater(len(ciphertext), 0)
        
        decrypted = _dpapi_decrypt(ciphertext)
        self.assertEqual(plaintext, decrypted)

    def test_hwid_generator(self):
        hwid = get_machine_hwid()
        self.assertEqual(len(hwid), 64)
        self.assertRegex(hwid, r'^[a-f0-9]{64}$')

    def test_csv_importer_exporter(self):
        # Test Import
        results = import_csv_metadata(self.dummy_csv)
        self.assertIn('test_asset.jpg', results)
        meta = results['test_asset.jpg']
        self.assertEqual(meta['Title'], 'Test Title')
        
        # Test Export
        generate_microstock_csvs(self.test_dir, {"Adobe Stock", "Shutterstock"})
        
        adobe_out = os.path.join(self.test_dir, 'adobe_stock_export.csv')
        shutterstock_out = os.path.join(self.test_dir, 'shutterstock_export.csv')
        
        self.assertTrue(os.path.exists(adobe_out))
        self.assertTrue(os.path.exists(shutterstock_out))

    @patch('packages.ai_engine.service.OpenAI')
    @patch('packages.ai_engine.service.load_config', return_value={'9router_base_url': 'http://localhost:8080/v1'})
    def test_9router_ai_factory(self, mock_load, MockOpenAI):
        service = AIService("9router", "test-key", "gpt-4o-mini")
        
        # Verify provider uses OpenAI client with correct base url
        MockOpenAI.assert_called_with(api_key="test-key", base_url="http://localhost:8080/v1")
        self.assertEqual(service.provider, "9router")

    def test_exiftool_path_guard(self):
        processor = MediaProcessor()
        try:
            processor.embed_metadata(self.dummy_jpg, "Title", "Desc", ["k1"], "C")
            guard_success = True
        except Exception as e:
            guard_success = False
            
        self.assertTrue(guard_success)

    def test_platform_compliance_validator(self):
        from packages.shared_utils.filter import remove_redundant_keywords, trim_keywords
        
        raw_kws = ["apple", "Apple", "apples", "run", "running", "extra"] * 10 
        
        cleaned = remove_redundant_keywords(raw_kws)
        cleaned = trim_keywords(cleaned)
        
        self.assertLessEqual(len(cleaned), 49)
        self.assertIn("apple", [k.lower() for k in cleaned])
        self.assertIn("run", [k.lower() for k in cleaned])

if __name__ == '__main__':
    unittest.main()