import unittest
from pathlib import Path
import tempfile
import shutil
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import get_base_name, find_matching_index, MODELS_DIR


class TestVoiceChangerModelUtils(unittest.TestCase):
    def test_get_base_name(self):
        self.assertEqual(get_base_name("hoshino.pth"), "hoshino")
        self.assertEqual(get_base_name("models/trained_index/ayane.index"), "ayane")
        self.assertEqual(get_base_name("nested/path/model_v2.pth"), "model_v2")

    def test_find_matching_index_exact(self):
        index_files = ["nara.index", "other.index"]
        matched = find_matching_index("nara.pth", index_files)
        self.assertEqual(matched, "nara.index")

    def test_find_matching_index_contains(self):
        index_files = ["character_v1_added.index"]
        matched = find_matching_index("character_v1.pth", index_files)
        self.assertEqual(matched, "character_v1_added.index")

    def test_find_matching_index_none(self):
        index_files = ["foo.index", "bar.index"]
        matched = find_matching_index("baz.pth", index_files)
        self.assertIsNone(matched)

    def test_path_traversal_detection(self):
        base_dir = MODELS_DIR.resolve()
        safe_path = (MODELS_DIR / "sample.pth").resolve()
        malicious_path = (MODELS_DIR / "../../../evil.pth").resolve()

        self.assertTrue(safe_path.is_relative_to(base_dir))
        self.assertFalse(malicious_path.is_relative_to(base_dir))


if __name__ == '__main__':
    unittest.main()
