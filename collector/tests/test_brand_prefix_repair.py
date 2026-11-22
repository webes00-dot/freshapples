import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
from brand_prefix_repair import repair_brand_prefix_title

NAMES=["Gush Kush","Swedish OG","Mimosa Ice","Valley Frost",
       "Octane Mintz","Froot by the Foot","Mendo Breath","Turtle Taffy",
       "White Widow","Aloha Sugar","Daily Grape","Kanobi Sunset",
       "Killer Cupcake"]
MASTER={x.casefold():x for x in NAMES}

CASES=[
 ("OFFER CONDITIONS APPLY Verist Gush Kush 5x .35g Pre Roll","Gush Kush","Verist Fields",None),
 ("OFFER CONDITIONS APPLY Verist Swedish OG little sticks 5x .35g","Swedish OG","Verist Fields","Little Sticks"),
 ("Verist Gush Kush 1g Pre Roll","Gush Kush","Verist Fields",None),
 ("Verist Swedish OG 1g Pre Roll","Swedish OG","Verist Fields",None),
 ("Verist Gush Kush 3.5g","Gush Kush","Verist Fields",None),
 ("Verist Mimosa Ice Flower 3.5g","Mimosa Ice","Verist Fields",None),
 ("Verist Swedish OG 3.5g","Swedish OG","Verist Fields",None),
 ("OFFER CONDITIONS APPLY Trailhead Reserve Octane Mintz","Octane Mintz","Trailhead Cannabis","Reserve"),
 ("Verist Valley Frost Flower 3.5g","Valley Frost","Verist Fields",None),
 ("Verist fields Valley Frost 3.5","Valley Frost","Verist Fields",None),
 ("Highnorth Froot by the Foot Discovery Pack - 2g","Froot by the Foot",None,"Discovery Pack"),
 ("Highnorth Mendo Breath Discovery Pack - 2g","Mendo Breath",None,"Discovery Pack"),
 ("Highnorth Turtle Taffy Discovery Pack - 2g","Turtle Taffy",None,"Discovery Pack"),
 ("Highnorth White Widow Discovery Pack - 2g","White Widow",None,"Discovery Pack"),
 ("Rewind Daily Grape - .5g Live Rosin Disposable","Daily Grape","Rewind",None),
 ("Rewind Kanobi Sunset - 0.5g Live Rosin Disposable","Kanobi Sunset","Rewind",None),
 ("Rewind Killer Cupcake - 0.5g Live Rosin Disposable","Killer Cupcake","Rewind",None),
 ("Rewind Aloha Sugar - 0.5g Distillate Syringe","Aloha Sugar","Rewind",None),
]

class ApprovedBrandPrefixRepairTests(unittest.TestCase):
 def test_all_18_live_catalog_defect_patterns(self):
  for i,(title,strain,brand,variant) in enumerate(CASES):
   with self.subTest(title=title):
    item={"id":"test-id-"+str(i),"strain":title,"product_name":title,
          "retailer":"Highnorth" if title.startswith("Highnorth") else "Source Store",
          "price":43.5,"package_g":2,"url":"https://example.org/correct-product"}
    raw=dict(item)
    parsed=repair_brand_prefix_title(item,MASTER,{})
    self.assertIsNotNone(parsed)
    self.assertEqual(parsed["strain"],strain)
    self.assertEqual(parsed.get("brand"),brand)
    self.assertEqual(parsed.get("product_variant"),variant)
    self.assertEqual(item,raw,"Source observations must not be mutated")
 def test_missing_canonical_strain_is_review_not_guess(self):
  item={"strain":"Rewind Daily Grape - .5g Live Rosin Disposable","retailer":"Unwind"}
  self.assertIsNone(repair_brand_prefix_title(item,{},{}))
 def test_highnorth_is_retailer_not_manufacturer(self):
  item={"strain":"Highnorth Froot by the Foot Discovery Pack - 2g","retailer":"Another Store"}
  self.assertIsNone(repair_brand_prefix_title(item,MASTER,{}))
 def test_unknown_prefix_does_not_guess(self):
  for title in ("Verist Something Invented 3.5g",
                "Rewind Grape Wedding - 0.5g Live Rosin Disposable",
                "Trailhead Reserve Unconfirmed",
                "Highnorth Garlic Kush Discovery Pack - 2g"):
   with self.subTest(title=title):
    self.assertIsNone(repair_brand_prefix_title({"strain":title,"retailer":"Highnorth"},MASTER,{}))


if __name__=="__main__":
 unittest.main()
