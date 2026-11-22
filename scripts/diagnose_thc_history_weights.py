#!/usr/bin/env python3
"""Bounded read-only THC Minnesota price schema/weight diagnostic.

No product prices, retailer identities, or API keys are exported.
"""
import json
import os
import urllib.request
import urllib.error
import time
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from stage_thc_history_backfill import fetch, CATEGORY_NAMES

OUT = Path("collector/data/thcminnesota-weight-diagnostic")
WEIGHT_WORDS = ("weight", "gram", "size", "unit", "qty", "quantity", "amount", "volume", "pack")

def safe_fetch(token, params):
    for attempt in range(3):
        try:
            return fetch(token, params)
        except urllib.error.HTTPError as exc:
            if exc.code not in (500, 502, 503, 504) or attempt == 2:
                raise
            time.sleep(2 ** attempt)


def diagnostic(token):
    result = {"checked_at": datetime.now(timezone.utc).isoformat(),
              "publication_allowed": False, "categories": {}}
    for slug in CATEGORY_NAMES:
        raw = safe_fetch(token, {"category": slug, "limit": 100, "offset": 0})
        rows = raw.get("data") or []
        row_keys, product_keys, values, titles = Counter(), Counter(), {}, []
        date_values = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_keys.update(row.keys())
            product = row.get("products") or {}
            if not isinstance(product, dict):
                continue
            product_keys.update(product.keys())
            if row.get("scrape_date"):
                date_values.append(str(row["scrape_date"])[:10])
            if len(titles) < 12 and product.get("name"):
                titles.append(str(product["name"])[:120])
            for parent, data in (("row", row), ("product", product)):
                for key, val in data.items():
                    if any(word in key.lower() for word in WEIGHT_WORDS):
                        field = parent + "." + key
                        entry = values.setdefault(field, {"nonnull_count": 0, "examples": []})
                        if val not in (None, ""):
                            entry["nonnull_count"] += 1
                            if len(entry["examples"]) < 6 and str(val) not in entry["examples"]:
                                entry["examples"].append(str(val)[:100])
        result["categories"][slug] = {
            "returned": len(rows), "reported_total": raw.get("total"),
            "earliest_sample_date": min(date_values) if date_values else None,
            "latest_sample_date": max(date_values) if date_values else None,
            "row_keys": dict(row_keys), "product_keys": dict(product_keys),
            "weight_related_fields": values, "sample_product_names": titles,
        }
    # Full product endpoint may expose dimensions omitted by nested price records.
    req = urllib.request.Request("https://thcminnesota.com/api/v1/products?limit=100",
                                 headers={"Authorization": "Bearer " + token,
                                          "Accept": "application/json",
                                          "User-Agent": "MNtrees-Weight-Schema-Review/1.0"})
    with urllib.request.urlopen(req, timeout=45) as response:
        product_payload = json.loads(response.read(5_000_001))
    product_rows = product_payload.get("data") or []
    keys, weight_fields, sample_names = Counter(), {}, []
    def visit(value, prefix="", depth=0):
        if depth > 3 or not isinstance(value, dict):
            return
        for key, item in value.items():
            name = prefix + str(key)
            if any(word in str(key).lower() for word in WEIGHT_WORDS):
                record = weight_fields.setdefault(name, {"nonnull_count": 0, "examples": []})
                if item not in (None, ""):
                    record["nonnull_count"] += 1
                    value_text = str(item)[:100]
                    if value_text not in record["examples"] and len(record["examples"]) < 6:
                        record["examples"].append(value_text)
            if isinstance(item, dict):
                visit(item, name + ".", depth + 1)
    for product in product_rows:
        if not isinstance(product, dict):
            continue
        keys.update(product.keys())
        visit(product)
        if len(sample_names) < 8 and product.get("name"):
            sample_names.append(str(product["name"])[:120])
    result["product_endpoint"] = {"returned": len(product_rows), "total": product_payload.get("total"),
                                  "keys": dict(keys), "weight_related_fields": weight_fields,
                                  "sample_names": sample_names}
    # Confirm whether the remote API actually honors historical date bounds.
    bounds = []
    now = datetime.now(timezone.utc).date()
    for days in (30, 90, 180):
        low = (now - timedelta(days=days + 3)).isoformat()
        high = (now - timedelta(days=days - 3)).isoformat()
        try:
            response = safe_fetch(token, {"since": low, "until": high, "category": "flower",
                                          "limit": 100, "offset": 0})
            dates = [str(r.get("scrape_date", ""))[:10] for r in response.get("data", [])
                     if isinstance(r, dict) and r.get("scrape_date")]
            bounds.append({"requested_since": low, "requested_until": high,
                           "reported_total": response.get("total"),
                           "rows": len(dates), "min_date": min(dates) if dates else None,
                           "max_date": max(dates) if dates else None,
                           "all_within_range": bool(dates) and all(low <= d <= high for d in dates)})
        except urllib.error.HTTPError as exc:
            bounds.append({"requested_since": low, "requested_until": high,
                           "error": "HTTP_" + str(exc.code), "all_within_range": False})
    result["date_filter_probe"] = bounds
    return result

def main():
    token = os.environ.get("THCMINNESOTA_API_KEY", "").strip()
    if not token:
        raise SystemExit("THCMINNESOTA_API_KEY is unavailable")
    data = diagnostic(token)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "weight_schema.json").write_text(json.dumps(data, indent=2) + "\n")
    for slug, info in data["categories"].items():
        print(slug, "sample", info["returned"], "weight-related fields", info["weight_related_fields"],
              "product keys", list(info["product_keys"]))
    print("product endpoint", data["product_endpoint"])
    print("date filter probe", data["date_filter_probe"])
    print("Diagnostic only. No prices published.")

if __name__ == "__main__":
    main()
