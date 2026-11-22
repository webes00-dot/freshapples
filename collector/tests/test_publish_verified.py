import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from publish_verified import promote

STORE = "DIS-L24-000396-01-AUR"
URL = "https://shop.mnthc.co/lakeville/products/campfire/flower/blue-35g-campfire/"
STAMP = "2026-11-18T05:00:00+00:00"
STORES = {STORE:{"license":STORE,"retailer":"MN THC Co",
                 "address":"16085 Buck Hill Road Lakeville MN 55019"}}

def candidate(**kwargs):
    c={"id":"blue1","store_id":STORE,"retailer":"MN THC Co",
       "product_name":"Blue - 3.5g - Campfire Cannabis",
       "strain":"Blue","brand":"Campfire Cannabis","category":"Flower",
       "package_g":3.5,"price":40.0,"url":URL,"source_id":"",
       "checked_at":STAMP,"source_method":"tymber_html_card",
       "stock_status":"not_verified"}
    c.update(kwargs)
    return c

def original(price=40, **kwargs):
    c=candidate(price=price)
    c["retailer"]="MN THC Co — Lakeville"
    c.update(kwargs)
    return c

def scan(reachable=True):
    return {"checked_at":STAMP,"statuses":[{"license":STORE,"connection":"reachable" if reachable else "failed"}]}

def details(status="confirmed"):
    return {"records":[{"id":"blue1","status":status}]}

def gate(pass_gate=True):
    return {"records":[{"id":"blue1","readiness":"machine_checks_passed_needs_human_approval" if pass_gate else "hold"}]}

class PublishVerifiedTests(unittest.TestCase):
    def test_add_strict_valid_offer(self):
        out,report=promote([], [candidate()],scan(),details(),gate(),STORES)
        self.assertEqual(len(out),1)
        self.assertEqual(report["events"][0]["action"],"added")
        self.assertEqual(out[0]["retailer"],"MN THC Co — Lakeville")
        self.assertEqual(out[0]["city"],"Lakeville")
    def test_update_only_price_and_preserve_identity(self):
        old=original()
        out,report=promote([old],[candidate(price=45)],scan(),details(),gate(),STORES)
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]["price"],45)
        self.assertEqual(out[0]["id"],old["id"])
        self.assertEqual(report["events"][0]["action"],"price_updated")
    def test_unchanged_does_not_rewrite(self):
        out,report=promote([original()],[candidate()],scan(),details(),gate(),STORES)
        self.assertEqual(report["events"],[])
        self.assertEqual(out[0]["price"],40)
    def test_conflicting_price_is_held(self):
        out,report=promote([original()],[candidate(price=45)],scan(),details("mismatch"),gate(False),STORES)
        self.assertEqual(out[0]["price"],40)
        self.assertEqual(len(report["holds"]),1)
    def test_large_price_spike_is_held(self):
        out,report=promote([original()],[candidate(price=100)],scan(),details(),gate(),STORES)
        self.assertEqual(out[0]["price"],40)
        self.assertEqual(report["events"],[])
    def test_incomplete_scan_cannot_remove(self):
        out,report=promote([original()],[],scan(False),{"records":[]},{"records":[]},STORES)
        self.assertEqual(len(out),1)
        self.assertEqual(report["removed"],0)
    def test_stale_scan_candidate_is_held(self):
        out,report=promote([],[candidate(checked_at="2020-01-01")],scan(),details(),gate(),STORES)
        self.assertEqual(len(out),0)
        self.assertEqual(report["holds"][0]["reasons"],["stale_candidate"])
    def test_unsupported_store_blocked(self):
        out,report=promote([],[candidate(store_id="OTHER")],scan(),details(),gate(),STORES)
        self.assertEqual(len(out),0)
        self.assertIn("unsupported_store_or_adapter",report["holds"][0]["reasons"])
    def test_different_brand_preserves_published(self):
        out,report=promote([original()],[candidate(brand="Another")],scan(),details(),gate(False),STORES)
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]["brand"],"Campfire Cannabis")
    def test_duplicate_source_products_blocked(self):
        out,report=promote([],[candidate(),candidate()],scan(),details(),gate(),STORES)
        self.assertEqual(len(out),0)
        self.assertEqual(len(report["holds"]),2)
    def test_false_weak_validation_blocks_new_product(self):
        out,report=promote([],[candidate(category="Vape")],scan(),details(),gate(),STORES)
        self.assertEqual(len(out),0)
        self.assertIn("failed_product_quality_check",report["holds"][0]["reasons"])

if __name__=="__main__":
    unittest.main()
