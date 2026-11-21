"""Verify that live card capture hands every supported format to V2."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from scanner_v2_capture import capture_rendered
from scanner_v2_pilot import rendered_products


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


if __name__ == "__main__":
    unittest.main()
