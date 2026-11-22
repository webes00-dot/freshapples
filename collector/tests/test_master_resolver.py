import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from master_resolver import key, cleanup, title_candidates, resolve_master


class MasterResolverTests(unittest.TestCase):
    def setUp(self):
        self.canonical = {
            key(n): n for n in [
                "Cereal Milk", "Sunset Sherbet", "Strawberry Lemonade",
                "Cherry Lady Slipper", "Mimosa Ice", "Granddaddy Purple",
                "Cheetah Piss", "Turtle Taffy", "Gush Kush", "Fog Dog",
            ]
        }
        self.aliases = {"cereal milk blend": "Cereal Milk",
                        "sunset sherbert": "Sunset Sherbet",
                        "grandaddy purple": "Granddaddy Purple"}

    def resolve(self, proposed, raw=None, brand=""):
        return resolve_master(proposed=proposed, raw_title=raw or proposed,
                              brand=brand, canonical=self.canonical,
                              aliases=self.aliases)

    def test_exact_and_approved_aliases(self):
        self.assertEqual(self.resolve("Cereal Milk")["strain"], "Cereal Milk")
        self.assertEqual(self.resolve("Cereal Milk Blend")["strain"], "Cereal Milk")
        self.assertEqual(self.resolve("Sunset Sherbert")["strain"], "Sunset Sherbet")

    def test_reparse_brand_and_format_noise(self):
        cases = [
            ("Trailhead Cannabis Cherry Lady Slipper", "", "Cherry Lady Slipper"),
            ("Mr. Birch Mimosa Ice 3.5g", "", "Mimosa Ice"),
            ("Native Cuts Cheetah Piss", "", "Cheetah Piss"),
            ("Cannabis Turtle Taffy", "", "Turtle Taffy"),
            ("Verist Fields | Gush Kush | 3.5g", "", "Gush Kush"),
            ("FLÖR Fog Dog Flower", "FLÖR", "Fog Dog"),
        ]
        for title, brand, expected in cases:
            with self.subTest(title=title):
                self.assertEqual(self.resolve(title, brand=brand)["strain"], expected)

    def test_only_suggest_not_approve_unknown(self):
        result = self.resolve("Meduza")
        self.assertEqual(result["status"], "review")
        self.assertEqual(result["method"], "unresolved_after_reparse")

    def test_no_generic_product_approval(self):
        result = self.resolve("0 0 in cart")
        self.assertEqual(result["status"], "review")


if __name__ == "__main__":
    unittest.main()
