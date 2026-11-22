import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from collector import extract_product, jsonld_products, consolidate, valid_public_url, supplemental_category_urls, flowhub_category_pages

class CollectorTests(unittest.TestCase):
    def test_flowhub_category_links_same_store_only(self):
        raw='''<a href="/rec/flower/nb/b4a">Flower</a>
        <a href="/rec/preroll/nb/c2d">Prerolls</a>
        <a href="/rec/vapes/nb/e5f">Vapes</a>
        <a href="/rec/flower/pdp/strain/v/abc">Product</a>
        <a href="https://other.dispensary.shop/rec/flower/nb/zzz">Other</a>
        <a href="/rec/flower/nb/b4a">Duplicate</a>'''
        urls=flowhub_category_pages(raw,"https://fortroadcannabis.dispensary.shop/rec/menu")
        self.assertEqual(len(urls),3)
        self.assertTrue(all("fortroadcannabis.dispensary.shop" in x for x in urls))

    def test_jsonld_product_price(self):
        html = '<script type="application/ld+json">{"@type":"Product","name":"Example Flower","sku":"A123","offers":{"price":"29.99","priceCurrency":"USD"}}</script>'
        products = list(jsonld_products(html))
        self.assertEqual(len(products), 1)
        result = extract_product(products[0], "Store", "https://example.org/shop", "2026-11-17")
        self.assertEqual(result["price"], 29.99)
        self.assertIsNone(result["package_g"])
        self.assertEqual(result["stock_status"], "not_verified")
    def test_no_price_is_not_a_listing(self):
        self.assertIsNone(extract_product({"name": "No price"}, "Store", "https://example.org", "today"))
    def test_retailer_offers_not_merged(self):
        a = {"retailer": "A", "source_id": "123", "url": "https://a.example/p", "price": 20, "product_name": "X"}
        b = {**a, "retailer": "B", "price": 30}
        products, conflicts = consolidate([a, b])
        self.assertEqual(len(products), 2)
        self.assertFalse(conflicts)
    def test_different_named_products_not_merged(self):
        a = {"retailer": "A", "source_id": "123", "url": "https://a.example/p", "price": 20, "product_name": "X"}
        b = {**a, "product_name": "Y"}
        self.assertEqual(len(consolidate([a, b])[0]), 2)
    def test_supplemental_category_urls_exclude_duplicate_primary(self):
        rows = [
            {"license":"STORE","category":"Flower","url":"https://5ddispensary.com/shop/flower"},
            {"license":"STORE","category":"Preroll","url":"https://5ddispensary.com/shop/pre-rolls"},
            {"license":"STORE","category":"Vape","url":"https://5ddispensary.com/shop/vapes"},
            {"license":"OTHER","category":"Flower","url":"https://example.org/shop/flower"},
        ]
        extras = supplemental_category_urls("STORE","https://5ddispensary.com/shop/flower",rows)
        self.assertEqual(extras,[
            ("Preroll","https://5ddispensary.com/shop/pre-rolls"),
            ("Vape","https://5ddispensary.com/shop/vapes"),
        ])
    def test_bad_urls_rejected(self):
        self.assertFalse(valid_public_url("http://127.0.0.1/private"))
        self.assertFalse(valid_public_url("http://localhost/"))
        self.assertFalse(valid_public_url("file:///etc/passwd"))
        self.assertTrue(valid_public_url("https://example.org/shop"))
if __name__ == "__main__":
    unittest.main()
