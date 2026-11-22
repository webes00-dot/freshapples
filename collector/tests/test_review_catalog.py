import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from review_catalog import compare

def offer(**kwargs):
    base = {"retailer":"MN THC Co","store_id":"LICENSE-LAKEVILLE",
            "product_name":"Zesty Parm - 3.5g - Flor",
            "strain":"Zesty Parm","brand":"Flor","category":"Flower","package_g":3.5,
            "price":40,"url":"https://shop.example.com/lakeville/products/zesty",
            "checked_at":"2026-11-18T01:00:00Z","stock_status":"not_verified","source_id":""}
    base.update(kwargs)
    return base

class CatalogReviewTests(unittest.TestCase):
    def review(self, published, candidates):
        return compare(published,candidates,{"checked_at":"2026-11-18T01:00:00Z"})
    def test_new_offer_is_proposal_not_publish(self):
        out=self.review([], [offer()])
        self.assertEqual(out["counts"]["addition_candidates"],1)
        self.assertFalse(out["publish_approved"])
        self.assertEqual(out["auto_published"],0)
    def test_store_locations_are_not_merged(self):
        out=self.review([], [offer(),offer(store_id="LICENSE-DUNDAS",url="https://shop.example.com/dundas/products/zesty")])
        self.assertEqual(out["counts"]["addition_candidates"],2)
    def test_same_product_price_change_is_reviewed(self):
        out=self.review([offer(price=40)], [offer(price=45)])
        self.assertEqual(out["counts"]["price_change_candidates"],1)
        self.assertEqual(out["counts"]["addition_candidates"],0)
    def test_brand_change_blocks_automatic_matching(self):
        out=self.review([offer(brand="Flor")],[offer(brand="Different")])
        self.assertEqual(out["counts"]["needs_review"],1)
    def test_store_license_allows_presentation_label_variation(self):
        old = offer(retailer="MN THC Co — Lakeville")
        current = offer(retailer="MN THC Co")
        out = self.review([old], [current])
        self.assertEqual(out["counts"]["unchanged_candidates"], 1)
        self.assertEqual(out["counts"]["needs_review"], 0)
    def test_existing_store_license_price_change(self):
        old = offer(retailer="MN THC Co — Lakeville", price=40)
        current = offer(retailer="MN THC Co", price=42)
        out = self.review([old], [current])
        self.assertEqual(out["counts"]["price_change_candidates"], 1)
        self.assertEqual(out["counts"]["needs_review"], 0)
    def test_duplicate_source_identity_requires_review(self):
        out=self.review([], [offer(price=40),offer(price=35)])
        self.assertEqual(out["counts"]["needs_review"],1)
    def test_no_deletion_on_empty_or_failed_scan(self):
        out=self.review([offer()], [])
        self.assertEqual(out["counts"]["missing_not_removed"],1)
        self.assertEqual(out["counts"]["addition_candidates"],0)
    def test_missing_weight_not_given_per_gram(self):
        out=self.review([], [offer(package_g=None)])
        self.assertIn("unverified_weight",out["needs_review"][0]["reasons"])
    def test_no_nonproduct_or_offsite_url(self):
        out=self.review([], [offer(url="https://shop.example.com/")])
        self.assertIn("not_direct_product_url",out["needs_review"][0]["reasons"])
    def test_fuzzy_fingerprint_never_merges(self):
        old=offer(store_id="",url="https://shop.example.com/",id="old")
        out=self.review([old],[offer()])
        self.assertEqual(out["counts"]["needs_review"],1)
        self.assertEqual(out["auto_published"],0)
if __name__=="__main__":
    unittest.main()
