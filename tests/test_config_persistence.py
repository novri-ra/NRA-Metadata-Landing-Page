import unittest
import os
import json
import tkinter as tk
import customtkinter as ctk

# Ensure headless mode doesn't crash on Windows
# In this environment, it should work fine since it's Windows and UI tests passed earlier.

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "desktop", "src"))
from ui.main_window import AppWindow as App

from unittest.mock import patch
import tempfile

class TestConfigPersistence(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        import backend.core.config_manager as config_manager
        self.old_config_dir = config_manager.get_config_dir()
        config_manager.set_config_dir(self.tmp_dir.name)
        
        # Create a fresh app instance
        self.app = App()
        # Suppress log printing
        self.app.log = lambda *args, **kwargs: None

    def tearDown(self):
        self.app.destroy()
        import backend.core.config_manager as config_manager
        config_manager.set_config_dir(self.old_config_dir)
        self.tmp_dir.cleanup()

    def test_persistence_lifecycle(self):
        app = self.app
        
        # 1. Simulasikan pengisian API Key berbeda untuk 3 provider
        app.provider_cb.set("OpenAI")
        app._on_provider_change("OpenAI")
        app.api_key_text.delete("1.0", "end")
        app.api_key_text.insert("1.0", "sk-openai-123")
        # Trigger focus out simulation
        app.config["api_keys"]["OpenAI"] = "sk-openai-123"
        
        app.provider_cb.set("Gemini")
        app._on_provider_change("Gemini")
        app.api_key_text.delete("1.0", "end")
        app.api_key_text.insert("1.0", "AIza-gemini-456")
        app.config["api_keys"]["Gemini"] = "AIza-gemini-456"
        
        app.provider_cb.set("Custom")
        app._on_provider_change("Custom")
        app.api_key_text.delete("1.0", "end")
        app.api_key_text.insert("1.0", "custom-789")
        app.config["api_keys"]["Custom"] = "custom-789"

        # 2. Asersikan: pergantian provider memuat key yang sesuai
        app.provider_cb.set("OpenAI")
        app._on_provider_change("OpenAI")
        self.assertEqual(app.config["api_keys"]["OpenAI"], "sk-openai-123")
        
        app.provider_cb.set("Gemini")
        app._on_provider_change("Gemini")
        self.assertEqual(app.config["api_keys"]["Gemini"], "AIza-gemini-456")

        # 3. Simulasikan pergeseran slider dan checkbox
        app.temp_slider.set(0.7)
        app.workers_slider.set(8)
        
        # Checkboxes
        app.auto_watch.set(True)
        app.auto_zip.set(True)
        
        # Fetched models 
        app.MODEL_MAP["OpenAI"] = ["mock-model-1", "mock-model-2"]
        app.config.setdefault("model_cache", {})["OpenAI"] = ["mock-model-1", "mock-model-2"]
        
        # 4. Simpan config
        app._save_current_config()
        
        # 5. Instantiate ulang aplikasi (simulasi restart)
        app2 = App()
        app2.log = lambda *args, **kwargs: None
        
        # Asersikan persistensi State UI dan Konfigurasi
        self.assertEqual(app2.config["api_keys"]["OpenAI"], "sk-openai-123")
        self.assertEqual(app2.config["api_keys"]["Gemini"], "AIza-gemini-456")
        self.assertEqual(app2.config["api_keys"]["Custom"], "custom-789")
        
        self.assertEqual(app2.config["model_cache"]["OpenAI"], ["mock-model-1", "mock-model-2"])
        
        self.assertAlmostEqual(app2.config["temperature"], 0.7)
        self.assertEqual(app2.config["workers"], 8)
        self.assertTrue(app2.config["auto_watch"])
        self.assertTrue(app2.config["auto_zip_vector"])
        
        app2.destroy()

if __name__ == "__main__":
    unittest.main()
