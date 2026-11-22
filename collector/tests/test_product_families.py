import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from product_families import product_family, canonical_brand_family, annotate, reviewed_product_family

class Families(unittest.TestCase):
    def test_bourbon_zulu_alias(self):
        self.assertEqual(product_family("Bourbon Berry Zulu"),("Bourbon Berry Zulu","approved_exact_alias"))
        self.assertEqual(product_family("Zulu Terp"),("Bourbon Berry Zulu","approved_exact_alias"))
    def test_bumper_variations_group(self):
        self.assertEqual(product_family("Bumper OG - Premium")[0],"Bumper OG")
    def test_banana_hybrid_is_not_exact_alias(self):
        self.assertEqual(product_family("Banana Push Pop x Gummi Bear"),("Banana Push Pop","variant_family"))
        self.assertEqual(product_family("Banana Push Pop"),("Banana Push Pop","variant_family"))
    def test_lake_leaf_brand_family_preserves_source(self):
        a=annotate({"strain":"Bumper OG","brand":"Lake Leaf","price":30,"package_g":4})
        b=annotate({"strain":"Bumper OG","brand":"Campfire Cannabis","price":40,"package_g":3.5})
        self.assertEqual(a["brand_family"],b["brand_family"])
        self.assertNotEqual(a["brand"],b["brand"])
        self.assertNotEqual(a["package_g"],b["package_g"])
    def test_owner_approved_berry_zulu_and_aurora(self):
        self.assertEqual(reviewed_product_family("Berry Zulu - Bourbon Berry x Whiskey Zulu [Sauce]","D'ope! Cannabis","Concentrate")[0],"Bourbon Berry x Whiskey Zulu")
        self.assertEqual(reviewed_product_family("Aurora Blend Terp Badder","D'ope! Cannabis","Concentrate")[0],"Aurora Blend")
    def test_brand_category_guard_prevents_unrelated_merge(self):
        self.assertIsNone(reviewed_product_family("Jack Herer","Another Producer","Vape"))
        self.assertIsNone(reviewed_product_family("Jack Herer","Oma","Flower"))
        self.assertIsNone(reviewed_product_family("Skywalker OG","Float Cannabis","Vape"))
    def test_variants_group_without_changing_source_fields(self):
        original={"strain":"Skywalker","brand":"Unbound","category":"Vape","price":32,"package_g":1}
        result=annotate(original)
        self.assertEqual(result["product_family"],"Skywalker OG")
        self.assertEqual(result["price"],32)
        self.assertEqual(result["strain"],"Skywalker")
    def test_reviewed_apricot_and_froot_aliases(self):
        self.assertEqual(reviewed_product_family("Sunset Apricot Orange Disposable","Tasty Gems","Vapes")[0],"Sunstone Apricot Orange")
        self.assertEqual(reviewed_product_family("Atlas Froot by the Foot Premium","Mischief","Flower")[0],"Froot by the Foot")
    def test_noisy_zesty_titles_are_same_strain(self):
        variants = [
            "Avion PreRoll-X | Avion | Zesty Parm | 1 g (CANNABIS FLOWER (PACKAGED))",
            "Minny Grown | Zesty Parm | 2pk .75g Preroll | Sativa",
            "OFFER CONDITIONS APPLY Dizgo | Pre-Packaged | Zesty Parm | 3.5g",
        ]
        for label in variants:
            with self.subTest(label=label):
                row = annotate({"product_name": label, "strain": label, "brand": "Dizgo", "category": "Preroll", "price": 22})
                self.assertEqual(row["strain"], "Zesty Parm")
                self.assertEqual(row["product_family"], "Zesty Parm")
                self.assertEqual(row["price"], 22)
    def test_unrelated_strains_remain_separate(self):
        self.assertEqual(product_family("Guava"),("Guava","unmapped"))
        self.assertEqual(product_family("Banana OG"),("Banana OG","unmapped"))

if __name__=="__main__":
    unittest.main()
