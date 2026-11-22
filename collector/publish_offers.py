#!/usr/bin/env python3
"""Persist public menu listings and dated prices in the catalog database."""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://mntrees.co/api/internal/scanner-offers"
FIELDS = (
    "id", "retailer", "store_id", "product_name", "strain", "brand", "category",
    "package_g", "url", "source_id", "source_method", "weight_status",
    "price_selection", "checked_at",
)

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


def request_json(request, attempts=1):
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if attempt + 1 == attempts or error.code not in (404, 405, 429, 502, 503):
                host = urlsplit(request.full_url).hostname
                raise RuntimeError(f"{request.get_method()} {host} returned HTTP {error.code}.") from None
            time.sleep(5)


def workflow_token():
    url = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
    token = os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]
    query = urlencode({"audience": ENDPOINT})
    request = urllib.request.Request(
        url + ("&" if "?" in url else "?") + query,
        headers={"Authorization": f"Bearer {token}"},
    )
    return request_json(request)["value"]


def main():
    data = ROOT / "collector" / "data"
    scan = json.loads((data / "latest_scan.json").read_text())
    offers = json.loads((data / "candidate_products.json").read_text())
    rows = publishable_rows(scan, offers)
    if not rows:
        raise RuntimeError("The scan did not return any priced listings.")
    token = workflow_token()
    updated = recorded = 0
    for start in range(0, len(rows), 100):
        request = urllib.request.Request(
            ENDPOINT, data=json.dumps(rows[start:start + 100]).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        result = request_json(request, attempts=8)
        updated += result["listings_written"]
        recorded += result["price_observations"]
    print(json.dumps({
        "retailers_scanned": scan["targets_checked"],
        "retailers_with_offers": len({row["store_id"] for row in rows}),
        "priced_listings": len(rows), "listings_written": updated,
        "price_observations": recorded,
    }))


if __name__ == "__main__":
    main()
