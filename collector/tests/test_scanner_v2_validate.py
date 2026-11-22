"""SKU-safe deduplication and validation fixtures for Scanner V2."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from scanner_v2_validate import validate

def offer(**updates):
    row = dict(
        observation_id="obs1", retailer_id="STORE-A", source_kind="official_menu_candidate",
        source_product_id="sku-123", variant_key="3.5g",
        source_url="https://store.example/shop",
        product_url="https://store.example/product/guava",
        raw_title="Campfire Cannabis Guava 3.5g",
        observed_at="2026-11-20T12:00:00+00:00", brand="Campfire Cannabis",
        strain="Guava", category="Flower", package_g=3.5,
        price=65, identity_status="ready", stock_status="not_verified")
    row.update(updates)
    return row

class V2ValidatorTests(unittest.TestCase):
    def test_duplicate_same_sku_one_survives(self):
        report=validate([offer(),offer(observation_id="obs2")])
        self.assertEqual(len(report["accepted"]),1)
        self.assertEqual(len(report["duplicates_suppressed"]),1)
        self.assertFalse(report["holds"])

    def test_distinct_pack_variant_not_merged(self):
        report=validate([offer(),offer(observation_id="obs2",variant_key="7g",package_g=7)])
        self.assertEqual(len(report["accepted"]),2)

    def test_distinct_retailer_not_merged(self):
        report=validate([offer(),offer(observation_id="obs2",retailer_id="STORE-B")])
        self.assertEqual(len(report["accepted"]),2)

    def test_conflicting_brand_for_same_sku_is_held(self):
        report=validate([offer(),offer(observation_id="obs2",brand="Stargaze")])
        self.assertEqual(len(report["accepted"]),0)
        self.assertEqual(report["holds"][0]["reasons"],["conflicting_sku_identity_or_price"])

    def test_confirmed_brand_wins_over_blank_brand_for_same_sku(self):
        report = validate([offer(), offer(observation_id="obs2", brand="")])
        self.assertEqual([row["observation_id"] for row in report["accepted"]], ["obs1"])
        self.assertEqual(report["duplicates_suppressed"], ["obs2"])
        self.assertFalse(report["holds"])

    def test_missing_strain_is_held_even_when_brand_is_optional(self):
        report = validate([offer(brand="", strain="")])
        self.assertEqual(report["holds"][0]["reasons"], ["missing_strain"])

    def test_price_drift_is_not_silently_overwritten(self):
        report=validate([offer(),offer(observation_id="obs2",price=70)])
        self.assertEqual(len(report["accepted"]),0)
        self.assertEqual(report["holds"][0]["reasons"],["conflicting_sku_identity_or_price"])

    def test_unresolved_identification_is_held(self):
        report=validate([offer(identity_status="needs_review",brand="")])
        self.assertEqual(len(report["accepted"]),0)
        self.assertIn("identity_pending_review",report["holds"][0]["reasons"])

    def test_invalid_strain_text_is_held(self):
        report=validate([offer(strain="Guava 3.5g")])
        self.assertIn("weight_in_strain_name",report["holds"][0]["reasons"])

    def test_nonverified_stock_preserved(self):
        report=validate([offer(stock_status="in_stock")])
        self.assertEqual(len(report["accepted"]),0)
        self.assertIn("unverified_inventory_assertion",report["holds"][0]["reasons"])

    def test_generic_menu_different_products_remain_distinct(self):
        a=offer(source_product_id="",variant_key="",product_url="https://store.example/menu")
        b=offer(source_product_id="",variant_key="",product_url="https://store.example/menu",
                observation_id="obs2",raw_title="Stargaze Dabbalicious 1g",
                brand="Stargaze",strain="Dabbalicious",category="Vape",package_g=1)
        self.assertEqual(len(validate([a,b])["accepted"]),2)

if __name__=="__main__":
    unittest.main()
