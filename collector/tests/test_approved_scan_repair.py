import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from approved_scan_repair import repair_scan_identity

MASTER_NAMES = {
    n.casefold(): n for n in (
        "Cap Junky", "Froot by the Foot", "Brownie Scout", "Zesty Parm",
        "Block Party", "Gorilla Zkittlez", "Biscotti", "Trilla",
        "Space Boogie", "Mendo Breath", "Double Sour Grape",
        "Hawaiian Fanta", "Velvet Glove"
    )
}


class ApprovedScanRepairTests(unittest.TestCase):
    def check(self, label, expected, **source):
        source.setdefault("product_name", label)
        source.setdefault("strain", label)
        actual = repair_scan_identity(source, MASTER_NAMES, {})
        self.assertEqual(actual, expected)

    def test_greenhouse_cart_label_uses_specific_product_url(self):
        self.check("0 0 in cart", {"strain": "Cap Junky"},
                   url="https://thegreenhousecannabisco.com/mn/forestlake/menu/flower-12433/buds-hybrid-cap-junky-35g-749724?idx=2")
        self.check("SALE 0 0 in cart", {"strain": "Froot by the Foot"},
                   url="https://thegreenhousecannabisco.com/mn/forestlake/menu/flower-12433/buds-hybrid-froot-by-the-foot-35g-818799")
        self.check("0 0 in cart", None,
                   url="https://thegreenhousecannabisco.com/mn/forestlake/menu/flower-12433/buds-hybrid-unverified-strain-35g-12345")
        self.check("0 0 in cart", None,
                   url="https://another-dispensary.com/flower/buds-hybrid-cap-junky-35g-749724")

    def test_green_goods_brand_and_variants(self):
        for variant in ("Premium Flower", "Mini Buds", "Mixed Buds"):
            self.check("Indica flower Brownie Scout RYTHM " + variant,
                       {"strain": "Brownie Scout", "brand": "RYTHM",
                        "product_variant": variant},
                       url="https://visitgreengoods.com/shop-minnesota/products/39415/rythm-indica-brownie-scout")
        self.check("Indica flower Unknown Clone RYTHM Mini Buds", None,
                   url="https://visitgreengoods.com/shop-minnesota/products/123/rythm-indica-unknown-clone")

    def test_green_apple_delimiters_keep_strain(self):
        self.check("Minny Grown Zesty Parm | 3.5gm Flower",
                   {"strain": "Zesty Parm", "brand": "Minny Grown"},
                   retailer="Green Apple", url="https://greenapplecannabis.dispensary.shop/rec/menu",
                   strain="3.5gm Flower")
        self.check("Redwood County Weed Management Block Party | 1gm Preroll",
                   {"strain": "Block Party", "brand": "Redwood County Weed Management"},
                   retailer="Green Apple", strain="1gm Preroll")
        self.check("Float Cannabis Gorilla Zkittlez | 1gm Preroll",
                   {"strain": "Gorilla Zkittlez", "brand": "Float Cannabis"},
                   retailer="Green Apple", strain="1gm Preroll")

    def test_waabigwan_grade_and_trailing_separator(self):
        self.check("Popcorn- Biscotti-", {"strain": "Biscotti", "product_variant": "Popcorn"},
                   retailer="Waabigwan Mashkiki — Mahnomen")
        self.check("Trilla-", {"strain": "Trilla"},
                   retailer="Waabigwan Mashkiki — Mahnomen")
        self.check("MAC 1-", None, retailer="Waabigwan Mashkiki — Saint Cloud")

    def test_promo_flor_and_verist(self):
        self.check("ON SALE FLOR Mendo Breath Flower",
                   {"strain": "Mendo Breath", "brand": "FLÖR"},
                   retailer="B & D Cannabis")
        self.check("THC: 15.4% VERIST Double Sour Grape (3.5g)",
                   {"strain": "Double Sour Grape", "brand": "Verist Fields"})
        self.check("THC: 15.4% Verist Double Sour Grapes (3.5g)",
                   {"strain": "Double Sour Grape", "brand": "Verist Fields"})

    def test_hawaiian_transcription_and_velvet_variant(self):
        self.check("Unbound Hawiaain Fanta 3.5g",
                   {"strain": "Hawaiian Fanta", "brand": "Unbound"})
        for variant in ("Popcorn", "Mixed Buds"):
            self.check("Rythm | " + variant + " | Velvet Glove RYTHM",
                       {"strain": "Velvet Glove", "brand": "RYTHM",
                        "product_variant": variant},
                       retailer="MN Roots Crosslake")

    def test_no_unverified_identity_generation(self):
        self.check("Some Unknown Brand Novel Strain Flower", None,
                   retailer="Green Apple")
        self.check("0 0 in cart", None, retailer="The Greenhouse Cannabis Company",
                   url="https://thegreenhousecannabisco.com/mn/forestlake/menu/flower-12433/buds-hybrid-not-master-35g-123456")


if __name__ == "__main__":
    unittest.main()
