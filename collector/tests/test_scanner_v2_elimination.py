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
        brand="", category_hint="", card_text="", source_category=""):
    old={"identity_status":"needs_review","identity_reasons":["missing_brand","strain_not_in_master"],
         "brand":"","strain":title,"package_g":None,"category":""}
    raw={"raw_title":title,"product_url":url,"source_url":url,
         "source_brand_text":brand,"source_category_text":source_category,
         "source_metadata":{"category_hint_unverified":category_hint,"card_text":card_text}}
    return rerank(old,raw,MASTER,BRANDS)


class EliminationPassTests(unittest.TestCase):
    def test_explicit_category_field_resolves_format(self):
        row = run("Grasslandz Guava 1g", url="", source_category="Vapes")
        self.assertEqual(row["category"], "Vape")
        self.assertEqual(row["identity_status"], "ready")
        self.assertEqual(row["resolution_evidence"]["category_basis"], "source_category_field")

    def test_explicit_category_field_overrides_conflicting_title(self):
        row = run("Grasslandz Guava Flower 1g", source_category="Pre-Rolls")
        self.assertEqual(row["category"], "Preroll")
        self.assertEqual(row["identity_status"], "ready")
        self.assertEqual(row["resolution_evidence"]["title_category"], "Flower")

    def test_unrecognized_category_does_not_promote_adapter_hint(self):
        row = run("Grasslandz Guava 1g", url="", source_category="Uncategorized",
                  category_hint="Vape")
        self.assertEqual(row["category"], "Vape")
        self.assertIn("category_only_adapter_hint", row["identity_reasons"])

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

    def test_card_weights_use_selected_or_priced_package(self):
        cases = (
            ("Guava Flower", "THC: 20.8%\n7g\nselected\n3.5g\n$85.00", 7, "selected_card_size"),
            ("Guava Flower", "THC: 22.1%\n\n$52.00\n\n/3.5g\nAdd to Bag", 3.5, "priced_card_size"),
            ("Guava Cartridge", "$65.00 /1g\nAdd to Bag", 1, "priced_card_size"),
            ("Guava Flower", "7g\n3.5g\n$85.00", None, "missing_weight"),
            ("Guava Flower", "7g\nselected\n$85.00 /3.5g", None, "conflicting_weights"),
            ("Guava Flower 7g", "$52.00 /3.5g", 7, "unique_weight"),
        )
        for title, card, weight, basis in cases:
            with self.subTest(title=title, card=card):
                self.assertEqual(package_size(title, {"card_text": card}, "Flower"),
                                 (weight, None, basis))

    def test_count_inferred_from_total_and_labeled_preroll_weight(self):
        for title in (
            "^Lifted North Prerolls - Blueberry Muffin, 2.5 grams (.5g each",
            "^Lifted North Prerolls - Pineapple Muffin, 2.5 grams (.5g each)",
        ):
            with self.subTest(title=title):
                self.assertEqual(package_size(title, {}, "Preroll"),
                                 (2.5, 5, "pack_count_from_total_and_unit_weight"))
        row = run("Grasslandz Guava Prerolls 2.5g (.5g each)", source_category="Pre-Rolls")
        self.assertEqual((row["package_g"], row["pack_count"], row["identity_status"]),
                         (2.5, 5, "ready"))

    def test_count_inference_preserves_weight_conflicts(self):
        for title in (
            "Prerolls 2.5g (.6g each)",
            "Prerolls 2.5g (.5g)",
            "Prerolls 2.5g (.5g each) 4ct",
            "Prerolls 2.5g selected .5g each",
            "Prerolls 2.5g each (.5g each)",
        ):
            with self.subTest(title=title):
                package_g, _, reason = package_size(title, {}, "Preroll")
                self.assertIsNone(package_g)
                self.assertEqual(reason, "conflicting_weights")

    def test_verified_product_line_is_form_specific(self):
        brands = [{"name": "Dogwalkers"}, {"name": "Verist Fields"}]
        old = {"identity_status": "needs_review"}
        for title, producer in (("Big Dog Guava | .75 Gram Preroll", "Dogwalkers"),
                                ("Sappy Pappy Guava | Cured Resin 1g", "Verist Fields")):
            row = rerank(old, {"raw_title": title}, MASTER, brands)
            self.assertEqual(row["brand"], producer)
        row = rerank(old, {"raw_title": "Big Dog Guava Flower 3.5g"}, MASTER, brands)
        self.assertFalse(row.get("brand"))

    def test_good_green_group_aliases_preserve_dogwalkers_product_line(self):
        brands = [{"name": "Good Green",
                   "aliases": ["Good Greens", "Dogwalkers", "Dogwalker", "Dog Walker", "Dog Walkers"]}]
        for source in ("Good Green", "Good Greens", "Dogwalkers", "Dogwalker", "Dog Walker", "Dog Walkers"):
            with self.subTest(source=source):
                row = rerank({}, {"raw_title": "Good Green Guava Flower 3.5g",
                                  "source_brand_text": source}, MASTER, brands)
                self.assertEqual(row["brand"], "Good Green")
                self.assertEqual(row["identity_status"], "ready")
        row = rerank({}, {"raw_title": "Big Dog Guava .75g Preroll"}, MASTER, brands)
        self.assertEqual((row["brand"], row["product_line"]), ("Good Green", "Big Dog"))
        row = rerank({}, {"raw_title": "Fog Dog Dogwalker .75g Preroll",
                          "source_brand_text": "Watchtower"}, MASTER, brands)
        self.assertIn("missing_or_conflicting_approved_brand", row["identity_reasons"])

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
