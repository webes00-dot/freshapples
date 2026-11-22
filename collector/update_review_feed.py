#!/usr/bin/env python3
"""Safely append scan-derived SKU candidates to the *review* feed.

No scan finding is a published/stock-verified offer. Failures never remove
previous review records; stable candidate IDs preserve browser decisions.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlsplit
from product_families import annotate

ROOT = Path(__file__).resolve().parents[1]

def source_key(row):
    store = str(row.get("store_id") or "").strip()
    url = str(row.get("url") or row.get("source_category_url") or "").split("?")[0].rstrip("/")
    name = str(row.get("product_name") or row.get("advertised_product_name") or "").strip().casefold()
    if not store or not url or not name:
        return None
    return store, url, name

def merge(existing, candidates, scan, readiness, catalog):
    if not isinstance(existing.get("candidates"), list) or not isinstance(candidates, list):
        raise ValueError("Malformed feed or scan")
    stamp = str(scan.get("checked_at") or "")
    if not stamp:
        raise ValueError("Missing scan timestamp")
    published = {source_key(x) for x in catalog if source_key(x)}
    existing_keys = {source_key(x) for x in existing["candidates"] if source_key(x)}
    additions = []
    decisions = {str(x.get("id")): x for x in readiness.get("records", [])}
    matched = 0
    added = 0
    for c in candidates:
        if c.get("checked_at") != stamp:
            continue
        key = source_key(c)
        if not key or key in existing_keys or key in published:
            continue
        url = str(c.get("url") or "")
        if urlsplit(url).scheme != "https" or "/products/" not in urlsplit(url).path:
            continue
        try:
            price = float(c.get("price"))
            if not math.isfinite(price) or price <= 0 or price >= 10000:
                continue
        except (TypeError, ValueError):
            continue
        gate = decisions.get(str(c.get("id")))
        if not gate:
            continue
        identity = hashlib.sha256("|".join(key).encode()).hexdigest()[:18]
        row = {
            "candidate_id": "scan-" + identity,
            "retailer": c.get("retailer", ""),
            "store_id": c.get("store_id", ""),
            "city": "",
            "state": "MN",
            "category": c.get("category") or "Unclassified",
            "advertised_product_name": c.get("product_name"),
            "advertised_brand": c.get("brand") or "",
            "strain": c.get("strain") or c.get("product_name"),
            "advertised_total_grams": str(c.get("package_g") or ""),
            "advertised_price_usd": round(price, 2),
            "menu_status": "advertised_not_stock_verified",
            "source_category_url": url,
            "observed_at": stamp,
            "record_status": "review_only_not_published",
            "review_reason": ", ".join(gate.get("reasons") or ["new_scan_candidate"]),
            "verification_status": gate.get("detail_status") or "unknown",
        }
        tagged = annotate({"strain": row["strain"], "brand": row["advertised_brand"]})
        row["product_family"] = tagged["product_family"]
        row["brand_family"] = tagged["brand_family"]
        additions.append(row)
        existing_keys.add(key)
        added += 1
    result = dict(existing)
    result["candidates"] = list(existing["candidates"]) + additions
    result["last_scan_reviewed_at"] = stamp
    result["disclaimer"] = "Editorial research candidates only; source pages and availability are not verified live stock. Review decisions never publish offers."
    return result, {"added": added, "total": len(result["candidates"]), "preserved": len(existing["candidates"]), "removed": 0}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--feed",type=Path,default=ROOT/"data/review_candidates.json")
    p.add_argument("--candidates",type=Path,default=ROOT/"collector/data/candidate_products.json")
    p.add_argument("--scan",type=Path,default=ROOT/"collector/data/latest_scan.json")
    p.add_argument("--gate",type=Path,default=ROOT/"collector/data/publication_readiness.json")
    p.add_argument("--catalog",type=Path,default=ROOT/"data/listings.json")
    p.add_argument("--report",type=Path,default=ROOT/"collector/data/review_feed_diff.json")
    a=p.parse_args()
    result,stats=merge(json.loads(a.feed.read_text()),json.loads(a.candidates.read_text()),
                        json.loads(a.scan.read_text()),json.loads(a.gate.read_text()),
                        json.loads(a.catalog.read_text()))
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(stats,indent=2)+"\n")
    if stats["added"]:
        a.feed.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(stats,indent=2))

if __name__=="__main__":
    main()
