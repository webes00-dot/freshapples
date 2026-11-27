import json
from pathlib import Path
import sqlite3
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from discover_entities import Names, discover_products, review, target_rows
from flowhub_adapter import extract_cards


OPERATIONS = json.loads((Path(__file__).resolve().parents[2] / "src" / "scanner-entity-queries.json").read_text())


class EntityDiscoveryTests(unittest.TestCase):
    def test_structured_flowhub_identity_is_matched_to_the_exact_card(self):
        variant = {"variant_id": "v1", "brand": "Example Farms", "product_name": "Plum Pie | 3.5g"}
        page = '<script>__remixContext.p(' + json.dumps([variant]) + ');</script>'
        page += '<a href="/rec/flower/pdp/plum-pie/v/v1">Example Farms Plum Pie Flower $20.00 / 3.5g</a>'
        page += '<a href="/rec/flower/pdp/lemon-pie/v/v2">Example Farms Lemon Pie Flower $20.00 / 3.5g</a>'
        card, other = extract_cards(page, "https://example.dispensary.shop/rec/menu")
        self.assertEqual(card["observed_brand"], "Example Farms")
        self.assertEqual(card["observed_product_name"], "Plum Pie | 3.5g")
        self.assertIsNone(other["observed_brand"])

    def test_master_insert_respects_aliases_and_is_safe_to_repeat(self):
        db = sqlite3.connect(":memory:")
        db.executescript("""
          CREATE TABLE brands (canonical_name TEXT COLLATE NOCASE UNIQUE, research_status TEXT, raw_json TEXT, updated_at TEXT);
          CREATE TABLE strains (canonical_name TEXT COLLATE NOCASE UNIQUE, review_status TEXT, raw_json TEXT, updated_at TEXT);
          CREATE TABLE review_queue (entity_type TEXT, entity_key TEXT, reason TEXT, payload_json TEXT);
        """)
        indexes = {
            "brand": Names([], [{"observed_name": "Existing Farms", "canonical_name": "Existing Cannabis"}]),
            "strain": Names([{"canonical_name": "Blue Dream", "aliases": "Blue Test"}], []),
        }
        common = {"category": "Flower", "source_method": "flowhub_html_card_review_only",
                  "url": "https://example.dispensary.shop/rec/flower/pdp/plum-pie/v/v1", "store_id": "store-one"}
        offers = [
            {**common, "observed_brand": "Existing Farms", "observed_product_name": "Blue Test | 3.5g"},
            {**common, "observed_brand": "One Example", "observed_product_name": "Plum Pie | 3.5g | 22%"},
            {**common, "store_id": "store-two", "url": "https://another.dispensary.shop/rec/flower/pdp/plum-pie/v/v2",
             "observed_brand": "One Example", "observed_product_name": "Plum Pie | 3.5g"},
            {**common, "observed_brand": "Single Source", "observed_product_name": "Indica Blend | 3.5g"},
            {**common, "observed_brand": "One Example", "observed_product_name": "BlueDream"},
        ]
        commands, events = discover_products(offers, indexes)
        for command in commands * 2:
            db.execute(OPERATIONS[command["operation"]]["sql"], command["params"])
        self.assertEqual(db.execute("SELECT canonical_name FROM brands").fetchall(), [("One Example",)])
        self.assertEqual(db.execute("SELECT canonical_name FROM strains").fetchall(), [("Plum Pie",)])
        self.assertIn(("strain", "BlueDream", "scanner_identity_uncertain"), [e[:3] for e in events])
        self.assertIn(("brand", "Single Source", "scanner_single_source"), [e[:3] for e in events])
        for _ in range(2):
            command = review("strain", "plum pie", "scanner_new_entity", offers[1])
            db.execute(OPERATIONS[command["operation"]]["sql"], command["params"])
        self.assertEqual(db.execute("SELECT count(*) FROM review_queue").fetchone(), (1,))

    def test_d1_targets_add_retailers_and_preserve_deeper_same_host_menu(self):
        legacy = [{"license": "a", "retailer": "A", "verified_direct_menu_url": "https://a.example/menu"}]
        current = [
            {"license_id": "a", "display_name": "A", "menu_url": "https://a.example/"},
            {"license_id": "b", "display_name": "B", "menu_url": "https://b.example/menu"},
            {"license_id": "c", "display_name": "C", "menu_url": "https://weedmaps.com/menu/c"},
        ]
        self.assertEqual(target_rows(current, legacy), legacy + [
            {"license": "b", "retailer": "B", "verified_direct_menu_url": "https://b.example/menu"},
        ])
