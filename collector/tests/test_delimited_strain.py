import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
from delimited_strain import resolve_delimited_strain

MASTER = {s.casefold():s for s in [
    "Cap Junky","Mendo Breath","Blue Dream","Platinum Jesus",
    "Hawaiian Fanta","Mac V2","Rainbow Run","Purple Octane",
    "Double Sour Grape","Animal Face","Durban Z","Gogurtz",
    "Illemonati","Orangade","Papaya Fuel","Valley Frost",
    "Orion","Turtle Taffy","LA Kush Cake","Mimosa Ice",
    "Gorilla Zkittlez","Toad Venom","Magic Marker","Blue Zushi","OG Kush","Trainwreck","Blueberry Diesel","Grape Canyon Zkittlez"
]}
class DelimitedNameTests(unittest.TestCase):
    def test_exact_master_segments_and_explicit_brands(self):
        cases = [
            ("Preroll-IX | RCWM | Cap Junky |", "Cap Junky","Redwood County Weed Management"),
            ("Preroll-IX | Avio | Mendo Breath 1 |","Mendo Breath","Avio"),
            ("-IX | Verist Fields | Platinum Jesus |","Platinum Jesus","Verist Fields"),
            ("Pre-Packaged REM IX | Unbound | Hawaiian Fanta |","Hawaiian Fanta","Unbound"),
            ("RYTHM | Animal Face |","Animal Face","RYTHM"),
            ("Unbound | Illemonati |","Illemonati","Unbound"),
            ("erba | Minnie's | Turtle Taffy |","Turtle Taffy","ERBA"),
            ("Verist Fields | Little Stick | Mimosa Ice |","Mimosa Ice","Verist Fields"),
            ("Float Cannabis Magic Marker | 3.5gm Flower","Magic Marker","Float Cannabis"),
            ("Rainbow Run | Distillate Infused | Pre Roll","Rainbow Run",None),
            ("Northpark OG Kush Cart | 1gm Vapes","OG Kush","Northpark"),
            ("Bud Doctor Blueberry Diesel |","Blueberry Diesel","Bud Doctor"),
            ("$10.00 OFF Lake Leaf Grape Canyon Zkittlez |","Grape Canyon Zkittlez","Lake Leaf"),
        ]
        for title, strain, brand in cases:
            with self.subTest(title=title):
                actual=resolve_delimited_strain(title,MASTER,{})
                self.assertEqual(actual and actual["strain"],strain)
                self.assertEqual(actual and actual.get("brand"),brand)
    def test_unresolved_or_accessories_are_not_guessed(self):
        for title in ["Good Green |","Satya Incense | PATCHOULI",
                      "Zombie Resin-IX | Stash & Co x Loon Labs | Various Strains |",
                      "Any Fake | Unknown |",
                      "RYTHM | Animal Face | Purple Octane"]:
            with self.subTest(title=title):
                self.assertIsNone(resolve_delimited_strain(title,MASTER,{}))

if __name__=="__main__": unittest.main()
