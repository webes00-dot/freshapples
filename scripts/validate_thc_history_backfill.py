#!/usr/bin/env python3
"""Fail-closed validation of staged THC Minnesota historical observations.

Separate third-party historical observations from MNtrees first-party menu history.
Never publish a subset as statewide or category-wide historical medians.
"""
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

STAGED = Path("collector/data/thcminnesota-history-backfill/staged_observations.json")
REPORT = Path("collector/data/thcminnesota-history-backfill/validation.json")
CATEGORIES = {"Flower", "Pre-Rolls", "Concentrates"}
SLUGS = {"flower", "pre-rolls", "concentrates"}

def validate(staged):
    reasons = list(staged.get("blockers") or [])
    if staged.get("api_date_preflight") and not staged["api_date_preflight"].get("verified"):
        reasons.append("Historical source date-bound preflight failed; do not import any records")
    if staged.get("schema") != "mntrees-thc-history-stage-v1":
        reasons.append("Staging schema mismatch")
    audit = staged.get("categories") or {}
    if set(audit) != SLUGS:
        reasons.append("Missing required category audit")
    rows = staged.get("records") or []
    days = defaultdict(set)
    stores = defaultdict(set)
    seen = set()
    rejected = Counter()
    start = staged.get("window_start", "")
    end = staged.get("window_end", "")
    for row in rows:
        cat = row.get("category")
        day = row.get("observation_date", "")
        grams = row.get("package_g")
        price = row.get("package_price_usd")
        ppg = row.get("price_per_gram_usd")
        if cat not in CATEGORIES or not (start <= day <= end):
            rejected["category_or_date"] += 1
            continue
        try:
            date.fromisoformat(day)
            valid_numeric = (0 < float(grams) <= 112 and 0 < float(price) <= 20000
                             and abs(float(price)/float(grams) - float(ppg)) <= 0.001)
        except (ValueError, TypeError, ZeroDivisionError):
            valid_numeric = False
        if not valid_numeric:
            rejected["price_or_weight"] += 1
            continue
        item = (cat, day, row.get("source_record_id"), row.get("source_product_id"),
                row.get("source_store_id"), price)
        if item in seen:
            rejected["duplicate"] += 1
            continue
        seen.add(item)
        days[cat].add(day)
        if row.get("source_store_id"):
            stores[(cat, day)].add(str(row["source_store_id"]))
        else:
            rejected["missing_store_identity"] += 1
    if rejected:
        reasons.append("Invalid, duplicate or ungrounded rows: " + str(dict(rejected)))
    for slug in SLUGS:
        info = audit.get(slug, {})
        if not info.get("pages_complete"):
            reasons.append(f"{slug}: pagination incomplete; 20-page cap reached")
        if info.get("date_filter_mismatch_observed"):
            # Rows outside date range are excluded; this warning alone does not block if
            # complete pagination can still be independently established.
            reasons.append(f"{slug}: upstream date filter returned out-of-window observations")
        if info.get("category_mismatch", 0):
            reasons.append(f"{slug}: unexpected product categories received")
        if info.get("missing_weight", 0):
            reasons.append(f"{slug}: unweighted records prevent unbiased per-gram median")
        if info.get("missing_date", 0) or info.get("invalid_price", 0):
            reasons.append(f"{slug}: incomplete/invalid source records")
        category = {"flower": "Flower", "pre-rolls": "Pre-Rolls", "concentrates": "Concentrates"}[slug]
        if len(days[category]) < 30:
            reasons.append(f"{slug}: fewer than 30 dated observations; cannot establish 180-day trend")
    # At least one comparison date in each of the 30/90/180-day intervals.
    try:
        last = date.fromisoformat(end)
        for cat in CATEGORIES:
            for lower, upper in ((0, 30), (30, 90), (90, 180)):
                if not any(lower <= (last-date.fromisoformat(x)).days <= upper for x in days[cat]):
                    reasons.append(f"{cat}: no observations in {lower}-{upper} day segment")
    except ValueError:
        reasons.append("Invalid window end date")
    return {"publication_allowed": not reasons,
            "record_count": len(rows),
            "unique_days": {k: len(v) for k, v in sorted(days.items())},
            "minimum_distinct_stores_per_category_day": {
                cat: min((len(stores[(cat, day)]) for day in ds), default=0)
                for cat, ds in sorted(days.items())},
            "reject_counts": dict(rejected), "blockers": reasons,
            "destination": "HOLD: third-party history separate from first-party market-price-history.json"}

def main():
    if not STAGED.is_file():
        raise SystemExit("No staged backfill artifact; historical import cannot be validated")
    output = validate(json.loads(STAGED.read_text()))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))
    return 0 if output["publication_allowed"] else 1

if __name__ == "__main__":
    sys.exit(main())
