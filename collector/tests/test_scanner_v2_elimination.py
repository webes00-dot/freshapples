"""Second pass only: known aliases and bounded evidence, not SKU patches."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from scanner_v2_elimination import rerank, package_size

MASTER={"canonical_strains":["Guava","Guava Cake","Citrus Slushy","Bumper OG","Flower Power",
   "Fog Dog","Animal Face","Blue Dream","Brownie Scout","AK-47","Biscotti","Cap Junky"],
   "approved_aliases":{"Guava Auto":"Guava"}}
BRANDS=[{"name":"Campfire Cannabis","aliases":["Campfire"]},
 {"name":"Grasslandz"},{"name":"FLOR","aliases":["FLÖR"]},
 {"name":"RYTHM","aliases":["Rythm"]},{"name":"Stargaze"},{"name":"Minny Grown"},{"name":"Tasty Gems"},
 {"name":"Float Cannabis","aliases":["Float","Float Canna Co"]},
 {"name":"Redwood County Weed Management","aliases":["RCWM","RCWM Co"]}]


def run(title, url="https://shop.example/rec/flower",
        brand="", category_hint="", card_text=""):
    old={"identity_status":"needs_review","identity_reasons":["missing_brand","strain_not_in_master"],
         "brand":"","strain":title,"package_g":None,"category":""}
    raw={"raw_title":title,"product_url":url,"source_url":url,
         "source_brand_text":brand,
         "source_metadata":{"category_hint_unverified":category_hint,"card_text":card_text}}
    return rerank(old,raw,MASTER,BRANDS)


class EliminationPassTests(unittest.TestCase):
    def test_observed_float_alias_and_count_first_pack(self):
        row = run("Float 1x1g Pre Rolls Cap Junky Preroll THC: 27.2%")
        self.assertEqual((row["brand"], row["strain"], row["package_g"], row["pack_count"]),
                         ("Float Cannabis", "Cap Junky", 1, 1))
        self.assertEqual(row["identity_status"], "ready")

    def test_promotion_does_not_remove_observed_brand(self):
        row = run("Staff pick Float Canna Co Blue Dream Flower 3.5g")
        self.assertEqual(row["brand"], "Float Cannabis")
        self.assertEqual(row["identity_status"], "ready")

    def test_rcwm_brand_in_title_or_labelled_description(self):
        for row in (run("Flower Cap Junky | 3.5g | RCWM Co. 17.8% THC"),
                    run("Cap Junky Flower 3.5g", card_text="Cap Junky\nBrand: RCWM")):
            self.assertEqual(row["brand"], "Redwood County Weed Management")
            self.assertEqual(row["identity_status"], "ready")

    def test_conflicting_card_brand_stays_held(self):
        row = run("Float Cap Junky Flower 3.5g", card_text="Brand: RCWM")
        self.assertEqual(row["brand"], "")
        self.assertIn("missing_or_conflicting_approved_brand", row["identity_reasons"])

    def test_seltzer_and_float_flavor_are_not_flower_brands(self):
        row = run("Deal! Aura Seltzer 10mg - Lemon Basil - 12oz")
        self.assertEqual(row["identity_reasons"], ["non_target_category"])
        row = run("Foundry Nation Orange Dream Float | 10mg THC", url="https://shop.example/menu")
        self.assertEqual(row["brand"], "")

    def test_flower_fallback_requires_explicit_grams(self):
        url = "https://shop.example/menu"
        self.assertEqual(run("Grasslandz Guava 3.5 g", url=url)["category"], "Flower")
        self.assertFalse(run("Grasslandz Guava 3.5", url=url)["category"])
        self.assertFalse(run("Grasslandz Guava 7x0.5g", url=url)["category"])

    def test_product_slug_and_finished_form(self):
        row = run("Bundle Guava 1g distillate", url="https://shop.example/menu/dabs-12/grasslandz-guava-123")
        self.assertEqual((row["brand"], row["category"]), ("Grasslandz", "Concentrates"))
        self.assertEqual(run("Grasslandz Guava Distillate 510 1g")["category"], "Vape")

    def test_ready_equipment_is_excluded(self):
        old = {"identity_status": "ready", "category": "Flower", "brand": "Grasslandz"}
        row = rerank(old, {"raw_title": "Gear Flower Mill Grinder"}, MASTER, BRANDS)
        self.assertEqual(row["identity_reasons"], ["non_target_category"])

    def test_weight_options_require_selected_product_link(self):
        title = "Flower 7g selected 3.5g"
        self.assertEqual(package_size(title, {}, "Flower")[0], None)
        self.assertEqual(package_size(title, {}, "Flower", "https://shop.example/product/flower-7g")[0], 7)
        self.assertEqual(package_size("5-pack (0.5g ea) selected 1 G - SINGLE", {}, "Preroll",
                                      "https://shop.example/product/pre-roll-5-pack-05g-ea")[:2], (2.5, 5))

    def test_equivalent_fraction_and_disagreeing_units(self):
        self.assertEqual(package_size(".5G Disposable 1/2 gram", {}, "Vape")[0], 0.5)
        self.assertIsNone(package_size("Pre-rolls 0.33 g | 0.3 g | 3 ct", {}, "Preroll")[0])
        self.assertIsNone(package_size("Pre-Packed 7g 1/8 oz", {}, "Flower")[0])

    def test_verified_product_line_is_form_specific(self):
        brands = [{"name": "Dogwalkers"}, {"name": "Verist Fields"}]
        old = {"identity_status": "needs_review"}
        for title, producer in (("Big Dog Guava | .75 Gram Preroll", "Dogwalkers"),
                                ("Sappy Pappy Guava | Cured Resin 1g", "Verist Fields")):
            row = rerank(old, {"raw_title": title}, MASTER, brands)
            self.assertEqual(row["brand"], producer)
        row = rerank(old, {"raw_title": "Big Dog Guava Flower 3.5g"}, MASTER, brands)
        self.assertFalse(row.get("brand"))

    def test_brand_in_middle_and_cultivar_bounded(self):
        z=run("THC: 28.8% CAMPFIRE CANNABIS Guava - 3.5g - Campfire Cannabis 1/8 oz")
        self.assertEqual((z["brand"],z["strain"],z["package_g"],z["category"]),
                         ("Campfire Cannabis","Guava",3.5,"Flower"))
        self.assertEqual(z["identity_status"],"ready")

    def test_brand_trailing_and_known_strain(self):
        z=run("Rythm Brownie Scout | Prepacked | 3.5g | Rythm | Flower THC: 20.7%")
        self.assertEqual((z["brand"],z["strain"],z["category"]),
                         ("RYTHM","Brownie Scout","Flower"))
        self.assertEqual(z["identity_status"],"ready")

    def test_unit_count_and_total_do_not_conflict(self):
        z=run("THC: 14.23% GRASSLANDZ Citrus Slushy - Infused Pre-roll - 1g - 2ct - Grasslandz 2.0 grams",
              url="https://shop.example/rec/preroll")
        self.assertEqual(z["package_g"],2)
        self.assertEqual(z["pack_count"],2)
        self.assertEqual(z["identity_status"],"ready")

    def test_explicit_unit_times_count_is_total_package_weight(self):
        z=run("Minny Grown Bumper OG Pre Roll | 0.75g x 2 Preroll 50/50 THC: 18.7%",
              url="https://shop.example/rec/preroll")
        self.assertEqual(z["package_g"],1.5)
        self.assertEqual(z["pack_count"],2)
        self.assertEqual(z["identity_status"],"ready")

    def test_explicit_edible_title_is_not_flower_even_if_menu_context_is_flower(self):
        z=run("Campfire Cannabis Guava Gummies 3.5g Flower",
              url="https://shop.example/rec/flower")
        self.assertEqual(z["identity_reasons"],["non_target_category"])

    def test_ambiguous_unit_v_total_remains_hold(self):
        g,count,status=package_size("Guava 1g 2ct",{},"Preroll")
        self.assertIsNone(g)
        self.assertEqual(status,"ambiguous_unit_vs_total")

    def test_nested_cultivar_select_longest(self):
        z=run("Campfire Cannabis Guava Cake | 3.5g | Flower")
        self.assertEqual(z["strain"],"Guava Cake")
        self.assertEqual(z["identity_status"],"ready")

    def test_unknown_prefix_allows_approved_cultivar(self):
        z=run("Tasty Gems Chocolate Diamond Biscotti | 0.5g Vape",
              brand="Tasty Gems")
        self.assertEqual(z["identity_status"],"ready")
        self.assertEqual(z["strain"],"Biscotti")

    def test_multiple_distinct_strains_still_hold(self):
        z=run("Campfire Cannabis Guava Blue Dream 3.5g Flower")
        self.assertEqual(z["identity_status"],"needs_review")
        self.assertIn("missing_or_conflicting_approved_strain",z["identity_reasons"])

    def test_edible_url_is_not_promoted_as_strain(self):
        z=run("Campfire Cannabis Guava 3.5g",
              url="https://shop.example/products/edibles/guava-gummies")
        self.assertEqual(z["identity_reasons"],["non_target_category"])

    def test_existing_ready_is_unchanged(self):
        old={"identity_status":"ready","brand":"Stargaze","strain":"Guava",
             "category":"Vape","package_g":1,"identity_reasons":[]}
        raw={"raw_title":"bad scan","product_url":"https://shop.example/flower",
             "source_url":"https://shop.example/flower"}
        result=rerank(old,raw,MASTER,BRANDS)
        self.assertEqual(result["brand"],"Stargaze")
        self.assertEqual(result["identity_status"],"ready")

if __name__=="__main__":
    unittest.main()
