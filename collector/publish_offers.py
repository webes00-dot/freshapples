#!/usr/bin/env python3
"""Persist public menu listings and dated prices in the catalog database."""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DATABASE = "457785f2-ab73-4858-b524-ba613a2b5388"
FIELDS = (
    "id", "retailer", "store_id", "product_name", "strain", "brand", "category",
    "package_g", "url", "source_id", "source_method", "weight_status",
    "price_selection", "checked_at",
)

UPSERT = """
INSERT INTO scanner_offers
    (offer_key, retailer_key, observed_at, price_cents, source_url, public_json)
SELECT 'scanner:' || json_extract(value, '$.id'),
       json_extract(value, '$.store_id'), json_extract(value, '$.checked_at'),
       json_extract(value, '$.price_cents'), json_extract(value, '$.url'), value
FROM json_each(?)
WHERE true
ON CONFLICT(offer_key) DO UPDATE SET
    observed_at = excluded.observed_at,
    price_cents = excluded.price_cents,
    source_url = excluded.source_url,
    public_json = excluded.public_json
WHERE excluded.observed_at > scanner_offers.observed_at
"""

HISTORY = """
INSERT INTO price_observations
    (product_key, retailer_key, observed_at, price_cents, source_url, raw_json)
SELECT o.offer_key, o.retailer_key, o.observed_at, o.price_cents, o.source_url,
       json_object('source', 'scanner', 'workflow_run_id', ?2)
FROM json_each(?1) j
JOIN scanner_offers o ON o.offer_key = 'scanner:' || json_extract(j.value, '$.id')
    AND o.observed_at = json_extract(j.value, '$.checked_at')
WHERE NOT EXISTS (
    SELECT 1 FROM price_observations p WHERE p.product_key = o.offer_key
    AND p.retailer_key = o.retailer_key AND p.observed_at = o.observed_at
)
"""


def publishable_rows(scan, offers):
    stores = {s["license"] for s in scan["statuses"] if s["connection"] == "reachable"}
    rows = {}
    for offer in offers:
        price = offer["price"]
        url = urlsplit(offer["url"])
        if (
            offer["store_id"] not in stores or not offer["id"] or not offer["product_name"]
            or offer["checked_at"] != scan["checked_at"]
            or not isinstance(price, (float, int)) or not 0 < price < 10000
            or url.scheme not in ("http", "https") or not url.hostname or url.username
        ):
            continue
        row = {key: offer.get(key) for key in FIELDS}
        row["price_cents"] = round(price * 100)
        rows.setdefault(row["id"], row)
    return list(rows.values())


def query(sql, params):
    account = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    token = os.environ["CLOUDFLARE_API_TOKEN"]
    if not account or not token:
        raise RuntimeError("Cloudflare credentials are missing.")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/d1/database/{DATABASE}/query"
    request = urllib.request.Request(
        url,
        data=json.dumps({"sql": sql, "params": params}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Cloudflare catalog D1 returned HTTP {exc.code}.") from None
    results = payload.get("result") or []
    if not payload.get("success") or not results or not results[0].get("success"):
        raise RuntimeError("Cloudflare catalog D1 did not complete the query.")
    return results[0]


def main():
    data = ROOT / "collector" / "data"
    scan = json.loads((data / "latest_scan.json").read_text())
    offers = json.loads((data / "candidate_products.json").read_text())
    rows = publishable_rows(scan, offers)
    if not rows:
        raise RuntimeError("The scan did not return any priced listings.")
    query((ROOT / "migrations" / "catalog_scanner.sql").read_text(), [])
    updated = recorded = 0
    for start in range(0, len(rows), 100):
        params = [json.dumps(rows[start:start + 100])]
        updated += query(UPSERT, params)["meta"]["changes"]
        recorded += query(HISTORY, [*params, int(os.environ["GITHUB_RUN_ID"])])["meta"]["changes"]
    print(json.dumps({
        "retailers_scanned": scan["targets_checked"],
        "retailers_with_offers": len({row["store_id"] for row in rows}),
        "priced_listings": len(rows), "listings_written": updated,
        "price_observations": recorded,
    }))


if __name__ == "__main__":
    main()
