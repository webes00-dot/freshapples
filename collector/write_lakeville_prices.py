#!/usr/bin/env python3
"""Append verified Lakeville menu prices to the staging catalog."""

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

STORE = "DIS-L24-000396-01-AUR"
DATABASE = "457785f2-ab73-4858-b524-ba613a2b5388"
DATA = Path(__file__).resolve().parent / "data"

INSERT = """
WITH input AS (
    SELECT json_extract(value, '$.id') AS product_key,
           json_extract(value, '$.url') AS source_url,
           json_extract(value, '$.price_cents') AS price_cents,
           json_extract(value, '$.provenance') AS raw_json
    FROM json_each(?1)
)
INSERT INTO price_observations
    (product_key, retailer_key, observed_at, price_cents, source_url, raw_json)
SELECT i.product_key, r.source_key, ?3, i.price_cents, i.source_url, i.raw_json
FROM input i
JOIN products p ON p.source_key = i.product_key
JOIN retailers r ON r.id = p.retailer_id
WHERE r.source_key = ?2 AND r.license_id = ?2
  AND json_extract(p.raw_json, '$[8]') = i.source_url
  AND NOT EXISTS (
      SELECT 1 FROM price_observations o
      WHERE o.product_key = i.product_key AND o.retailer_key = r.source_key
        AND o.observed_at = ?3
  )
"""

VERIFY = """
SELECT count(*) AS verified
FROM price_observations o
JOIN json_each(?1) i ON o.product_key = json_extract(i.value, '$.id')
  AND o.source_url = json_extract(i.value, '$.url')
  AND o.price_cents = json_extract(i.value, '$.price_cents')
WHERE o.retailer_key = ?2 AND o.observed_at = ?3
"""


def candidate_rows(scan, offers, run_id):
    if scan["published"] is not False or not scan["reason"].startswith("read_only_staging"):
        raise ValueError("Expected a read-only collector artifact.")
    if any(conflict["new"]["store_id"] == STORE or conflict["old"]["store_id"] == STORE
           for conflict in scan["conflicts"]):
        raise ValueError("Lakeville has conflicting offers.")

    observed_at = datetime.fromisoformat(scan["checked_at"])
    if observed_at.tzinfo is None:
        raise ValueError("Scan timestamp is missing a time zone.")
    rows = {}
    for offer in offers:
        if offer["store_id"] != STORE or offer["price"] is None:
            continue
        price = Decimal(str(offer["price"])) * 100
        url = urlsplit(offer["url"])
        if (
            not re.fullmatch(r"[0-9a-f]{20}", offer["id"])
            or offer["checked_at"] != scan["checked_at"]
            or url.scheme != "https" or url.netloc != "shop.mnthc.co"
            or not url.path.startswith("/lakeville/products/")
            or not price.is_finite() or price <= 0 or price != price.to_integral_value()
        ):
            raise ValueError("Lakeville scan contains an invalid listing or price.")
        key = "scanner:" + offer["id"]
        if key in rows:
            raise ValueError("Lakeville candidate data contains a duplicate identity.")
        rows[key] = {
            "id": key,
            "url": offer["url"],
            "price_cents": int(price),
            "provenance": json.dumps({
                "source": "scanner",
                "workflow_run_id": run_id,
                "price_selection": offer["price_selection"],
            }),
        }
    if not rows:
        raise ValueError("No priced Lakeville listings were extracted.")
    return list(rows.values()), observed_at.astimezone(timezone.utc).isoformat()


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
        raise RuntimeError(f"Cloudflare staging D1 returned HTTP {exc.code}.") from None
    results = payload.get("result") or []
    if not payload.get("success") or not results or not results[0].get("success"):
        raise RuntimeError("Cloudflare staging D1 did not complete the query.")
    return results[0]


def main():
    scan = json.loads((DATA / "latest_scan.json").read_text())
    offers = json.loads((DATA / "candidate_products.json").read_text())
    rows, observed_at = candidate_rows(scan, offers, int(os.environ["GITHUB_RUN_ID"]))
    params = [json.dumps(rows), STORE, observed_at]
    inserted = query(INSERT, params)["meta"]["changes"]
    verified = query(VERIFY, params)["results"][0]["verified"]
    print(json.dumps({
        "retailer": STORE, "observed_at": observed_at, "candidates": len(rows),
        "inserted": inserted, "verified": verified, "unmatched": len(rows) - verified,
    }))
    if not 0 < verified <= len(rows):
        raise RuntimeError("Could not verify unique Lakeville observations in staging D1.")


if __name__ == "__main__":
    main()
