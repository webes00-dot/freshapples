import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from brand_aliases import canonical_brand

class BrandAliasTests(unittest.TestCase):
    def test_emerald_farms_collaborations(self):
        self.assertEqual(canonical_brand("Emerald Farms + HOG Cannabis"), "Emerald Farms")
        self.assertEqual(canonical_brand("Emerald Fire Farms + HOG Cannabis"), "Emerald Farms")
        self.assertEqual(canonical_brand("Emerald Fire Farms"), "Emerald Farms")
    def test_aliases(self):
        for value in ("Campfire", "Campfire Cannabis"):
            self.assertEqual(canonical_brand(value), "Campfire Cannabis")
        for value in ("Redwood", "Redwood County Weed Management"):
            self.assertEqual(canonical_brand(value), "Redwood County Weed Management")
        for value in ("Flor", "FLOR", "Flör"):
            self.assertEqual(canonical_brand(value), "FLÖR")
    def test_user_confirmed_aliases(self):
        self.assertEqual(canonical_brand("Lakeside Canna"), "Lakeside Cannabis")
        self.assertEqual(canonical_brand("Lakeside Cana"), "Lakeside Cannabis")
        self.assertEqual(canonical_brand("Lakeside Cannabis"), "Lakeside Cannabis")
        self.assertEqual(canonical_brand("Lake Leaf"), "Campfire Cannabis")
        self.assertEqual(canonical_brand("Campfire / Lake Leaf"), "Campfire Cannabis")
        self.assertEqual(canonical_brand("Emerald Fire Farms"), "Emerald Farms")
        self.assertEqual(canonical_brand("Emerald Farms"), "Emerald Farms")
        self.assertEqual(canonical_brand("Laketown"), "Laketown Farms")
        self.assertEqual(canonical_brand("Laketown Farms"), "Laketown Farms")
        self.assertEqual(canonical_brand("Oma"), "Laketown Farms")
        self.assertEqual(canonical_brand("Native care"), "Native Care")
        self.assertEqual(canonical_brand("Native Care"), "Native Care")
        self.assertEqual(canonical_brand("North Park"), "Northpark")
        self.assertEqual(canonical_brand("Northpark Cannabis Co"), "Northpark")
        self.assertEqual(canonical_brand("Northpark"), "Northpark")
        self.assertEqual(canonical_brand("sMIILE"), "SMIILE")
        self.assertEqual(canonical_brand("SMIILE"), "SMIILE")
        self.assertEqual(canonical_brand("Sappy Pappy"), "Verist Fields")
        self.assertEqual(canonical_brand("Verist Fields"), "Verist Fields")
    def test_other_brands_are_distinct(self):
        self.assertEqual(canonical_brand("Float Cannabis Co."), "Float Cannabis")
        self.assertEqual(canonical_brand("Unbound"), "Unbound")
        self.assertEqual(canonical_brand("Emerald Bay"), "Emerald Bay")

if __name__ == "__main__":
    unittest.main()
