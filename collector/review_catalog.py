#!/usr/bin/env python3
"""Produce a review-only diff between retailer candidates and last published catalog.

Never modifies data/listings.json; never treats failures/missing candidates as deletions.
"""
import argparse
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit

PROJECT = Path(__file__).resolve().parents[1]

def identity(row):
    """Only exact store+source matches are automatic; fuzzy matches need review."""
    store = str(row.get("store_id") or row.get("retailer") or "").strip().casefold()
    source_id = str(row.get("source_id") or "").strip()
    url = str(row.get("url") or "").strip().split("?")[0].rstrip("/")
    if store and source_id:
        return ("source", store, source_id)
    if store and "/products/" in urlsplit(url).path and url.startswith("https://"):
        return ("product_url", store, url)
    return None

def fingerprint(row):
    return (
        str(row.get("retailer") or "").casefold().strip(),
        str(row.get("strain") or "").casefold().strip(),
        str(row.get("brand") or "").casefold().strip(),
        str(row.get("category") or "").casefold().strip(),
        row.get("package_g"),
    )

def valid_candidate(row):
    errors = []
    for k in ("retailer", "store_id", "product_name", "strain", "brand", "category", "url", "checked_at"):
        if not str(row.get(k) or "").strip():
            errors.append("missing_" + k)
    try:
        price = float(row.get("price"))
        if not math.isfinite(price) or price <= 0 or price >= 10000:
            errors.append("invalid_price")
    except (ValueError, TypeError):
        errors.append("invalid_price")
    try:
        grams = float(row.get("package_g"))
        if not math.isfinite(grams) or grams <= 0 or grams > 112:
            errors.append("invalid_weight")
    except (ValueError, TypeError):
        errors.append("unverified_weight")
    u = urlsplit(str(row.get("url") or ""))
    if u.scheme != "https" or not u.hostname or "/products/" not in u.path:
        errors.append("not_direct_product_url")
    if row.get("stock_status") != "not_verified":
        errors.append("invalid_inventory_disclaimer")
    return errors

def compare(published, candidates, scan):
    published_by_id = {}
    for row in published:
        key = identity(row)
        if key:
            published_by_id[key] = row
    candidates_by_id = {}
    ambiguous = []
    for row in candidates:
        key = identity(row)
        if key is None:
            ambiguous.append({"record": row, "reasons": sorted(set(["no_strong_identity"] + valid_candidate(row)))})
        else:
            candidates_by_id.setdefault(key, []).append(row)
    review = {"scan_checked_at": scan.get("checked_at"), "published_records": len(published),
              "candidate_records": len(candidates), "addition_candidates": [],
              "price_change_candidates": [], "unchanged_candidates": [],
              "needs_review": ambiguous, "missing_not_removed": [],
              "auto_published": 0, "publish_approved": False}
    prior_fingerprints = {}
    for old in published:
        prior_fingerprints.setdefault(fingerprint(old), []).append(old)
    for key, matches in candidates_by_id.items():
        if len(matches) != 1:
            review["needs_review"].append({"records": matches, "reasons": ["duplicate_source_identity"]})
            continue
        row = matches[0]
        problems = valid_candidate(row)
        if problems:
            review["needs_review"].append({"record": row, "reasons": problems})
            continue
        old = published_by_id.get(key)
        if old:
            # Same product reference doesn't allow silently changing package/brand/category.
            altered = [k for k in ("strain", "brand", "category")
                       if str(row.get(k) or "").casefold().strip() != str(old.get(k) or "").casefold().strip()]
            try:
                same_weight = math.isclose(float(row.get("package_g")), float(old.get("package_g")), abs_tol=1e-9)
            except (TypeError, ValueError):
                same_weight = row.get("package_g") == old.get("package_g")
            if not same_weight:
                altered.append("package_g")
            # Retailer presentation labels may differ ("MN THC Co" vs "MN THC Co — Dundas").
            # A stable license/store ID is the stronger identity and prevents false conflicts.
            if not old.get("store_id") or not row.get("store_id"):
                if str(row.get("retailer") or "").casefold().strip() != str(old.get("retailer") or "").casefold().strip():
                    altered.append("retailer")
            if altered:
                review["needs_review"].append({"record": row, "published": old,
                                                "reasons": ["changed_" + k for k in altered]})
            elif float(old["price"]) != float(row["price"]):
                review["price_change_candidates"].append({"published": old, "candidate": row})
            else:
                review["unchanged_candidates"].append(row)
        elif prior_fingerprints.get(fingerprint(row)):
            review["needs_review"].append({"record": row, "possible_matches": prior_fingerprints[fingerprint(row)],
                                            "reasons": ["possible_existing_product_other_source"]})
        else:
            review["addition_candidates"].append(row)
    # Missing from a partial or unsuccessful scan is NEVER a removal signal.
    review["missing_not_removed"] = [{"id": x.get("id"), "retailer": x.get("retailer")} for x in published
                                      if identity(x) and identity(x) not in candidates_by_id]
    review["counts"] = {k: len(review[k]) for k in
                         ("addition_candidates", "price_change_candidates", "unchanged_candidates",
                          "needs_review", "missing_not_removed")}
    return review

def main():
    args = argparse.ArgumentParser()
    args.add_argument("--published", type=Path, default=PROJECT / "data/listings.json")
    args.add_argument("--candidates", type=Path, default=PROJECT / "collector/data/candidate_products.json")
    args.add_argument("--scan", type=Path, default=PROJECT / "collector/data/latest_scan.json")
    args.add_argument("--output", type=Path, default=PROJECT / "collector/data/catalog_review.json")
    options = args.parse_args()
    published = json.loads(options.published.read_text(encoding="utf-8"))
    candidates = json.loads(options.candidates.read_text(encoding="utf-8"))
    scan = json.loads(options.scan.read_text(encoding="utf-8"))
    if not isinstance(published, list) or not isinstance(candidates, list):
        raise SystemExit("Expected JSON arrays for published and candidate records")
    review = compare(published, candidates, scan)
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(review, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"review_counts": review["counts"], "auto_published": False, "review_file": str(options.output)}, indent=2))

if __name__ == "__main__":
    main()
