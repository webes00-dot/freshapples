import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_details import compare_detail, verify

CANDIDATE = {"id":"x1","store_id":"LAKE","retailer":"MN THC Co",
             "url":"https://shop.example.com/lakeville/products/x","product_name":"Bumper OG - 3.5G - Flor",
             "price":40}

def product(name="Bumper OG - 3.5G - Flor", price="40", currency="USD"):
    return {"@type":"Product","name":name,
            "offers":{"price":price,"priceCurrency":currency}}

class DetailVerificationTests(unittest.TestCase):
    def test_confirm_exact_identity_and_usd_price(self):
        result = compare_detail(CANDIDATE,[product()])
        self.assertEqual(result["status"],"confirmed")
    def test_changed_price_is_mismatch(self):
        self.assertEqual(compare_detail(CANDIDATE,[product(price="45")])["status"],"mismatch")
    def test_missing_detail_data_is_inconclusive(self):
        self.assertEqual(compare_detail(CANDIDATE,[])["status"],"inconclusive")
    def test_duplicate_detail_data_is_inconclusive(self):
        self.assertEqual(compare_detail(CANDIDATE,[product(),product()])["status"],"inconclusive")
    def test_currency_must_be_usd(self):
        self.assertEqual(compare_detail(CANDIDATE,[product(currency="CAD")])["status"],"inconclusive")
    def test_different_product_name_not_approved(self):
        self.assertEqual(compare_detail(CANDIDATE,[product(name="Other")])["status"],"inconclusive")
    def test_flowhub_cards_do_not_make_unsupported_detail_requests(self):
        candidate={**CANDIDATE,"source_method":"flowhub_html_card_review_only"}
        def blocked(url):
            raise AssertionError("Flowhub independent verification should not be attempted")
        r=verify([candidate],fetcher=blocked)
        self.assertEqual(r["counts"]["unverified_card_only"],1)
        self.assertEqual(r["auto_published"],0)
    def test_fetch_failure_preserves_staging_only(self):
        x = verify([CANDIDATE],fetcher=lambda url:{"ok":False,"error":"http_error","status":403})
        self.assertEqual(x["counts"]["unreachable"],1)
        self.assertFalse(x["publication_allowed"])
        self.assertEqual(x["auto_published"],0)
    def test_redirect_to_other_product_is_rejected(self):
        x=verify([CANDIDATE],fetcher=lambda url:{"ok":True,"url":"https://shop.example.com/lakeville/products/other","html":"x"},parser=lambda html:[product()])
        self.assertEqual(x["counts"]["inconclusive"],1)
if __name__=="__main__":
    unittest.main()
