import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from update_review_feed import merge

STAMP="2026-11-18T05:40:00+00:00"
C={"id":"a","store_id":"licensed","retailer":"Example Retailer",
   "url":"https://shop.mnthc.co/lakeville/products/example/flower/bourbon/",
   "product_name":"Bourbon Berry Zulu - 3.5g - Campfire Cannabis",
   "strain":"Bourbon Berry Zulu","brand":"Campfire Cannabis",
   "category":"Flower","package_g":3.5,"price":48,"checked_at":STAMP}
SCAN={"checked_at":STAMP}
GATE={"records":[{"id":"a","readiness":"hold","reasons":["brand_alias_review"],"detail_status":"confirmed"}]}

class FeedTests(unittest.TestCase):
    def test_hold_is_review_only(self):
        data,stats=merge({"candidates":[]},[C],SCAN,GATE,[])
        self.assertEqual(stats["added"],1)
        self.assertEqual(data["candidates"][0]["record_status"],"review_only_not_published")
        self.assertEqual(data["candidates"][0]["product_family"],"Bourbon Berry Zulu")
    def test_same_scan_does_not_duplicate(self):
        data,_=merge({"candidates":[]},[C],SCAN,GATE,[])
        newer,stats=merge(data,[C],SCAN,GATE,[])
        self.assertEqual(stats["added"],0)
        self.assertEqual(newer["candidates"][0]["candidate_id"],data["candidates"][0]["candidate_id"])
    def test_preserve_old_on_scan_failure(self):
        old={"candidates":[{"candidate_id":"5d-001","retailer":"5D"}]}
        newer,stats=merge(old,[],SCAN,{"records":[]},[])
        self.assertEqual(len(newer["candidates"]),1)
        self.assertEqual(stats["removed"],0)
    def test_stale_candidate_is_ignored(self):
        newer,stats=merge({"candidates":[]},[{**C,"checked_at":"earlier"}],SCAN,GATE,[])
        self.assertEqual(stats["added"],0)
    def test_published_product_is_not_added_again(self):
        old={**C}
        newer,stats=merge({"candidates":[]},[C],SCAN,GATE,[old])
        self.assertEqual(stats["added"],0)
    def test_no_gate_result_no_review(self):
        newer,stats=merge({"candidates":[]},[C],SCAN,{"records":[]},[])
        self.assertEqual(stats["added"],0)
    def test_untrusted_url_ignored(self):
        bad={**C,"url":"http://some-site/products/thing"}
        newer,stats=merge({"candidates":[]},[bad],SCAN,GATE,[])
        self.assertEqual(stats["added"],0)

if __name__=="__main__":
    unittest.main()
