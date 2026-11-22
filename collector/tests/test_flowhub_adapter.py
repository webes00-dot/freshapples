import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flowhub_adapter import extract_cards, split_brand_and_strain

BASE="https://fortroadcannabis.dispensary.shop/rec/menu"
class FlowhubAdapterTests(unittest.TestCase):
    def test_flower_card_extracts_sale_price(self):
        html='<a href="/rec/flower/pdp/first-class-funk/v/sku1"><img src="/x.png"><span>ON SALE Unbound First Class Funk - 1/8oz</span><span> Flower THC: 18.8% $50.00 $40.00 /3.5g Add to Bag</span></a>'
        result=extract_cards(html,BASE)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["price"],40)
        self.assertEqual(result[0]["category"],"Flower")
        self.assertEqual(result[0]["package_g"],3.5)
        self.assertEqual(result[0]["source_method"],"flowhub_html_card_review_only")
    def test_preroll_distinct(self):
        html='<a href="/rec/preroll/pdp/bumper/v/sku2">Northpark Bumper OG - 1g PreRolls 3pk Preroll THC: 14% $25.00 /3g Add to Bag</a>'
        rows=extract_cards(html,BASE)
        self.assertEqual(rows[0]["category"],"Preroll")
        self.assertEqual(rows[0]["package_g"],3)
    def test_real_flowhub_product_detail_url_and_category(self):
        html='<a href="/rec/view/pdp/p/v/da0a5718-85ca-47c1-98c1-42726b78fe0a"><span>Campfire Lit OG 3.5g Flower THC: 29.4% $44.52/4g Add to Bag</span></a>'
        offers=extract_cards(html,BASE)
        self.assertEqual(len(offers),1)
        self.assertEqual(offers[0]["category"],"Flower")
        self.assertEqual(offers[0]["price"],44.52)
        self.assertEqual(offers[0]["package_g"],4)
        self.assertEqual(offers[0]["product_name"],"Campfire Lit OG 3.5g")
    def test_real_flowhub_concentrate_path(self):
        html='<a href="/rec/view/pdp/p/v/sku2">Dope Cannabis Live Rosin 1g Concentrates THC: 70% $52.00/1g Add to Bag</a>'
        offers=extract_cards(html,BASE)
        self.assertEqual(len(offers),1)
        self.assertEqual(offers[0]["category"],"Concentrate")
    def test_mantine_inline_style_does_not_corrupt_product_card(self):
        html=('''<a style="text-decoration:unset" data-discover="true" href="/rec/flower/pdp/cap-junky/v/abc123">
          <style data-mantine-styles="inline">.random{min-height:12px}''' + 'very-long-css-'*80 +
          '''</style><div class="flowhub-product-card"><span>Campfire Cannabis Cap Junky - 3.5g</span>
          <span>Flower</span><span>Indica-dom</span><span>THC: 20%</span>
          <span>$45.00</span><span>/ 3.5g</span><button>Add to Bag</button></div></a>''')
        rows=extract_cards(html,BASE)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["price"],45)
        self.assertEqual(rows[0]["category"],"Flower")
        self.assertNotIn("very-long-css",rows[0]["product_name"])
    def test_cultivator_and_strain_are_split_without_guessing(self):
        self.assertEqual(split_brand_and_strain("Rythm Durban Z - 1/4oz"),("RYTHM","Durban Z"))
        self.assertEqual(split_brand_and_strain("Unbound Skywalker OG - 1g Vape Cart"),("Unbound","Skywalker OG"))
        self.assertEqual(split_brand_and_strain("Unknown Label Banana Push Pop"),("","Unknown Label Banana Push Pop"))
    def test_no_price_never_extracts(self):
        self.assertEqual(extract_cards('<a href="/rec/flower/pdp/x/v/a">Some Product Add to Bag</a>',BASE),[])
    def test_ambiguous_two_prices_held_without_sale_label(self):
        self.assertEqual(extract_cards('<a href="/rec/flower/pdp/x/v/a">Some Product $40.00 $55.00 /3.5g</a>',BASE),[])
    def test_offsite_product_dropped(self):
        html='<a href="https://evil.example/rec/flower/pdp/x/v/a">Some Product $50.00 /3.5g</a>'
        self.assertEqual(extract_cards(html,BASE),[])
    def test_no_repeated_product_tiles(self):
        html='<a href="/rec/flower/pdp/x/v/abc">Brand Product $40.00 /3.5g Add to Bag</a>'
        self.assertEqual(len(extract_cards(html+html,BASE)),1)
    def test_electronics_excluded(self):
        html='<a href="/rec/electronics/pdp/x/v/abc">Vape battery $25.00 /ea Add to Bag</a>'
        self.assertEqual(extract_cards(html,BASE),[])
    def test_unit_weight_unknown_without_label(self):
        html='<a href="/rec/flower/pdp/x/v/abc">Brand Product $40.00 Add to Bag</a>'
        self.assertIsNone(extract_cards(html,BASE)[0]["package_g"])

if __name__=="__main__":
    unittest.main()
