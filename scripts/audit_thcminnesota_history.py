#!/usr/bin/env python3
"""Read-only historical coverage audit for THC Minnesota.

Do not treat aggregate package-price trends as per-gram values.
No consumer publication and no repository data modifications.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = "https://thcminnesota.com"
OUT = Path("collector/data/thcminnesota-history-audit")
CATEGORIES = {"flower": "Flower", "pre-rolls": "Pre-Rolls", "concentrates": "Concentrates"}


def get_json(token, endpoint, params):
    url = BASE + endpoint + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "User-Agent": "MNtrees-History-Coverage-Review/1.0",
    })
    with urllib.request.urlopen(request, timeout=45) as response:
        raw = response.read(5_000_001)
        if len(raw) > 5_000_000:
            raise ValueError("Response exceeded 5 MB safety bound")
        return json.loads(raw)


def report_rows(data):
    rows = data.get("data", [])
    dates = sorted({str(r.get("scrape_date", "")) for r in rows
                    if isinstance(r, dict) and r.get("scrape_date")})
    categories = Counter()
    with_weight = 0
    for row in rows:
        product = row.get("products") or {}
        category = (product.get("categories") or {}).get("name") or "Unknown"
        categories[category] += 1
        if product.get("weight_label"):
            with_weight += 1
    field_counts = Counter()
    product_fields = Counter()
    product_sample_values = {}
    for row in rows:
        product = row.get("products") or {}
        if not isinstance(product, dict):
            continue
        product_fields.update(product.keys())
        for key in ("weight_grams", "weight_label", "name", "category_id"):
            val = product.get(key)
            if val is not None and key not in product_sample_values:
                product_sample_values[key] = str(val)[:80]
    unit_counts = Counter()
    sample_values = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        field_counts.update(row.keys())
        for key in ("price", "price_per_gram", "weight_grams", "weight_label", "scrape_date", "scraped_at"):
            val = row.get(key)
            if val is not None:
                unit_counts[key] += 1
                if key not in sample_values:
                    sample_values[key] = str(val)[:80]
    return {
        "sample_product_fields": dict(product_fields),
        "sample_product_values": product_sample_values,
        "sample_fields": dict(field_counts),
        "sample_nonnull_key_counts": dict(unit_counts),
        "sample_key_values": sample_values,
        "reported_total": data.get("total"),
        "sample_size": len(rows),
        "sample_earliest_date": dates[0] if dates else None,
        "sample_latest_date": dates[-1] if dates else None,
        "sample_categories": dict(categories),
        "sample_with_weight_field": with_weight,
    }


def main():
    token = os.getenv("THCMINNESOTA_API_KEY", "").strip()
    if not token:
        raise SystemExit("Missing THCMINNESOTA_API_KEY; no requests made")
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    report = {"checked_at": now.isoformat(), "sample_limit": 100, "allowed_categories": CATEGORIES, "windows": {}}
    failures = 0
    for days in (30, 90, 180):
        since = (now - timedelta(days=days)).date().isoformat()
        section = {"requested_since": since}
        section["pricing_by_category"] = {}
        section["date_window_filter"] = {}
        start = (now - timedelta(days=days + 3)).date().isoformat()
        end = (now - timedelta(days=max(0, days - 3))).date().isoformat()
        for slug, expected_name in CATEGORIES.items():
            try:
                bounded = get_json(token, "/api/v1/pricing", {
                    "since": start, "until": end, "category": slug,
                    "limit": 100, "offset": 0
                })
                bounded_stats = report_rows(bounded)
                dates = [v for v in (bounded_stats["sample_earliest_date"],
                                      bounded_stats["sample_latest_date"]) if v]
                section["date_window_filter"][slug] = {
                    "requested_from": start, "requested_until": end,
                    "reported_total": bounded_stats["reported_total"],
                    "sample_earliest_date": bounded_stats["sample_earliest_date"],
                    "sample_latest_date": bounded_stats["sample_latest_date"],
                    "sample_all_within_requested_window": bool(dates) and all(start <= v <= end for v in dates)
                }
            except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
                section["date_window_filter"][slug] = {"error": type(exc).__name__}
        for slug, expected_name in CATEGORIES.items():
            try:
                data = get_json(token, "/api/v1/pricing",
                                {"since": since, "category": slug, "limit": 100, "offset": 0})
                details = report_rows(data)
                other = {name: count for name, count in details["sample_categories"].items()
                         if name != expected_name}
                details["category_filter_verified_on_sample"] = not other and details["sample_size"] > 0
                details["unexpected_categories"] = other
                details["count_is_usable"] = details["category_filter_verified_on_sample"]
                section["pricing_by_category"][slug] = details
                if other:
                    failures += 1
                    print("WARNING: API category filter returned mismatched rows", slug, other)
            except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
                failures += 1
                section["pricing_by_category"][slug] = {"error": type(exc).__name__}
        try:
            trend = get_json(token, "/api/v1/pricing/trends", {"since": since})
            points = trend.get("data", [])
            dates = sorted(str(x["date"]) for x in points if isinstance(x, dict) and x.get("date"))
            section["trends"] = {
                "returned_days": len(dates),
                "earliest": dates[0] if dates else None,
                "latest": dates[-1] if dates else None,
                "advertised_days": trend.get("days"),
                "field_names": sorted(set().union(*(set(x) for x in points if isinstance(x, dict)))),
                "sample_point": points[0] if points and isinstance(points[0], dict) else None,
                "unit": "UNKNOWN: never assume USD per gram",
                "scope": "Unfiltered trends; never publish as category prices",
            }
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
            failures += 1
            section["trends_error"] = type(exc).__name__
        report["windows"][str(days)] = section
        print("Window", days, json.dumps(section, sort_keys=True))
    bounded = [value for section in report["windows"].values()
               for value in section.get("date_window_filter", {}).values()]
    samples = [value for section in report["windows"].values()
               for value in section.get("pricing_by_category", {}).values()]
    all_dates_verified = bool(bounded) and all(
        value.get("sample_all_within_requested_window") is True for value in bounded)
    all_weights_verified = bool(samples) and all(
        value.get("sample_with_weight_field", 0) > 0 or
        value.get("sample_product_values", {}).get("weight_grams") is not None
        for value in samples)
    report["publication_readiness"] = {
        "api_authentication": "verified",
        "per_gram_history_import_allowed": bool(all_dates_verified and all_weights_verified),
        "historical_until_filter_verified": all_dates_verified,
        "package_weight_verified": all_weights_verified,
        "blockers": [
            reason for failed, reason in (
                (not all_dates_verified, "Historical until-date filter did not constrain returned snapshots"),
                (not all_weights_verified, "Snapshot products lack confirmed package weight metadata")
            ) if failed
        ]
    }
    print("PUBLICATION READINESS:", json.dumps(report["publication_readiness"], sort_keys=True))
    (OUT / "coverage.json").write_text(json.dumps(report, indent=2) + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
