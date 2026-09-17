import unittest
import os
import tempfile
from PIL import Image
from backend.core.clustering import (
    compute_dhash,
    hamming_distance,
    normalize_asset_name,
    adapt_metadata_for_variant,
    ClusterCoordinator
)

class TestClustering(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.img1_path = os.path.join(self.tmp_dir.name, "img1.png")
        self.img2_path = os.path.join(self.tmp_dir.name, "img2.png")
        self.img3_path = os.path.join(self.tmp_dir.name, "img3.png")

        # Image 1 and 2 are almost identical (black squares)
        img1 = Image.new("RGB", (100, 100), color="black")
        img1.save(self.img1_path)

        img2 = Image.new("RGB", (100, 100), color=(1, 1, 1)) # Very slight difference
        img2.save(self.img2_path)

        # Image 3 is completely different (black/white pattern)
        img3 = Image.new("RGB", (100, 100), color="black")
        img3.paste(Image.new("RGB", (50, 100), color="white"), (0, 0))
        img3.save(self.img3_path)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_compute_dhash_and_hamming(self):
        hash1 = compute_dhash(self.img1_path)
        hash2 = compute_dhash(self.img2_path)
        hash3 = compute_dhash(self.img3_path)

        # 1 and 2 should have identical or very similar hash
        dist_1_2 = hamming_distance(hash1, hash2)
        self.assertTrue(dist_1_2 <= 2)

        # 1 and 3 should be different
        dist_1_3 = hamming_distance(hash1, hash3)
        self.assertTrue(dist_1_3 > 4)

    def test_normalize_asset_name(self):
        self.assertEqual(normalize_asset_name("Cat_Icon_01.png"), "cat_icon")
        self.assertEqual(normalize_asset_name("Dog-Silhouette.eps"), "dog")
        self.assertEqual(normalize_asset_name("tree_color_v2.ai"), "tree")
        self.assertEqual(normalize_asset_name("House_flat.jpg"), "house")

    def test_adapt_metadata_for_variant(self):
        leader_meta = {
            "title": "Cute Cat Silhouette Vector",
            "keywords": ["cat", "cute", "animal", "silhouette"]
        }
        
        # Test 1: Variant is "Outline"
        adapted = adapt_metadata_for_variant(leader_meta, "cat_silhouette", "cat_outline")
        self.assertEqual(adapted["title"], "Cute Cat Outline Vector")
        self.assertIn("outline", adapted["keywords"])
        
        # Test 2: Variant has style not in leader, and leader has no specific style
        leader_meta2 = {
            "title": "Dog Vector Image",
            "keywords": ["dog", "vector", "pet"]
        }
        adapted2 = adapt_metadata_for_variant(leader_meta2, "dog_1", "dog_color")
        self.assertEqual(adapted2["title"], "Dog Vector Image Color")
        self.assertIn("color", adapted2["keywords"])

    def test_cluster_coordinator(self):
        coord = ClusterCoordinator(threshold=4)
        
        # Register img1
        is_leader, event, lname = coord.register_asset("path/to/img1.png", self.img1_path, "cat_icon_black.png")
        self.assertTrue(is_leader)
        self.assertIsNotNone(event)
        self.assertIsNone(lname)

        # Register img2 (similar perceptual hash)
        is_leader2, event2, lname2 = coord.register_asset("path/to/img2.png", self.img2_path, "cat_icon_outline.png")
        self.assertFalse(is_leader2)
        self.assertEqual(event, event2) # Waits on the same event
        self.assertEqual(lname2, "cat_icon_black.png")

        # Leader sets metadata
        meta = {"title": "Cat", "keywords": ["cat"]}
        coord.set_leader_metadata("path/to/img1.png", meta)

        # Variant gets metadata
        res, out_lname = coord.get_leader_metadata("path/to/img2.png", timeout=1.0)
        self.assertIsNotNone(res)
        self.assertEqual(res["title"], "Cat")

        # Disable clustering
        coord2 = ClusterCoordinator(enabled=False)
        il, ev, ln = coord2.register_asset("path/to/img1.png", self.img1_path, "cat_icon_black.png")
        self.assertTrue(il)
        self.assertIsNone(ev)

if __name__ == '__main__':
    unittest.main()
