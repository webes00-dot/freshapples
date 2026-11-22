#!/usr/bin/env python3
"""Stage THC Minnesota dated historical price samples; NEVER publish or merge with current menus.

This is a bounded API review. Per-day medians are deliberately NOT computed unless
pagination and every accepted weight/date can be verified independently.
"""
import json
import os
import re
import urllib.parse
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE = "https://thcminnesota.com/api/v1/pricing"
OUT = Path("collector/data/thcminnesota-history-backfill")
CATEGORY_NAMES = {"flower": "Flower", "pre-rolls": "Pre-Rolls", "concentrates": "Concentrates"}
MAX_PAGES = 20
PAGE_SIZE = 100
WEIGHT = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(g|gram|grams|oz|ounce|ounces)\s*$", re.I)

def package_grams(product, row):
    """Only structured product weights count; never guess from a product title."""
    grams = product.get("weight_grams")
    if grams is None:
        grams = row.get("weight_grams")
    if grams is not None:
        try:
            amount = float(grams)
            return amount if 0 < amount <= 112 else None
        except (TypeError, ValueError):
            return None
    label = product.get("weight_label") or row.get("weight_label")
    match = WEIGHT.fullmatch(str(label or ""))
    if not match:
        return None
    amount = float(match.group(1))
    if match.group(2).lower() in ("oz", "ounce", "ounces"):
        amount *= 28.349523125
    return amount if 0 < amount <= 112 else None

def fetch(token, params):
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token, "Accept": "application/json",
        "User-Agent": "MNtrees-History-Staging/1.0"})
    with urllib.request.urlopen(req, timeout=45) as response:
        raw = response.read(5_000_001)
    if len(raw) > 5_000_000:
        raise ValueError("API response exceeds 5 MB")
    return json.loads(raw)

def date_window_preflight(token, today):
    """Stop before bulk pagination if the provider ignores historical 'until'."""
    target = today - timedelta(days=90)
    low = (target - timedelta(days=3)).isoformat()
    high = (target + timedelta(days=3)).isoformat()
    response = fetch(token, {"since": low, "until": high,
                             "category": "flower", "limit": 25, "offset": 0})
    dates = [str(row.get("scrape_date", ""))[:10] for row in response.get("data", [])
             if isinstance(row, dict) and row.get("scrape_date")]
    return {"requested_since": low, "requested_until": high,
            "sample_size": len(dates),
            "sample_first_date": min(dates) if dates else None,
            "sample_last_date": max(dates) if dates else None,
            "verified": bool(dates) and all(low <= day <= high for day in dates)}


def stage(token, today=None):
    today = today or datetime.now(timezone.utc).date()
    start = today - timedelta(days=180)
    try:
        preflight = date_window_preflight(token, today)
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        preflight = {"verified": False, "error": type(exc).__name__,
                     "http_status": getattr(exc, "code", None)}
    if not preflight["verified"]:
        return {"schema": "mntrees-thc-history-stage-v1",
                "window_start": start.isoformat(), "window_end": today.isoformat(),
                "api_date_preflight": preflight,
                "categories": {slug: {"pages_complete": False, "received": 0}
                               for slug in CATEGORY_NAMES},
                "records": [], "publication_allowed": False,
                "blockers": ["Upstream historical date filter unavailable or returned out-of-window snapshots"],
                "warning": "Source cannot support verified dated per-gram backfill. No publication."}
    # The API's 'until' filter was previously observed failing; always enforce dates locally.
    records, audits = [], {}
    for slug, expected in CATEGORY_NAMES.items():
        counters = Counter()
        seen = set()
        reported_total = None
        completed = False
        date_filter_mismatch = False
        for page in range(MAX_PAGES):
            response = fetch(token, {"since": start.isoformat(), "until": today.isoformat(),
                                     "category": slug, "limit": PAGE_SIZE,
                                     "offset": page * PAGE_SIZE})
            rows = response.get("data")
            if not isinstance(rows, list):
                raise ValueError("Unexpected API response data")
            reported_total = response.get("total")
            counters["pages"] += 1
            for row in rows:
                counters["received"] += 1
                if not isinstance(row, dict):
                    counters["invalid_row"] += 1
                    continue
                product = row.get("products") or {}
                if not isinstance(product, dict):
                    counters["invalid_product"] += 1
                    continue
                actual_category = (product.get("categories") or {}).get("name")
                if actual_category != expected:
                    counters["category_mismatch"] += 1
                    continue
                raw_date = str(row.get("scrape_date") or "")
                try:
                    day = date.fromisoformat(raw_date[:10])
                except ValueError:
                    counters["missing_date"] += 1
                    continue
                if day < start or day > today:
                    counters["outside_window"] += 1
                    date_filter_mismatch = True
                    continue
                grams = package_grams(product, row)
                if grams is None:
                    counters["missing_weight"] += 1
                    continue
                try:
                    price = float(row.get("price"))
                except (ValueError, TypeError):
                    counters["invalid_price"] += 1
                    continue
                if not (0 < price <= 20000):
                    counters["invalid_price"] += 1
                    continue
                # Dedupe repeated API pages without incorrectly collapsing distinct SKUs.
                identity = (str(row.get("id") or ""), str(product.get("id") or ""),
                            str(row.get("dispensary_id") or ""), day.isoformat(), price)
                if not identity[0] and not identity[1]:
                    counters["missing_identity"] += 1
                    continue
                if identity in seen:
                    counters["duplicate"] += 1
                    continue
                seen.add(identity)
                records.append({"source": "THC Minnesota API", "observation_date": day.isoformat(),
                                "category": expected, "source_record_id": identity[0],
                                "source_product_id": identity[1], "source_store_id": identity[2],
                                "package_g": round(grams, 5), "package_price_usd": round(price, 2),
                                "price_per_gram_usd": round(price / grams, 4)})
                counters["accepted"] += 1
            if len(rows) < PAGE_SIZE:
                completed = True
                break
        audits[slug] = {**dict(counters), "reported_total": reported_total,
                        "pages_complete": completed,
                        "date_filter_mismatch_observed": date_filter_mismatch,
                        "publication_allowed": False}
    return {"schema": "mntrees-thc-history-stage-v1", "window_start": start.isoformat(),
            "window_end": today.isoformat(), "categories": audits,
            "records": records, "publication_allowed": False,
            "warning": "Staging sample only; incompletely paginated windows must not become market medians. Historical third-party prices are not current stock."}

def main():
    token = os.environ.get("THCMINNESOTA_API_KEY", "").strip()
    if not token:
        raise SystemExit("Missing THCMINNESOTA_API_KEY; no records imported.")
    result = stage(token)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "staged_observations.json").write_text(json.dumps(result, indent=2) + "\n")
    (OUT / "summary.json").write_text(json.dumps({k: v for k, v in result.items() if k != "records"}, indent=2) + "\n")
    print(json.dumps({"accepted": len(result["records"]), "categories": result["categories"],
                      "publication_allowed": False}, indent=2))

if __name__ == "__main__":
    main()
