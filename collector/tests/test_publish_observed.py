import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from publish_observed import promote

STAMP="2026-11-18T05:00:00+00:00"
SKU="https://shop.mnthc.co/lakeville/products/campfire/flower/blue-35g/"
STORE="DIS-L24-000396-01-AUR"
BASE={"id":"sku-1","store_id":STORE,"retailer":"MN THC Co",
      "product_name":"Blue - 3.5g - Campfire Cannabis","strain":"Blue",
      "brand":"Campfire Cannabis","category":"Flower","package_g":3.5,
      "price":45,"url":SKU,"source_method":"tymber_html_card","checked_at":STAMP}
STORES={STORE:{"license":STORE,"retailer":"MN THC Co",
 "address":"16085 Buck Hill Road Lakeville MN 55019"}}
SCAN={"checked_at":STAMP,"statuses":[{"license":STORE,"connection":"reachable"}]}
class ObservedTests(unittest.TestCase):
    def test_publish_sourced_advertised_price(self):
        new,r=promote([],[BASE],SCAN,{"records":[{"id":"sku-1","status":"confirmed"}]},STORES)
        self.assertEqual(r["added"],1)
        self.assertEqual(new[0]["stock_status"],"not_verified")
        self.assertEqual(new[0]["product_family"],"Blue")
    def test_mismatch_held(self):
        new,r=promote([],[BASE],SCAN,{"records":[{"id":"sku-1","status":"mismatch"}]},STORES)
        self.assertEqual(r["added"],0)
        self.assertEqual(r["held"],1)
    def test_missing_detail_is_advertised_not_verified(self):
        new,r=promote([],[BASE],SCAN,{"records":[{"id":"sku-1","status":"inconclusive"}]},STORES)
        self.assertEqual(r["added"],1)
        self.assertEqual(new[0]["record_status"],"observed_advertised_menu")
    def test_no_duplicates_and_no_missing_removals(self):
        first,_=promote([],[BASE],SCAN,{"records":[]},STORES)
        second,report=promote(first,[BASE],SCAN,{"records":[]},STORES)
        self.assertEqual(len(second),1)
        self.assertEqual(report["added"],0)
        third,report=promote(second,[],SCAN,{"records":[]},STORES)
        self.assertEqual(len(third),1)
        self.assertEqual(report["removed"],0)
    def test_unknown_weight_kept_null(self):
        new,r=promote([],[{**BASE,"package_g":None}],SCAN,{"records":[]},STORES)
        self.assertIsNone(new[0]["package_g"])
    def test_failed_store_scan_blocks_fresh_offers(self):
        new,r=promote([],[BASE],{"checked_at":STAMP,"statuses":[]},{"records":[]},STORES)
        self.assertEqual(r["added"],0)
    def test_source_store_mismatch_blocks(self):
        new,r=promote([],[{**BASE,"retailer":"Other"}],SCAN,{"records":[]},STORES)
        self.assertEqual(r["added"],0)
    def test_flowhub_source_review_gate_relaxed_for_sourced_price(self):
        f={**BASE,"source_method":"flowhub_html_card_review_only",
            "url":"https://greenapplecannabis.dispensary.shop/rec/flower/pdp/blue/v/1"}
        sites={STORE:STORES[STORE]}
        new,r=promote([], [f],SCAN,{"records":[]},sites)
        self.assertEqual(r["added"],1)

if __name__=="__main__":
    unittest.main()
