#!/usr/bin/env python3
"""Track absent offers on comparable retailer menu pages. Keep raw observations."""
import argparse
import datetime as dt
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
MISS_LIMIT = 10
CENTRAL = ZoneInfo("America/Chicago")
SOURCES = ("listings.json", "researched_menu_offers.json",
           "new_retailer_menu_offers.json", "auto_menu_offers.json")
DETAIL_PATH = re.compile(r"/(?:pdp|products?)/[^/]+", re.I)
PAGINATION = re.compile(
    r"""rel\s*=\s*["']next["']|[?&](?:page|paged)=[2-9]\d*\b|"""
    r"""pagination[-_]next|>\s*(?:load|show) more(?: products)?\s*<""", re.I)


def product_key(url, title):
    parsed = urlsplit(str(url or ""))
    title = " ".join(str(title or "").split()).casefold()
    if parsed.scheme == "https" and parsed.hostname and DETAIL_PATH.search(parsed.path) and title:
        return parsed.hostname + parsed.path.rstrip("/"), title
    return None


def menu_page(requested_url, response, products):
    """Record products from one nonempty, unpaginated page at its expected URL."""
    actual = str(response.get("url") or "").rstrip("/")
    if (not response.get("ok") or actual != requested_url.rstrip("/") or
            PAGINATION.search(response.get("html") or "")):
        return None
    offers = {key for item in products if (key := product_key(item.get("url"), item.get("product_name")))}
    if not offers:
        return None
    return {"url": actual, "offers": sorted(offers)}


def published_offers(data_dir):
    stores = json.loads((data_dir / "retailer_locations.json").read_text())
    normalize_address = lambda value: re.sub(r"[^a-z0-9]", "", str(value or "").casefold())
    locations = defaultdict(set)
    for store in stores:
        address = normalize_address(store.get("address"))
        if address and store.get("id"):
            locations[address].add(store["id"])
    for source in SOURCES:
        for item in json.loads((data_dir / source).read_text()):
            store = item.get("store_id") or item.get("retailer_id")
            if not store:
                matches = locations[normalize_address(item.get("address"))]
                if len(matches) == 1:
                    store = next(iter(matches))
            title = item.get("raw_scanned_product_name") or item.get("product_name")
            product = product_key(item.get("url"), title)
            if item.get("id") and store and product:
                yield item["id"], (store, *product)


def scheduled_slot(scan_time):
    local = dt.datetime.fromisoformat(scan_time).astimezone(CENTRAL)
    if local.hour in (8, 20):
        return f"{local.date().isoformat()}T{local.hour:02d}"
    return ""


def advance(state, published, scan, candidates, count_misses):
    if scan.get("limited") or not scan.get("checked_at"):
        return state
    slot = scheduled_slot(scan["checked_at"]) if count_misses else ""
    new_slot = bool(slot and slot > state.get("last_counted_slot", ""))
    page_sizes = {}
    pages_by_offer = defaultdict(dict)
    seen = set()
    reachable = set()
    for status in scan["statuses"]:
        if status["connection"] != "reachable" or status.get("category"):
            continue
        store = status["license"]
        reachable.add(store)
        for page in status.get("menu_pages", []):
            offers = {tuple(offer) for offer in page["offers"]}
            if not offers:
                continue
            url, count = page["url"], len(offers)
            page_sizes[store, url] = count
            for offer in offers:
                key = (store, *offer)
                pages_by_offer[key][url] = count
                seen.add(key)

    for item in candidates:
        store = item.get("store_id")
        key = product_key(item.get("url"), item.get("product_name"))
        if store in reachable and key and item.get("checked_at") == scan["checked_at"]:
            seen.add((store, *key))

    tracked = {}
    for offer_id, key in published:
        previous = state.get("offers", {}).get(offer_id)
        if previous and tuple(previous["identity"]) != key:
            previous = None
        if key in seen:
            pages = pages_by_offer.get(key) or (previous["pages"] if previous else {})
            if pages:
                tracked[offer_id] = {"identity": list(key), "misses": 0, "pages": pages}
            continue
        if previous is None:
            continue
        # Require each previously observed page to load and return comparable
        # coverage. A sharp drop is inconclusive, even if some products parse.
        pages = previous["pages"]
        covered = pages and all(
            page_sizes.get((key[0], url), 0) >= max(1, (count * 7 + 9) // 10)
            for url, count in pages.items()
        )
        misses = min(MISS_LIMIT, previous["misses"] + int(new_slot and bool(covered)))
        tracked[offer_id] = {**previous, "misses": misses}

    return {"last_counted_slot": slot if new_slot else state.get("last_counted_slot", ""),
            "offers": tracked,
            "retired_ids": sorted(offer_id for offer_id, row in tracked.items() if row["misses"] >= MISS_LIMIT)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count-misses", action="store_true", help="Count a missing offer once per scheduled Central scan window.")
    args = parser.parse_args()
    destination = ROOT / "data" / "menu_miss_state.json"
    state = json.loads(destination.read_text()) if destination.exists() else {}
    staging = ROOT / "collector" / "data"
    scan = json.loads((staging / "latest_scan.json").read_text())
    candidates = json.loads((staging / "candidate_products.json").read_text())
    updated = advance(state, published_offers(destination.parent), scan, candidates, args.count_misses)
    destination.write_text(json.dumps(updated, sort_keys=True, separators=(",", ":")) + "\n")
    print(f"Tracked {len(updated['offers'])} offers, {len(updated['retired_ids'])} hidden after {MISS_LIMIT} misses.")


if __name__ == "__main__":
    main()
