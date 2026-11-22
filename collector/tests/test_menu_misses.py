import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from track_menu_misses import advance, menu_page, product_key


class MenuMissTests(unittest.TestCase):
    page = "https://retailer.example/rec/menu"
    product = "https://retailer.example/rec/flower/pdp/item-123"
    retailer = "Store A"
    name = "Flower — 3.5 g"
    siblings = [(f"retailer.example/rec/flower/pdp/item-{i}", f"flower {i}") for i in range(5)]

    def setUp(self):
        self.key = product_key(self.product, self.name)
        self.published = [("item", (self.retailer, *self.key)),
                          ("other-store", ("Store B", *self.key))]
        self.start = dt.datetime(2026, 11, 19, 14, tzinfo=dt.timezone.utc)

    def scan(self, index, offers, *, connection="reachable", limited=False, count=True, state=None, candidate=False):
        checked_at = (self.start + dt.timedelta(hours=12 * index)).isoformat()
        scan = {"checked_at": checked_at, "limited": limited,
                "statuses": [{"license": self.retailer, "connection": connection,
                              "menu_pages": [{"url": self.page, "offers": offers}]}]}
        candidates = [{"store_id": self.retailer, "checked_at": checked_at,
                       "url": self.product, "product_name": self.name}] if candidate else []
        return advance(state or {}, self.published, scan, candidates, count)

    def test_tenth_miss_hides_and_return_restores_exact_offer(self):
        state = self.scan(0, [*self.siblings, self.key])
        self.assertNotIn("other-store", state["offers"])
        for index in range(1, 10):
            state = self.scan(index, self.siblings, state=state)
            self.assertEqual(state["offers"]["item"]["misses"], index)
            self.assertEqual(state["retired_ids"], [])
        state = self.scan(10, self.siblings, state=state)
        self.assertEqual(state["retired_ids"], ["item"])
        state = self.scan(11, [], state=state, candidate=True)
        self.assertEqual(state["retired_ids"], [])
        self.assertEqual(state["offers"]["item"]["misses"], 0)

    def test_only_once_per_slot_and_failed_partial_manual_scans_do_not_count(self):
        state = self.scan(0, [*self.siblings, self.key])
        state = self.scan(1, self.siblings, state=state)
        for index, offers, params in [
            (1, self.siblings, {}),
            (2, self.siblings, {"connection": "failed"}),
            (3, [], {}),
            (4, self.siblings[:2], {}),
            (5, self.siblings, {"count": False}),
            (6, self.siblings, {"limited": True}),
        ]:
            state = self.scan(index, offers, state=state, **params)
            self.assertEqual(state["offers"]["item"]["misses"], 1)
        state = self.scan(7, self.siblings, state=state)
        self.assertEqual(state["offers"]["item"]["misses"], 2)

    def test_capture_rejects_pagination_redirects_and_non_product_links(self):
        item = {"url": self.product, "product_name": self.name}
        result = {"ok": True, "url": self.page, "html": ""}
        self.assertEqual(menu_page(self.page, result, [item])["offers"], [self.key])
        self.assertIsNone(menu_page(self.page, {**result, "html": '<a rel="next">Next</a>'}, [item]))
        self.assertIsNone(menu_page(self.page, {**result, "url": self.page + "/different"}, [item]))
        self.assertIsNone(menu_page(self.page, result, [{**item, "url": self.page}]))
