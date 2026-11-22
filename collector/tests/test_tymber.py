import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tymber_adapter import extract_cards, name_size_brand

BASE="https://shop.mnthc.co/lakeville/"

def card(href, title, price):
    return f'<div class="product-card"><a href="{href}">{title}</a><div class="price">{price}</div></div>'

class TymberAdapterTests(unittest.TestCase):
    def test_simple_products_and_store_paths(self):
        html=card("/lakeville/products/flr/flower/zesty-parm-123/","Zesty Parm - 3.5g - Flor","$40")
        offers=extract_cards(html, BASE)
        self.assertEqual(len(offers),1)
        self.assertEqual(offers[0]["strain"],"Zesty Parm")
        self.assertEqual(offers[0]["price"],40)
        self.assertEqual(offers[0]["package_g"],3.5)

    def test_sale_beats_previous_price(self):
        html=card("/lakeville/products/campfire/flower/mac-stomper-14g/","Mac Stomper - 14g - Campfire Cannabis","Previously $175 Sale Price $145")
        offers=extract_cards(html, BASE)
        self.assertEqual(len(offers),1)
        self.assertEqual(offers[0]["price"],145)
        self.assertEqual(offers[0]["price_selection"],"sale")

    def test_dedupe_repeated_recommendations(self):
        html=card("/lakeville/products/x/flower/a/","X - 4g - Campfire Cannabis","$55")*3
        self.assertEqual(len(extract_cards(html, BASE)),1)

    def test_no_cross_card_price_matching(self):
        html='<div class="grid">'+card("/lakeville/products/a/flower/a/","A - 4g - Campfire Cannabis","$55")+'<div><a href="/lakeville/products/b/flower/b/">B - 4g - Campfire Cannabis</a></div></div>'
        offers=extract_cards(html,BASE)
        self.assertEqual(len(offers),1)
        self.assertEqual(offers[0]["strain"],"A")

    def test_ignore_unweighted_and_offsite_links(self):
        html=card("/lakeville/products/a/flower/a/","Mystery flower","$25")+card("https://evil.test/products/x/","X - 4g - Campfire Cannabis","$50")
        self.assertEqual(extract_cards(html,BASE),[])

if __name__=="__main__":
    unittest.main()
