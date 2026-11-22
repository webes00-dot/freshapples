import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from publication_gate import check, evaluate

def row(**kwargs):
    obj={"id":"one","retailer":"MN THC Co Lakeville","store_id":"lakeville",
         "url":"https://shop.example.com/lakeville/products/brand/flower/blue-35g",
         "product_name":"Blue - 3.5g - Campfire Cannabis",
         "strain":"Blue","brand":"Campfire Cannabis","category":"Flower",
         "package_g":3.5,"price":40,"source_method":"tymber_html_card",
         "stock_status":"not_verified"}
    obj.update(kwargs)
    return obj

def detail(status="confirmed"):
    return {"id":"one","status":status}

class PublicationGateTests(unittest.TestCase):
    def test_machine_checks_no_auto_publication(self):
        r=evaluate([row()],{"records":[detail()]},{"needs_review":[],"price_change_candidates":[]})
        self.assertEqual(r["machine_checks_passed"],1)
        self.assertFalse(r["publish_approved"])
        self.assertEqual(r["auto_published"],0)
    def test_detail_mismatch_holds(self):
        self.assertIn("detail_not_confirmed",check(row(),detail("mismatch")))
    def test_price_title_weight_mismatch_holds(self):
        self.assertIn("weight_not_explicitly_confirmed_in_title",check(row(package_g=4),detail()))
    def test_missing_category_url_holds(self):
        self.assertIn("category_not_supported_by_product_path",check(row(category="Vape"),detail()))
    def test_brand_alias_holds(self):
        self.assertIn("brand_alias_review",check(row(brand="Flor",product_name="Blue - 3.5g - Flor"),detail()))
    def test_unverified_extractor_holds(self):
        self.assertIn("unreviewed_extractor",check(row(source_method="jsonld"),detail()))
    def test_catalog_conflict_holds(self):
        review={"needs_review":[{"record":{"id":"one"}}],"price_change_candidates":[]}
        r=evaluate([row()],{"records":[detail()]},review)
        self.assertEqual(r["on_hold"],1)
        self.assertIn("catalog_conflict",r["records"][0]["reasons"])
    def test_price_change_can_pass_strict_machine_checks(self):
        review={"needs_review":[],"price_change_candidates":[{"candidate":{"id":"one"}}]}
        r=evaluate([row()],{"records":[detail()]},review)
        self.assertEqual(r["machine_checks_passed"],1)
        self.assertFalse(r["publish_approved"])
    def test_duplicate_holds(self):
        r=evaluate([row(),row()],{"records":[detail()]},{"needs_review":[],"price_change_candidates":[]})
        self.assertEqual(r["on_hold"],2)
if __name__=="__main__":
    unittest.main()
