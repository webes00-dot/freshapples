"""Cross-platform identity contract: HTML, JSON-LD, rendered and API cards."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from unified_scan_rules import normalize_observation, infer_category, extract_weight, bounded_prefix
from scanner_v2_elimination import package_size

MASTER={"canonical_strains":["Barnyard High Test","Fruit Junky","A-Team","Blue Dream",
 "Flower Power","Gak Nana","Mixed Strain","Skywalker OG","Animal Face"],
 "approved_aliases":{"Sky Walker OG":"Skywalker OG"}}
BRANDS=[{"name":"Campfire Cannabis","aliases":["Campfire"]},
 {"name":"Feelin' MN","aliases":["Feelin MN"]},
 {"name":"Off The Path"},{"name":"Float"}]

def parse(name, brand="", category="", url="https://shop.example.org/product/test", **other):
    return normalize_observation({"product_name":name,"brand":brand,
        "category":category,"url":url,**other},MASTER,BRANDS)

class UnifiedScanRulesTests(unittest.TestCase):
    def test_fractional_grams_in_titles_and_card_sizes(self):
        for weight in ("3/4g", "3 / 4 gram", "¾ g", "3⁄4 grams", ".75 gram"):
            with self.subTest(weight=weight):
                title = f"Blue Dream {weight} Pre-Roll"
                self.assertEqual(extract_weight(title)[0], 0.75)
                self.assertEqual(package_size(title, {}, "Preroll")[0], 0.75)
                self.assertEqual(package_size("Blue Dream", {"card_text": f"$9\n/{weight}"}, "Preroll")[0], 0.75)
        self.assertEqual(extract_weight("1/4 oz")[0], 7)
        self.assertEqual(package_size("3/4g x 2", {}, "Preroll")[:2], (1.5, 2))

    def test_barnyard_packaging_out_of_strain(self):
        x=parse("Campfire Cannabis Barnyard High Test | 1/8oz Flower","Campfire Cannabis","Flower")
        self.assertEqual((x["brand"],x["strain"],x["package_g"],x["category"]),
                         ("Campfire Cannabis","Barnyard High Test",3.5,"Flower"))
        self.assertEqual(x["identity_status"],"ready")

    def test_feelin_potency_and_multipack(self):
        x=parse("Feelin MN Fruit Junky | .5g Pre-rolls 2ct | 17.5%THC","Feelin' MN","Preroll")
        self.assertEqual((x["brand"],x["strain"],x["package_g"],x.get("pack_count")),
                         ("Feelin' MN","Fruit Junky",1.0,2))
        self.assertEqual(x["identity_status"],"ready")

    def test_vape_category_from_filtered_official_url(self):
        x=parse("Off The Path Gak Nana .5g","Off The Path",
            url="https://offthepathcannabis.com/shop/?dtche%5Bcategory%5D=vaporizers")
        self.assertEqual(x["category"],"Vape")
        self.assertEqual(x["strain"],"Gak Nana")
        self.assertEqual(x["package_g"],0.5)

    def test_adapter_guess_cannot_override_actual_vape_menu_context(self):
        x=parse("Off The Path Gak Nana .5g Live Resin","Off The Path",
                adapter_category_hint="concentrates",
                source_menu_url="https://offthepathcannabis.com/shop/?dtche%5Bcategory%5D=vaporizers")
        self.assertEqual(x["category"],"Vape")
        self.assertEqual(x["strain"],"Gak Nana")
        self.assertEqual(x["identity_status"],"ready")

    def test_510_cartridge_beats_live_resin_concentrate(self):
        self.assertEqual(infer_category("Skywalker OG 1g Live Resin 510 Cartridge"),"Vape")
        self.assertEqual(infer_category("Skywalker OG 1g Live Resin Concentrate"),"Concentrates")

    def test_no_speculative_match_when_strain_unknown(self):
        x=parse("Off The Path Unidentified Cultivar 1g Vape","Off The Path","Vape")
        self.assertEqual(x["identity_status"],"needs_review")
        self.assertIn("strain_not_in_master",x["identity_reasons"])

    def test_ambiguous_weight_held_for_review(self):
        x=parse("Blue Dream 1g / 3.5g Flower","Campfire Cannabis","Flower")
        self.assertIsNone(x["package_g"])
        self.assertIn("conflicting_weights",x["identity_reasons"])

    def test_verified_strain_a_team_preserved(self):
        x=parse("Campfire Cannabis A-Team 3.5g Flower","Campfire Cannabis","Flower")
        self.assertEqual(x["strain"],"A-Team")

    def test_cultivar_flower_power_not_stripped(self):
        x=parse("Campfire Cannabis Flower Power 3.5g Flower","Campfire Cannabis","Flower")
        self.assertEqual(x["strain"],"Flower Power")


    def test_brand_field_strips_known_cultivar_and_package(self):
        x=parse("Campfire Cannabis Blue Dream 3.5g Flower",
                "Campfire Cannabis Blue Dream 3.5g", "Flower")
        self.assertEqual(x["brand"],"Campfire Cannabis")
        self.assertEqual(x["strain"],"Blue Dream")

    def test_unknown_brand_is_explicit_review_case(self):
        x=parse("New Producer Blue Dream 3.5g Flower","New Producer","Flower")
        self.assertEqual(x["identity_status"],"needs_review")
        self.assertIn("brand_not_in_master",x["identity_reasons"])

    def test_unsupported_brand_not_derived_from_middle_of_strain(self):
        x=parse("Animal Face 3.5g Flower","","Flower")
        self.assertFalse(x["brand"])
        self.assertIn("missing_brand",x["identity_reasons"])

    def test_url_strain_needs_title_confirmation(self):
        x=parse("Off The Path Blue Dream 1g Vape","Off The Path","Vape",
             url="https://shop.example.org/product/skywalker-og-1g")
        self.assertEqual(x["strain"],"Blue Dream")

    def test_direct_product_url_can_recover_missing_cultivar_weight_and_brand(self):
        x=parse("3.5g Flower", category="Flower",
                url="https://shop.example.org/product/campfire-cannabis-blue-dream-3.5g")
        self.assertEqual(x["brand"],"Campfire Cannabis")
        self.assertEqual(x["strain"],"Blue Dream")
        self.assertEqual(x["package_g"],3.5)
        self.assertEqual(x["identity_status"],"ready")

    def test_store_landing_page_never_supplies_product_identity(self):
        x=parse("3.5g Flower", category="Flower",
                url="https://offthepathcannabis.com/shop/?dtche%5Bcategory%5D=flower")
        self.assertIn("missing_brand",x["identity_reasons"])
        self.assertIn("missing_strain",x["identity_reasons"])

    def test_brand_prefix_token_boundary(self):
        self.assertIsNone(bounded_prefix("Floatation 3.5g","Float"))
        self.assertEqual(bounded_prefix("Feelin MN Fruit Junky","Feelin' MN"),"Fruit Junky")

if __name__ == "__main__":
    unittest.main()
