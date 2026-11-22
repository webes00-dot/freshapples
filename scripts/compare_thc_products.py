#!/usr/bin/env python3
"""Read-only comparison of THC Minnesota review candidates to MNtrees source offers.

No fuzzy strain assignment, no publication, and no mutation of editorial masters.
"""
import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "collector/data/thcminnesota-product-review/report.json"
OUT = ROOT / "collector/data/thcminnesota-product-review/comparison"
FEEDS = (
    "data/auto_menu_offers.json",
    "data/researched_menu_offers.json",
    "data/new_retailer_menu_offers.json",
    "data/listings.json",
)

def norm(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())

def identity(value):
    return (norm(value.get("retailer") or value.get("store")),
            norm(value.get("city")))

def read_feed(path):
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for field in ("offers", "listings", "data", "products"):
            if isinstance(data.get(field), list):
                return data[field]
    raise ValueError("Unrecognized offer feed: " + str(path))

def main():
    data = json.loads(SOURCE.read_text())
    candidates = data.get("candidates") or []
    offers = []
    for filename in FEEDS:
        offers.extend(read_feed(ROOT / filename))
    master = json.loads((ROOT / "data/retailer_locations.json").read_text())

    # Full location-level license identities only; a parent license is not a store.
    license_to_locations = {}
    name_to_locations = {}
    address_to_locations = {}
    for store in master:
        for lic in (store.get("id"), store.get("license_id")):
            if lic:
                license_to_locations.setdefault(str(lic).strip().upper(), set()).add(store["id"])
        name_to_locations.setdefault(norm(store.get("name")), set()).add(store["id"])
        if store.get("address"):
            address_to_locations.setdefault(norm(store["address"]), set()).add(store["id"])

    # Some existing observations identify the store by source ID and some by name.
    offer_by_id = {}
    offer_by_name = {}
    for offer in offers:
        rid = str(offer.get("retailer_id") or "").strip().upper()
        if rid:
            offer_by_id.setdefault(rid, []).append(offer)
        rname = norm(offer.get("retailer"))
        if rname:
            offer_by_name.setdefault(rname, []).append(offer)

    result = []
    metrics = Counter()
    for row in candidates:
        external_license = str(row.get("store_license") or "").strip().upper()
        external_name = norm(row.get("store"))
        ids = license_to_locations.get(external_license, set()) if external_license else set()
        if len(ids) == 1:
            store_id = next(iter(ids))
            store_name = next((x.get("name") for x in master if x.get("id") == store_id), "")
            match_basis = "exact_full_location_license"
        else:
            # Do not infer a store from a shared parent license or a fuzzy name.
            store_id = ""
            store_name = ""
            match_basis = "ambiguous_license" if ids else "unmatched_license"

        if not store_id and row.get("store_address"):
            # Strict full-address equivalence; conservative by design.
            address_ids = address_to_locations.get(norm(row["store_address"]), set())
            if len(address_ids) == 1:
                store_id = next(iter(address_ids))
                store_name = next((x.get("name") for x in master if x.get("id") == store_id), "")
                match_basis = "unique_exact_address"
            elif len(address_ids) > 1:
                match_basis = "ambiguous_address"
        if not store_id:
            name_ids = name_to_locations.get(external_name, set())
            if len(name_ids) == 1 and not ids and match_basis != "ambiguous_address":
                store_id = next(iter(name_ids))
                store_name = next((x.get("name") for x in master if x.get("id") == store_id), "")
                match_basis = "exact_name_only_requires_address_review"

        category = norm("Preroll" if row["category"] == "pre-rolls" else
                        "Concentrates" if row["category"] == "concentrates" else "Flower")
        if store_id and match_basis in ("exact_full_location_license", "unique_exact_address"):
            seen = offer_by_id.get(store_id.upper(), [])
            # Name fallback is only for offer feeds without location IDs.
            seen += [x for x in offer_by_name.get(norm(store_name), [])
                     if not x.get("retailer_id")]
        elif store_id:
            seen = []
        else:
            seen = []
        brand = norm(row.get("brand"))
        title = norm(row.get("raw_title"))
        same_brand = any(norm(o.get("brand")) == brand and
                         norm(o.get("category")) == category for o in seen)
        same_title = any(norm(o.get("brand")) == brand and
                         norm(o.get("product_name") or o.get("name")) == title and
                         norm(o.get("category")) == category for o in seen)
        if not store_id:
            status = "store_identity_unresolved"
        elif match_basis not in ("exact_full_location_license", "unique_exact_address"):
            status = "store_name_match_needs_review"
        elif same_title:
            status = "matching_raw_title_review_weight"
        elif same_brand:
            status = "known_store_brand_new_title_review"
        else:
            status = "new_store_brand_combo_review"
        metrics[(row["category"], status)] += 1
        result.append({**row, "comparison_status": status,
                       "matched_location_id": store_id,
                       "match_basis": match_basis,
                       "comparison_note": "Review only: product title, category, price, strain and grams require validation."})
    OUT.mkdir(parents=True, exist_ok=True)
    statuses = ("store_identity_unresolved", "store_name_match_needs_review",
                "matching_raw_title_review_weight", "known_store_brand_new_title_review",
                "new_store_brand_combo_review")
    summary = {"count": len(result), "by_category_and_status": {
        category: {status: metrics[(category, status)] for status in statuses}
        for category in ("flower", "pre-rolls", "concentrates")},
        "limitations": ["License matching requires the entire unique location-level ID",
                        "Name-only matches require independent address verification",
                        "Address matches require unique exact full address; spelling variants remain unresolved",
                        "Raw title matches are not verified duplicate SKUs",
                        "No assumed grams, strain, availability, or publication"]}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    with (OUT / "comparison.csv").open("w", newline="") as handle:
        fields = list(result[0]) if result else ["comparison_status"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(result)
    print(json.dumps(summary["by_category_and_status"], sort_keys=True))
    print("No public dataset changes.")


if __name__ == "__main__":
    main()
