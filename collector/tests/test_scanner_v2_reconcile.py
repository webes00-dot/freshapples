"""Integration checks for Scanner V2 capture -> shared identity resolver."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from scanner_v2_capture import capture_rendered
from scanner_v2_reconcile import reconcile
from scanner_v2_validate import validate


MASTER = {"canonical_strains": ["Guava", "Mendo Breath", "Funk Bomb", "Flower Power"],
          "approved_aliases": {"Mendo Breath Auto": "Mendo Breath"}}
BRANDS = [{"name": "Campfire Cannabis", "aliases": ["Campfire"]},
          {"name": "Growing Green"}, {"name": "Avio"}]


def snap(card):
    return {"results": [{"id": "STORE-1", "retailer": "Sample",
                         "scanned_at": "2026-11-20T20:00:00+00:00",
                         "menu_url": "https://shop.example/rec/flower",
                         "products": [card]}]}


def card(title, brand="", price=45):
    return {"card_text": title + " $45.00", "price_candidates": [price],
            "product_url": "https://shop.example/product/flower-1",
            "source_menu_url": "https://shop.example/rec/flower",
            "brand_candidate": brand}


class ScannerV2ReconcileTests(unittest.TestCase):
    def test_explicit_producer_line_can_supply_brand_omitted_from_title(self):
        evidence = dict(card("Guava Flower 3.5g"), raw_product_title="Guava Flower 3.5g")
        evidence["card_text"] = "Sativa Dominant\nFlower by Campfire Cannabis\nGuava Flower 3.5g\n$45.00"
        captured, holds = capture_rendered(snap(evidence))
        self.assertFalse(holds)
        parsed, = reconcile(captured, MASTER, BRANDS)
        self.assertEqual(parsed["brand"], "Campfire Cannabis")
        self.assertEqual(parsed["resolution_evidence"]["brand"]["sources"], ["card_brand"])
        self.assertEqual(parsed["identity_status"], "ready")

    def test_guava_size_and_brand_do_not_pollute_strain(self):
        captured, holds = capture_rendered(snap(
            card("Campfire Cannabis Guava 3.5g Flower", "Campfire Cannabis")))
        self.assertFalse(holds)
        parsed = reconcile(captured, MASTER, BRANDS)
        self.assertEqual(parsed[0]["brand"], "Campfire Cannabis")
        self.assertEqual(parsed[0]["strain"], "Guava")
        self.assertEqual(parsed[0]["package_g"], 3.5)
        self.assertEqual(parsed[0]["identity_status"], "ready")
        self.assertEqual(parsed[0]["raw_title"], "Campfire Cannabis Guava 3.5g Flower")

    def test_unknown_strain_must_not_be_autoapproved(self):
        captured, _ = capture_rendered(snap(
            card("Growing Green Mystery Buds 3.5g Flower", "Growing Green")))
        parsed = reconcile(captured, MASTER, BRANDS)
        self.assertEqual(parsed[0]["identity_status"], "needs_review")
        self.assertIn("strain_not_in_master", parsed[0]["identity_reasons"])
        self.assertEqual(parsed[0]["stock_status"], "not_verified")

    def test_unconfirmed_brand_does_not_hold_a_valid_offer(self):
        for brand in ("", "Unknown Producer"):
            with self.subTest(brand=brand):
                captured, holds = capture_rendered(snap(card("Guava Flower 3.5g", brand)))
                self.assertFalse(holds)
                rows = reconcile(captured, MASTER, BRANDS, approved_brands=BRANDS)
                self.assertEqual(rows[0]["brand"], "")
                self.assertEqual(rows[0]["identity_status"], "ready")
                report = validate(rows)
                self.assertEqual(len(report["accepted"]), 1)
                self.assertFalse(report["holds"])


if __name__ == "__main__":
    unittest.main()
