import os
import tempfile
import unittest

from backend.core.utils.key_manager import (
    build_openai_compatible_client,
    load_keys_from_file,
    parse_api_keys,
)


class ParseApiKeysTest(unittest.TestCase):
    def test_newline_separated(self):
        self.assertEqual(
            parse_api_keys("sk-gemini-key1\nsk-gemini-key2\nsk-gemini-key3"),
            ["sk-gemini-key1", "sk-gemini-key2", "sk-gemini-key3"],
        )

    def test_comma_semicolon_pipe(self):
        self.assertEqual(
            parse_api_keys("a1b2c3d4e5, sk-key-6f; sk-key-7g| sk-key-8h"),
            ["a1b2c3d4e5", "sk-key-6f", "sk-key-7g", "sk-key-8h"],
        )

    def test_json_python_list(self):
        self.assertEqual(
            parse_api_keys('["sk-key-1", "sk-key-2"]'), ["sk-key-1", "sk-key-2"]
        )
        self.assertEqual(
            parse_api_keys("'sk-key-1', 'sk-key-2'"), ["sk-key-1", "sk-key-2"]
        )

    def test_numbered_and_bulleted(self):
        self.assertEqual(
            parse_api_keys("1. sk-key-1\n- sk-key-2"), ["sk-key-1", "sk-key-2"]
        )

    def test_env_style(self):
        self.assertEqual(
            parse_api_keys('GEMINI_API_KEY=sk-key-123\nOPENAI_KEY="sk-key-456"'),
            ["sk-key-123", "sk-key-456"],
        )

    def test_dedup_case_insensitive_preserves_first(self):
        self.assertEqual(
            parse_api_keys("SK-key-1\nsk-key-1"), ["SK-key-1"]
        )

    def test_filters_short_tokens(self):
        self.assertEqual(parse_api_keys("ab\nvalidkey12345"), ["validkey12345"])

    def test_empty_and_whitespace(self):
        self.assertEqual(parse_api_keys(""), [])
        self.assertEqual(parse_api_keys("   \n  "), [])


class LoadKeysFromFileTest(unittest.TestCase):
    def test_env_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False, encoding="utf-8") as f:
            f.write("ANTHROPIC_KEY=sk-ant-1111\nGEMINI_KEY=gem-2222\n")
            path = f.name
        try:
            self.assertEqual(load_keys_from_file(path), ["sk-ant-1111", "gem-2222"])
        finally:
            os.unlink(path)

    def test_json_list_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write('["sk-json-1", "sk-json-2"]')
            path = f.name
        try:
            self.assertEqual(load_keys_from_file(path), ["sk-json-1", "sk-json-2"])
        finally:
            os.unlink(path)

    def test_csv_and_txt(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("sk-csv-111, sk-csv-222")
            path = f.name
        try:
            self.assertEqual(load_keys_from_file(path), ["sk-csv-111", "sk-csv-222"])
        finally:
            os.unlink(path)

    def test_missing_file_returns_empty(self):
        self.assertEqual(load_keys_from_file("/nonexistent/bogus.txt"), [])


class BuildClientTest(unittest.TestCase):
    def test_returns_openai_client_for_custom_endpoint(self):
        try:
            client = build_openai_compatible_client(
                "http://localhost:8080/v1", "sk-key-1", "my-model"
            )
        except ImportError:
            self.skipTest("openai package not installed")
        self.assertEqual(client.base_url, "http://localhost:8080/v1/")
        self.assertEqual(client.api_key, "sk-key-1")


if __name__ == "__main__":
    unittest.main()