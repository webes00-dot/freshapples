import sys
import unittest
from collections import Counter
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from build_catalog import infer_missing_brands, load_corrections, apply_correction, BLOCKED
from strain_rules import identify_product, match_strain, parse_structured_title

class CatalogIdentityTests(unittest.TestCase):
    def test_mr_birch_big_stick_torch_top_is_a_cultivar(self):
        for title in ("Mr. Birch Big Stick Torch Top",
                      "Mr Birch Big Stick Torch Top",
                      "ON SALE Mr. Birch Big Stick Torch Top Preroll"):
            with self.subTest(title=title):
                actual = identify_product(title)
                self.assertIsNotNone(actual)
                self.assertEqual(actual["strain"], "Torch Top")
                self.assertEqual(actual["brand"], "Verist Fields")
                self.assertEqual(actual["product_variant"], "Big Stick")


    def test_verist_sappy_pappy_is_product_line_not_strain(self):
        cases = {
            "Verist Fields Verist Fields | Cured Resin | Sappy Pappy | Dream Berry": "Dream Berry",
            "Sappy Pappy Dream Berry 1g Cured Resin": "Dream Berry",
            "Sappy Pappy Glacier Valley Sour 1g Cured Resin": "Glacier Valley Sour",
            "Sappy Pappy Sour Luxx 1g Cured Resin": "Sour Luxxe",
        }
        for title, cultivar in cases.items():
            with self.subTest(title=title):
                parsed=identify_product(title)
                self.assertIsNotNone(parsed)
                self.assertEqual(parsed["strain"],cultivar)
                self.assertEqual(parsed["brand"],"Verist Fields")
                self.assertEqual(parsed["product_variant"],"Sappy Pappy")
        self.assertIsNone(identify_product("Verist Sappy Pappy"))
        self.assertIsNone(identify_product("Sappy Pappy Unknown New Cultivar"))


    def test_verist_field_prefixes_are_brands_not_strains(self):
        cases = {
            "Verist Fields Mimosa Ice 3.5 Flower": ("Mimosa Ice", None),
            "Verist Fields Platinum Jesus": ("Platinum Jesus", None),
            "Verist Fields | Valley Frost |": ("Valley Frost", None),
            "Verist Fields | Little Stick | Double Sour Grape |": ("Double Sour Grape", "Little Stick"),
            "Verist Fields | Little Stick | Mimosa Ice |": ("Mimosa Ice", "Little Stick"),
            "Verist Fields | Little Stick | Valley Frost |": ("Valley Frost", "Little Stick"),
        }
        for raw, (strain, variant) in cases.items():
            with self.subTest(raw=raw):
                parsed = parse_structured_title(raw)
                self.assertIsNotNone(parsed)
                self.assertEqual(parsed["strain"], strain)
                self.assertEqual(parsed["brand"], "Verist Fields")
                self.assertEqual(parsed.get("product_variant"), variant)


    def test_aurora_strawneapple(self):
        self.assertEqual(identify_product("Aurora Cannabis LLC Strawneapple"), {"strain": "Strawneapple", "brand": "Aurora"})
        self.assertEqual(identify_product("Aurora Cannabis LLC Strawneapple | 3.5G"), {"strain": "Strawneapple", "brand": "Aurora"})

    def test_additional_exact_title_splits(self):
        samples = {
            "d'Ope Cannabis Anthos Blend |": ("Anthos Blend", "D'Ope"),
            "Minny Grown Minny Grown | Flower | FrankenPine": ("Franken Pine", "Minny Grown"),
            "Minny Grown Sour Lemons": ("Sour Lemons", "Minny Grown"),
            "Mischief Premium Atlas Froot by the Foot": ("Froot by the Foot", "Mischief Cannabis"),
            "NorthPark 510 Vape Cart-IX | Gelato #41": ("Gelato 41", "Northpark"),
            "NorthPark OG Kush Cart": ("OG Kush", "Northpark"),
            "R & D R & D Pharms | Black Maple | Pre-pack": ("Black Maple 22", "R & D Farms"),
            "Rewind Aloha Sugar": ("Aloha Sugar", "Rewind"),
            "Rewind Daily Grape": ("Daily Grape", "Rewind"),
            "Rewind Kanobi Sunset": ("Kanobi Sunset", "Rewind"),
            "Rewind Killer Cupcake": ("Killer Cupcake", "Rewind"),
            "Turtle Taffy - 2-Pack": ("Turtle Taffy", None),
            "Turtle Taffy - 8-Pack": ("Turtle Taffy", None),
            "Verist Fields Verist Fields | Cured Resin | Sappy Pappy | Dream Berry": ("Dream Berry", "Verist Fields"),
            "Verist Fields Verist Fields | Pre-Packaged | Double Sour Grapes": ("Double Sour Grape", "Verist Fields"),
            "Float Float | Pre-Packaged | Gorilla Zkittles": ("Gorilla Zkittlez", "Float Cannabis"),
            "Float Magic Marker": ("Magic Marker", "Float Cannabis"),
            "Shine Grand Daddy Purple": ("Granddaddy Purple", "&Shine"),
            "Trailhead Trailhead | Pre-Packaged | Gastronaunt": ("Gastronaut", "Trailhead Cannabis"),
        }
        for title, (strain, brand) in samples.items():
            with self.subTest(title=title):
                result = identify_product(title)
                self.assertIsNotNone(result)
                self.assertEqual(result["strain"], strain)
                self.assertEqual(result.get("brand"), brand)

    def test_owner_confirmed_merchandise_title_aliases(self):
        samples = {
            "Big Dog 3/4 Gram L'ORANGE Sativa": ("L'Orange", "Dogwalkers"),
            "3/4 Gram L'ORANGE Sativa Pre-Roll": ("L'Orange", None),
            "FLÖR Gummi-Bear Live Rosin | .5gm": ("Gummibears", "FLÖR"),
            "Highnorth Turtle Taffy Discovery Pack": ("Turtle Taffy", None),
            "Highnorth White Widow Discovery Pack": ("White Widow", None),
            "Little Stick by Verist Fields Double Sour Grape": ("Double Sour Grape", "Verist Fields"),
            "Little Stick by Verist Fields Platinum Jesus": ("Platinum Jesus", "Verist Fields"),
            "Mr Birch Big Stick Torch Top": ("Torch Top", "Verist Fields"),
            "Mr.Birch Little Stick - Swedish OG": ("Swedish OG", "Verist Fields"),
            "Popcorn- Space Boogie": ("Space Boogie", None),
            "Purple Cereal Milk": ("Purple Milk", None),
            "Mendo Breath Auto": ("Mendo Breath", None),
            "Pilot Light 2.0": ("Pilot Light", None),
            "Hyperion": ("Hyperion F1", None),
        }
        for raw, (strain, brand) in samples.items():
            with self.subTest(raw=raw):
                actual = identify_product(raw)
                self.assertIsNotNone(actual)
                self.assertEqual(actual["strain"], strain)
                self.assertEqual(actual.get("brand"), brand)

    def test_mnl_published_title_normalization(self):
        # Tested via server-side parser; catalog build also checks no MNL
        # brand prefix escapes into the generated strain headings.
        samples = {
            "Mnl Orange creamsicle .5": "Orange Creamsicle",
            "Mnl Watermelon.5": "Watermelon",
            "Mnl Nyc diesel 1/2 gram": "NYC Diesel",
            "MnLoon NYC Diesel": "NYC Diesel",
        }
        for raw, expected in samples.items():
            with self.subTest(raw=raw):
                parsed = identify_product(raw)
                self.assertIsNotNone(parsed)
                self.assertEqual(parsed["strain"], expected)
                self.assertEqual(parsed["brand"], "MN Loon")

    def test_owner_new_product_name_patterns(self):
        self.assertEqual(identify_product("Bud Doctor Scotch and Soda Flower 50/50"),
                         {"strain": "Scotch and Soda", "brand": "Bud Doctor"})
        self.assertEqual(identify_product("Lifted North Lifted North Pre-Rolls Blueberry Muffin Preroll"),
                         {"strain": "Blueberry Muffin", "brand": "Lifted North"})
        self.assertEqual(match_strain("Black Matter-", {})["strain"], "Black Matter")
        self.assertEqual(match_strain("Biscotti-", {})["strain"], "Biscotti")

    def test_owner_new_source_id_corrections(self):
        source_root=Path(__file__).resolve().parents[2] / "data"
        corrections=load_corrections()
        expectations={
            "auto-98e34540627d3b2449": ("Biscotti","Zips"),
            "auto-e5dcb2fca84243d013": ("Biscotti","Zips"),
            "auto-323ea31cd21b978ee3": ("Black Matter","Terps & Co"),
            "auto-e6abda441f8e6d1b83": ("Blueberry Muffin","Lifted North"),
            "auto-741ad870c337486c1d": ("Scotch and Soda","Bud Doctor"),
            "research-20261118-336": ("Mac Stomper","Campfire Cannabis"),
            "research-jc-20261118-017": ("Mandarin Cookies","Waabigwan Mashkiki"),
            "auto-98b6b25d82006d1876": ("Tanghulu","FLÖR"),
            "auto-6656d10ab76a7fc530": ("MAC Stomper","Campfire Cannabis"),
        }
        for id_,(strain,brand) in expectations.items():
            with self.subTest(id=id_):
                source="auto_menu_offers.json" if id_.startswith("auto-") else "researched_menu_offers.json"
                rows=json.loads((source_root / source).read_text())
                original=next(r for r in rows if r.get("id")==id_)
                amended=apply_correction(dict(original), corrections, Counter())
                self.assertEqual((amended["strain"],amended["brand"]),(strain,brand))

    def test_builder_aliases_match_public_reviewed_names(self):
        from strain_rules import normalize_brand
        strain_aliases = {
            "Cereal Milk Blend": "Cereal Milk",
            "Sunset Sherbert": "Sunset Sherbet",
            "Grandaddy Purple": "Granddaddy Purple",
            "Grand Daddy Purple": "Granddaddy Purple",
            "Granddaddy Purp": "Granddaddy Purple",
            "Cannabis Turtle Taffy": "Turtle Taffy",
            "Cannabis Fog Dog": "Fog Dog",
            "Trailhead Cherry Lady Slipper": "Cherry Lady Slipper",
            "Dizgo Medusa": "Medusa",
        }
        for raw, canonical in strain_aliases.items():
            with self.subTest(raw=raw):
                self.assertEqual(match_strain(raw, {})["strain"], canonical)
        brands = {
            "Elevate Botanicals": "Elevated Botanicals",
            "R & D Pharms": "R & D Farms",
            "Mr. Birch": "Verist Fields",
            "Little Sticks": "Verist Fields",
            "Big Stick": "Verist Fields",
            "Mnl": "MN Loon",
        }
        for raw, canonical in brands.items():
            with self.subTest(brand=raw):
                self.assertEqual(normalize_brand(raw), canonical)
        self.assertEqual(normalize_brand("Looner"), "Looner")
        for packaging in ("Little Stick", "Little Sticks", "Big Stick", "Big Sticks"):
            self.assertEqual(match_strain(packaging, {})["match_status"], "invalid")

    def test_reconciled_owner_approved_catalog_identifiers(self):
        """Exact-source corrections remain stable across future catalog builds."""
        corrections = load_corrections()
        expected = {
            "auto-2487e5f2eb40c51fcc": {"strain": "Purple Starfruit", "brand": "Campfire Cannabis"},
            "auto-8ad6d1a1481fa7abe6": {"strain": "Sour Lemons", "brand": "Campfire Cannabis"},
            "aurora-20261118-003": {"strain": "Double Sour Grape", "brand": "Verist Fields"},
            "aurora-20261118-006": {"strain": "Valley Frost", "brand": "Verist Fields"},
            "170b620b9d776666aae8": {"strain": "Cereal Milk", "brand": "D'Ope"},
            "research-20261118-015": {"strain": "Tropicana Cherry"},
            "research-20261118-153": {"strain": "Sunset Sherbet"},
            "auto-7f8fe35a8c2cc3c8b3": {"strain": "Strawberry Lemonade", "brand": "Elevated Botanicals", "status": "exclude_vape"},
        }
        for source_id, fields in expected.items():
            with self.subTest(source_id=source_id):
                correction = corrections[source_id]
                for key, value in fields.items():
                    self.assertEqual(correction.get(key), value)
                self.assertIn("expected_raw_name", correction)
                self.assertIn("expected_price", correction)
                self.assertIn("expected_weight_g", correction)
                self.assertEqual(correction.get("retailer"), correction["retailer"].strip())

    def test_diurnal_nector_concentrate_cannot_publish_as_flower(self):
        source=json.loads((Path(__file__).resolve().parents[2] / "data" / "auto_menu_offers.json").read_text())
        item=next(x for x in source if x.get("id")=="auto-439ba7efed7b1a3ba2")
        self.assertIsNone(apply_correction(dict(item),load_corrections(),Counter()))

    def test_fridley_official_url_and_unverified_prices_held(self):
        root=Path(__file__).resolve().parents[2] / "data"
        directory=json.loads((root / "retailer_locations.json").read_text())
        targets=json.loads((root / "retailer_menu_scan_targets.json").read_text())
        records=json.loads((root / "researched_menu_offers.json").read_text())
        self.assertEqual([x["id"] for x in directory if x.get("name")=="Fridley Dispensary"],["MICRO-L25-001290-01-AUR"])
        self.assertNotIn("RESEARCH-PRICED-133",{x["id"] for x in directory})
        self.assertEqual([x["url"] for x in targets if x["id"]=="MICRO-L25-001290-01-AUR"],
                         ["https://fridleydispensary.com/shop/"])
        fridley=[x for x in records if x.get("retailer_id")=="MICRO-L25-001290-01-AUR"]
        self.assertEqual(len(fridley),5)
        self.assertTrue(all(x["url"]=="https://fridleydispensary.com/shop/" for x in fridley))
        self.assertTrue(all(x["record_status"]=="hold_pending_first_party_price_verification" for x in fridley))

    def test_verist_branded_flower_and_distinct_mr_birch(self):
        cases=[
            ("THC: 15.4% VERIST Double Sour Grape (3.5g)", "Double Sour Grape"),
            ("THC: 15.4% Verist Double Sour Grape (3.5g)", "Double Sour Grape"),
            ("THC: 17.6% Verist FeelinMN - Uffda OG", "Uffda OG"),
        ]
        for raw,strain in cases:
            with self.subTest(raw=raw):
                self.assertEqual(identify_product(raw),{"strain":strain,"brand":"Verist Fields"})
        self.assertEqual(identify_product("ON SALE Mr. Birch Little Sticks Uffda OG Preroll"),
                         {"strain": "Uffda OG", "brand": "Verist Fields",
                          "product_variant": "Little Sticks"})

    def test_verist_source_id_corrections(self):
        corrections=load_corrections()
        source=json.loads((Path(__file__).resolve().parents[2] / "data" / "auto_menu_offers.json").read_text())
        expected={"auto-28a41c0e19ac66156c":"Double Sour Grape",
                  "auto-6748d030d74d8f2a4a":"Double Sour Grape",
                  "auto-a554981b5e00028ec8":"Uffda OG"}
        for id_,strain in expected.items():
            with self.subTest(id=id_):
                raw=next(x for x in source if x.get("id")==id_)
                corrected=apply_correction(dict(raw),corrections,Counter())
                self.assertEqual((corrected["strain"],corrected["brand"]),(strain,"Verist Fields"))

    def test_all_rcwm_explicit_brand_product_titles(self):
        cases = {
            "Redwood County Weed Management Cake Mix RCWM 3.5 Flower": "Cake Mix",
            "Redwood County Weed Management Cap Junky-RCWM-3.5 Flower": "Cap Junky",
            "Redwood County Weed Management Halle Berry-RCWM-3.5 Flower": "Halle Berry",
            "Redwood County Weed Management Lemon Cherry Gelato Flower": "Lemon Cherry Gelato",
            "Redwood County Weed Management Sunset Tea Flower": "Sunset Tea",
            "Redwood County Weed Management Gastro Pop-Preroll-1G-1CT": "Gastro Pop",
            "Redwood County Weed Management Jelly Breath-Preroll 1G": "Jelly Breath",
            "Redwood County Weed Management Preroll-RCWM-CapJunky-1 g-1 ct": "Cap Junky",
        }
        for raw,strain in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(
                    identify_product(raw),
                    {"strain": strain, "brand": "Redwood County Weed Management"},
                )

    def test_rcwm_pipe_and_legacy_sku_formats(self):
        variants={
            "Redwood County Weed Management Gastro Pop | 3.5gm Flower": "Gastro Pop",
            "Redwood County Weed Management Gastro Pop | 1gm Preroll": "Gastro Pop",
            "Redwood County Weed Management Preroll | Gastro Pop | 1g | Redwood County Weed Management |": "Gastro Pop",
            "Redwood County Weed Management Preroll | Halle Berry | 1g | Redwood County Weed Management |": "Halle Berry",
            "Redwood County Weed Management Jelly Breath-RCWM-3.5g": "Jelly Breath",
            "Redwood County Weed Management Lemon Cherry Gelato- 1G": "Lemon Cherry Gelato",
        }
        for raw,strain in variants.items():
            with self.subTest(raw=raw):
                self.assertEqual(identify_product(raw),
                                 {"strain":strain,"brand":"Redwood County Weed Management"})

    def test_rcwm_parser_does_not_guess_other_brands(self):
        self.assertIsNone(identify_product("Float Cake Mix Flower"))
        self.assertIsNone(identify_product("Redwood County Weed Management Unrecognized SKU"))

    def test_waabigwan_wiishkobi_and_generic_edible_exclusions(self):
        cases={
            "Wiishkobi Mashkiki-": "Wiishkobi Mashkiki",
            "Whishkobi Mashkiki": "Wiishkobi Mashkiki",
            "Popcorn- Wiishkobi Mashkiki-": "Wiishkobi Mashkiki",
        }
        for name,strain in cases.items():
            with self.subTest(name=name):
                self.assertEqual(identify_product(name),
                                 {"strain":strain,"brand":"Waabigwan Mashkiki"})
        source=json.loads((Path(__file__).resolve().parents[2] / "data" / "auto_menu_offers.json").read_text())
        corrections=load_corrections()
        for key in ("auto-114a1e129b0909ef12","auto-b2e720d0c0cba4043e"):
            item=next(x for x in source if x["id"]==key)
            self.assertIsNone(apply_correction(dict(item),corrections,Counter()))
        for key in ("auto-582a472d6703801ae7","auto-9b1e2119dd7a2821d6"):
            item=next(x for x in source if x["id"]==key)
            corrected=apply_correction(dict(item),corrections,Counter())
            self.assertEqual((corrected["strain"],corrected["brand"]),
                             ("Wiishkobi Mashkiki","Waabigwan Mashkiki"))

    def test_zips_biscotti_28g(self):
        self.assertEqual(identify_product("Zips - Biscotti (Limited Edition)-"),
                         {"strain": "Biscotti", "brand": "Zips"})

    def test_minny_grown_zesty_parm_and_other_brands_not_overridden(self):
        self.assertEqual(identify_product("Minny Grown Zesty Parm | 3.5gm Flower"),
                         {"strain": "Zesty Parm", "brand": "Minny Grown"})
        self.assertIsNone(identify_product("Zesty Parm"))

    def test_owner_exact_id_overrides(self):
        corrections = load_corrections()
        for id_, expected_strain, expected_brand in (
            ("auto-cf5369b8c72a359694", "Biscotti", "Zips"),
            ("research-20261118-132", "Zesty Parm", "Minny Grown"),
        ):
            with self.subTest(id=id_):
                source_name = "auto_menu_offers.json" if id_.startswith("auto-") else "researched_menu_offers.json"
                records = json.loads((Path(__file__).resolve().parents[2] / "data" / source_name).read_text())
                record = next(x for x in records if x.get("id") == id_)
                result = apply_correction(dict(record), corrections, Counter())
                self.assertEqual((result["strain"], result["brand"]), (expected_strain, expected_brand))

    def test_owner_verified_erba_white_widow_and_waabigwan_cheetah_piss(self):
        corrections = load_corrections()
        cases = [
            ("research-jc-20261118-015", "researched_menu_offers.json", "White Widow", "ERBA"),
            ("auto-262c6c8924e39415df", "auto_menu_offers.json", "Cheetah Piss", "Waabigwan Mashkiki"),
        ]
        for id_, source, strain, brand in cases:
            with self.subTest(id=id_):
                records = json.loads((Path(__file__).resolve().parents[2] / "data" / source).read_text())
                item = next(x for x in records if x.get("id") == id_)
                corrected = apply_correction(dict(item), corrections, Counter())
                self.assertEqual((corrected["strain"], corrected["brand"]), (strain, brand))
        self.assertEqual(identify_product("Waabigwan Mashkiki - Cheetah Piss (Limited Edition)-"),
                         {"strain": "Cheetah Piss", "brand": "Waabigwan Mashkiki"})
        self.assertIsNone(identify_product("White Widow"))
        self.assertIsNone(identify_product("Cheetah Piss"))

    def test_dizgo_and_flor_repeated_brand_preroll_titles(self):
        samples = {
            "Dizgo Collective Dizgo Blue Dream Preroll .33g 3 ct": ("Blue Dream", "Dizgo Collective"),
            "Dizgo Collective Dizgo Blue Dream Preroll .5g 2 ct": ("Blue Dream", "Dizgo Collective"),
            "Dizgo Collective Dizgo Hyperion Preroll .33g 3ct": ("Hyperion F1", "Dizgo Collective"),
            "Dizgo Collective Dizgo Hyperion Preroll .5g 2 ct": ("Hyperion F1", "Dizgo Collective"),
            "Dizgo Collective Dizgo Medusa Preroll .5g 2 ct": ("Medusa", "Dizgo Collective"),
            "Dizgo Collective Dizgo Purple Lemonade Preroll .33g 3ct": ("Purple Lemonade", "Dizgo Collective"),
            "Dizgo Collective Dizgo Purple Lemonade Preroll .5g 2ct": ("Purple Lemonade", "Dizgo Collective"),
            "Flor Flor Diamond Dust Preroll .35g 1 ct": ("Diamond Dust", "FLÖR"),
            "Flor Flor Fish Fry Infused Preroll .35g 1 ct": ("Fish Fry", "FLÖR"),
            "Flor Flor Garlic Jam Preroll 1g 1 ct": ("Garlic Jam", "FLÖR"),
            "Flor Flor Gummibears Preroll .35g 1 ct": ("Gummibears", "FLÖR"),
            "Flor Flor Pilot Light 2.0 Preroll 1g 1 ct": ("Pilot Light 2.0", "FLÖR"),
            "OFFER BUY 2 Dizgo Collective Dizgo Medusa Preroll .5g 2 ct": ("Medusa", "Dizgo Collective"),
            "OFFER CONDITIONS APPLY Dizgo Collective Dizgo Hyperion Preroll .33g 3ct": ("Hyperion F1", "Dizgo Collective"),
        }
        for raw,(strain,brand) in samples.items():
            with self.subTest(raw=raw):
                self.assertEqual(parse_structured_title(raw), {"strain": strain, "brand": brand})

    def test_repeated_brand_parser_does_not_guess_unbranded_prerolls(self):
        self.assertIsNone(parse_structured_title("Blue Dream Preroll .5g 2 ct"))
        self.assertIsNone(parse_structured_title("Flor Flor Gummibears 1g Live Rosin"))
        self.assertIsNone(parse_structured_title("OFFER BUY 2 Dizgo Collective Dizgo Medusa"))

    def test_native_care_blue_ox_titles_have_explicit_brand(self):
        for raw,strain in {
            "Native Care Cap Junky": "Cap Junky",
            "Native Care Flower IX | Super Silver Haze | Pre-pack | 3.5g": "Super Silver Haze",
            "Native Care Glitter Bomb": "Glitter Bomb",
            "Native Care Kosher Kush": "Kosher Kush",
            "Native Care Lit OG": "Lit OG",
        }.items():
            with self.subTest(raw=raw):
                self.assertEqual(parse_structured_title(raw), {"strain": strain, "brand": "Native Care"})

    def test_unbound_and_verist_mr_birch_preroll_titles(self):
        cases = {
            "Unbound Unbound MAC V2 Preroll .5g 5 ct": ("MAC V2","Unbound"),
            "Unbound Unbound Purple Ice Water Preroll 1g 1 ct": ("Purple Ice Water","Unbound"),
            "Unbound Unbound Vanilla Berries Preroll .5g 5 ct": ("Vanilla Berries","Unbound"),
            "Unbound Unbound Watermelon Pound Cake Preroll .5g 5 ct": ("Watermelon Pound Cake","Unbound"),
            "Verist Fields Mr. Birch Mimosa Ice Preroll .35g 5 ct": ("Mimosa Ice","Verist Fields"),
            "Verist Fields Mr. Birch Valley Frost Preroll .35g 5 ct": ("Valley Frost","Verist Fields"),
            "OFFER CONDITIONS APPLY Unbound Unbound Purple Ice Water Preroll 1g 1 ct": ("Purple Ice Water","Unbound"),
        }
        for name,(strain,brand) in cases.items():
            with self.subTest(name=name):
                self.assertEqual(parse_structured_title(name),{"strain":strain,"brand":brand})
        from strain_rules import normalize_brand
        self.assertEqual(normalize_brand("Mr. Birch"),"Verist Fields")
        self.assertEqual(normalize_brand("Mr Birch"),"Verist Fields")

    def test_dizgo_hyperion_and_flor_fog_dog(self):
        self.assertEqual(parse_structured_title("ON SALE Dizgo Hyperion F1 (3-Pack) Preroll"),
                         {"strain":"Hyperion F1","brand":"Dizgo Collective"})
        self.assertEqual(parse_structured_title("Indica FLÖR Fog Dog- 3.5- Flor 1/8 oz"),
                         {"strain":"Fog Dog","brand":"FLÖR"})
        self.assertEqual(parse_structured_title("FLÖR Fog Dog- 3.5- Flor 1/8 oz"),
                         {"strain":"Fog Dog","brand":"FLÖR"})
        self.assertEqual(parse_structured_title("Fog Dog"),None)

    def test_green_goods_structured_brand_and_strain(self):
        self.assertEqual(parse_structured_title("Indica flower Brownie Scout RYTHM Premium Flower"),
                         {"strain": "Brownie Scout", "brand": "RYTHM"})
        self.assertEqual(parse_structured_title("Sativa flower Durban Dream Boundary Waters Mixed Bud"),
                         {"strain": "Durban Dream", "brand": "Boundary Waters"})
        self.assertEqual(parse_structured_title("Hybrid flower OMG Good Green Flower"),
                         {"strain": "OMG", "brand": "Good Green"})

    def test_pipe_separated_brand_and_strain(self):
        self.assertEqual(parse_structured_title("Flower-IX | Native Care | Donny Burger | 3.5g (Flowers/Buds - Packaged)"),
                         {"strain": "Donny Burger", "brand": "Native Care"})
        self.assertEqual(parse_structured_title("Float Float | Pre-Packaged | Blue Dream | 3.5g"),
                         {"strain": "Blue Dream", "brand": "Float Cannabis"})

    def test_float_product_title(self):
        self.assertEqual(parse_structured_title("Float 3.5g Jar Magic Marker"),
                         {"strain": "Magic Marker", "brand": "Float Cannabis"})
        self.assertEqual(parse_structured_title("Float 1x1g Pre Rolls Cap Junky"),
                         {"strain": "Cap Junky", "brand": "Float Cannabis"})

    def test_explicit_brands_in_sale_titles(self):
        self.assertEqual(parse_structured_title("ON SALE Avio Mendo Breath Preroll"),
                         {"strain": "Mendo Breath", "brand": "Avio"})
        self.assertEqual(parse_structured_title("ON SALE Native Cuts Cheetah Piss Flower"),
                         {"strain": "Cheetah Piss", "brand": "Native Cuts"})
        self.assertEqual(parse_structured_title("ON SALE Float Lemon Fresh Flower"),
                         {"strain": "Lemon Fresh", "brand": "Float Cannabis"})

    def test_do_not_guess_unrecognized_title(self):
        self.assertIsNone(parse_structured_title("Zesty Parm"))
        self.assertIsNone(parse_structured_title("3.5g"))
        self.assertIsNone(parse_structured_title("Special Flower - Sale"))

    def test_owner_confirmed_alien_rock_candy(self):
        x = identify_product("Alien Rock Candy-")
        self.assertEqual(x, {"strain": "Alien Rock Candy", "brand": "Native Cuts"})

    def test_animal_scout_rythm(self):
        x = identify_product("Indica flower Animal Scout RYTHM Premium Flower")
        self.assertEqual(x, {"strain": "Animal Scout", "brand": "RYTHM"})

    def test_apple_fritter_rcwm_is_not_the_brand_float(self):
        x = identify_product("Redwood County Weed Management Apple Fritter RCWM 3.5 Flower")
        self.assertEqual(x, {"strain": "Apple Fritter", "brand": "Redwood County Weed Management"})

    def test_autopilot_merged_naming(self):
        self.assertEqual(identify_product("Auto Pilot - Distillate Infused Pre Roll")["strain"], "Autopilot")
        self.assertEqual(identify_product("AutoPilot-Infused PreRoll-Packaged Preroll")["strain"], "Autopilot")
        self.assertEqual(match_strain("Auto Pilot", {})["strain"], "Autopilot")

    def test_unique_brand_fill(self):
        offers = [{"strain": "Animal Scout", "brand": "RYTHM"},
                  {"strain": "Animal Scout", "brand": ""}]
        counts = Counter()
        infer_missing_brands(offers, counts)
        self.assertEqual(offers[1]["brand"], "RYTHM")
        self.assertEqual(offers[1]["brand_source"], "unique_strain_brand")

    def test_ambiguous_brand_remains_blank(self):
        offers = [{"strain": "Apple Fritter", "brand": "Float Cannabis"},
                  {"strain": "Apple Fritter", "brand": "Redwood County Weed Management"},
                  {"strain": "Apple Fritter", "brand": ""}]
        counts = Counter()
        infer_missing_brands(offers, counts)
        self.assertEqual(offers[2]["brand"], "")
        self.assertEqual(counts["brands_ambiguous_unassigned"], 1)

    def test_owner_confirmed_strain_fill(self):
        offers = [{"strain": "Alien Rock Candy", "brand": ""}]
        infer_missing_brands(offers, Counter())
        self.assertEqual(offers[0]["brand"], "Native Cuts")

    def test_do_not_override_existing_brand(self):
        offers = [{"strain": "Animal Scout", "brand": "Independent Brand"},
                  {"strain": "Animal Scout", "brand": "RYTHM"}]
        infer_missing_brands(offers, Counter())
        self.assertEqual(offers[0]["brand"], "Independent Brand")


    def test_animal_face_brands_are_product_specific(self):
        self.assertEqual(identify_product("Indica flower Animal Face RYTHM Mini Buds"), {"strain": "Animal Face", "brand": "RYTHM"})
        self.assertEqual(identify_product("Big Dog | Animal Face |"), {"strain": "Animal Face", "brand": "Big Dog"})
        self.assertEqual(identify_product("RYTHM | Animal Face |"), {"strain": "Animal Face", "brand": "RYTHM"})

    def test_autopilot_is_avio(self):
        self.assertEqual(identify_product("Auto Pilot - Distillate Infused Pre Roll"), {"strain": "Autopilot", "brand": "Avio"})
        self.assertEqual(identify_product("AutoPilot-Infused PreRoll-Packaged Preroll"), {"strain": "Autopilot", "brand": "Avio"})

    def test_beaver_cookies_green_goods_seven_gram(self):
        self.assertEqual(identify_product("Beaver Cookies 7g"), {"strain": "Beaver Cookies", "brand": "Green Goods"})

    def test_weight_specific_brand_does_not_overwrite_other_animal_face_brands(self):
        offers = [
            {"strain": "Animal Face", "brand": "RYTHM", "category": "Flower", "package_g": 7},
            {"strain": "Animal Face", "brand": "Dogwalkers", "category": "Preroll", "package_g": 0.75},
            {"strain": "Animal Face", "brand": "Big Dog", "category": "Preroll", "package_g": 0.75},
            {"strain": "Animal Face", "brand": "", "category": "Flower", "package_g": 7},
            {"strain": "Animal Face", "brand": "", "category": "Preroll", "package_g": 0.75},
        ]
        infer_missing_brands(offers, Counter())
        self.assertEqual(offers[3]["brand"], "RYTHM")
        self.assertEqual(offers[3]["brand_source"], "unique_strain_category_weight")
        self.assertEqual(offers[4]["brand"], "")
        self.assertEqual(offers[0]["brand"], "RYTHM")
        self.assertEqual(offers[1]["brand"], "Dogwalkers")


    def test_dinky_dope_corrections_map_to_source_urls(self):
        source = Path(__file__).resolve().parents[2] / "data" / "auto_menu_offers.json"
        offers = json.loads(source.read_text(encoding="utf-8"))
        by_id = {x["id"]: x for x in offers}
        expected = {
            "auto-a68a8dbcac0b4dcc10": "Franken Pine",
            "auto-7e9cdf2db4023b2704": "Lit OG",
            "auto-66aca672bc6ba170b7": "Fight Club",
            "auto-dc5d027efa5520ae02": "Cap Junky",
            "auto-92b4ad465a5561e9a5": "OG Kush",
            "auto-628f3cf1d58fefe76b": "Lemon Fresh",
            "auto-aae836c68068b2092a": "Granola Funk",
            "auto-0eb53e9468e1e80103": "Bangkok Purple",
        }
        corrections = load_corrections()
        for source_id, strain in expected.items():
            with self.subTest(source_id=source_id):
                original = by_id[source_id]
                amended = apply_correction(dict(original), corrections, Counter())
                self.assertEqual(amended["strain"], strain)
                self.assertEqual(amended["product_name"], strain)
                self.assertEqual(amended["raw_scanned_product_name"], "0 0 in cart")
                self.assertEqual(amended["retailer_id"], "MICRO-L25-000658-01-AUR")

    def test_dinky_dope_source_url_change_blocks_stale_correction(self):
        corrections = load_corrections()
        source_id = "auto-a68a8dbcac0b4dcc10"
        original = json.loads((Path(__file__).resolve().parents[2] / "data" / "auto_menu_offers.json").read_text())
        item = next(x for x in original if x.get("id") == source_id)
        tampered = {**item, "url": "https://shop.dinkydope.com/dinkytown/menu/flower-6450/other-product"}
        with self.assertRaisesRegex(ValueError, "source URL changed"):
            apply_correction(tampered, corrections, Counter())


    def test_approved_source_price_change_keeps_live_price(self):
        corrections = load_corrections()
        source_id = "auto-748d57a22f6a180e2d"
        records = json.loads((Path(__file__).resolve().parents[2] / "data" / "auto_menu_offers.json").read_text())
        original = next(x for x in records if x.get("id") == source_id)
        newer = {**original, "price": 45.0}
        counts = Counter()
        result = apply_correction(newer, corrections, counts)
        self.assertEqual(result["price"], 45.0)
        self.assertEqual(result["strain"], "Cheetah Piss")
        self.assertEqual(counts["approved_identity_with_new_observed_price"], 1)

    def test_reviewed_retailer_alias_requires_correct_license_id(self):
        corrections = load_corrections()
        source_id = "auto-a68a8dbcac0b4dcc10"
        records = json.loads((Path(__file__).resolve().parents[2] / "data" / "auto_menu_offers.json").read_text())
        original = next(x for x in records if x.get("id") == source_id)
        alias = {**original, "retailer": "Dinky Dope"}
        result = apply_correction(alias, corrections, Counter())
        self.assertEqual(result["strain"], "Franken Pine")
        wrong_store = {**alias, "retailer_id": "MICRO-OTHER-LOCATION"}
        with self.assertRaisesRegex(ValueError, "Source changed"):
            apply_correction(wrong_store, corrections, Counter())

    def test_approved_correction_still_rejects_changed_title_and_weight(self):
        corrections = load_corrections()
        source_id = "auto-a68a8dbcac0b4dcc10"
        records = json.loads((Path(__file__).resolve().parents[2] / "data" / "auto_menu_offers.json").read_text())
        original = next(x for x in records if x.get("id") == source_id)
        for change in ({"product_name": "Different strain 3.5g"}, {"package_g": 7.0}):
            with self.subTest(change=change):
                with self.assertRaisesRegex(ValueError, "Source changed"):
                    apply_correction({**original, **change}, corrections, Counter())


if __name__ == "__main__":
    unittest.main()
