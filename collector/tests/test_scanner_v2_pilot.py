"""Verify that live card capture hands every supported format to V2."""
import csv
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from scanner_v2_capture import capture_rendered
from scanner_v2_pilot import rendered_products, summarize


class LivePilotTests(unittest.TestCase):
    def test_keeps_all_forms_and_preserves_card_evidence(self):
        menu = "https://shop.example/menu"
        titles = ["Guava Flower", "Guava Pre-roll", "Guava Vape", "Guava Live Rosin Concentrate"]
        cards = [
            {"text": f"{title} $24.50", "href": f"https://shop.example/product/{index}",
             "title": title, "brand": "Sample Producer", "productId": str(index)}
            for index, title in enumerate(titles)
        ]
        products = rendered_products(cards, menu)
        captures, holds = capture_rendered({"results": [{
            "id": "S-1", "retailer": "Sample Shop", "menu_url": menu,
            "scanned_at": "2026-11-21T18:00:00Z", "products": products,
        }]})
        self.assertFalse(holds)
        self.assertEqual([capture["raw_title"] for capture in captures], titles)
        self.assertTrue(all(capture["source_brand_text"] == "Sample Producer" for capture in captures))
        self.assertTrue(all(capture["price"] == 24.50 for capture in captures))

    def test_report_includes_individual_capture_and_validation_holds(self):
        menu = "https://shop.example/menu"
        results = [{
            "id": "S-1", "retailer": "Sample Shop", "menu_url": menu,
            "scanned_at": "2026-11-21T18:00:00Z", "statuses": ["Cards captured"],
            "products": [
                {"raw_product_title": "Guava Flower", "card_text": "Guava Flower $25",
                 "price_candidates": [25], "product_url": menu + "/1"},
                {"raw_product_title": "Bad price", "card_text": "Bad price $25 $30",
                 "price_candidates": [25, 30], "product_url": menu + "/2"},
            ],
        }]
        master = {"brands": [{"name": "Sample Producer"}],
                  "strain_master": {"canonical_strains": ["Guava"]}}
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "holds.csv"
            summarize(results, master, path)
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual([row["Stage"] for row in rows], ["Capture", "Validation"])
        self.assertEqual(rows[0]["Validation hold reasons"], "ambiguous_or_missing_price")
        self.assertEqual(rows[1]["Raw product title"], "Guava Flower")
        self.assertIn("missing_weight", rows[1]["Identity hold reasons"])


if __name__ == "__main__":
    unittest.main()
