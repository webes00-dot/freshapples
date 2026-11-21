#!/usr/bin/env python3
"""Scanner V2 validation/deduplication release gate. Read-only shadow output.

Deduplicate repeated evidence for the SAME source SKU, not offers that merely
share a strain, brand or retailer. Report all ambiguous identity collisions.
Never overwrite live site data or silently discard inconsistent records.
"""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
ACCEPTED = {"Flower", "Preroll", "Vape", "Concentrates"}


def stable_url(url):
    parts = urlsplit(str(url or ""))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(),
                       parts.path.rstrip("/"), "", ""))


def sku_key(row):
    """Source SKU or exact URL + variant, scoped to licensed storefront.

    Different source SKUs must not be merged just because product names match.
    A generic menu URL cannot be relied on for distinct SKU identity.
    """
    retailer = str(row.get("retailer_id") or "")
    provider_id = str(row.get("source_product_id") or "")
    variant = str(row.get("variant_key") or "")
    product_url = stable_url(row.get("product_url"))
    raw_title = str(row.get("raw_title") or "").casefold().strip()
    if provider_id:
        return (retailer, "provider", provider_id, variant)
    if "/product/" in product_url or "/products/" in product_url or "/pdp/" in product_url:
        return (retailer, "pdp", product_url, variant)
    # When we only captured a generic menu, preserve titles separately.
    return (retailer, "menu_card", product_url, raw_title, variant)


def issue(row):
    errors = []
    if row.get("identity_status") != "ready":
        errors.append("identity_pending_review")
    if not row.get("retailer_id") or not row.get("raw_title") or not row.get("product_url"):
        errors.append("missing_provenance")
    if row.get("category") not in ACCEPTED:
        errors.append("invalid_type")
    if not row.get("brand") or not row.get("strain"):
        errors.append("missing_brand_or_strain")
    try:
        weight = float(row.get("package_g"))
        if not 0 < weight <= 28:
            errors.append("invalid_package_g")
    except (ValueError, TypeError):
        errors.append("invalid_package_g")
    try:
        price = float(row.get("price"))
        if not 0 < price <= 10000:
            errors.append("invalid_price")
    except (ValueError, TypeError):
        errors.append("invalid_price")
    if row.get("stock_status") != "not_verified":
        errors.append("unverified_inventory_assertion")
    raw_name = str(row.get("strain") or "")
    # Physical weight tokens at the end cannot be canonical strain text.
    import re
    if re.search(r"\s+\d+(?:\.\d+)?\s*(?:g|gm|grams?)$", raw_name, re.I):
        errors.append("weight_in_strain_name")
    if "|" in raw_name:
        errors.append("delimiter_in_strain_name")
    return list(dict.fromkeys(errors))


def identity_signature(row):
    return tuple(str(row.get(x) or "") for x in (
        "brand", "strain", "category", "package_g", "pack_count",
        "variant_key", "source_product_id"))


def choose_source(rows):
    """Choose one duplicate observation only when identity/price agree.

    Prefer direct official source candidate, then latest timestamp. Identical
    supplier URL and offer data are duplicates, not distinct retailer SKUs.
    """
    return sorted(rows, key=lambda r: (
        r.get("source_kind") == "official_menu_candidate",
        str(r.get("observed_at") or ""),
        str(r.get("observation_id") or "")), reverse=True)[0]


def validate(rows):
    by_sku = defaultdict(list)
    holds = []
    reasons = Counter()
    for row in rows:
        errors = issue(row)
        if errors:
            holds.append({"observation_id": row.get("observation_id"),
                          "retailer_id": row.get("retailer_id"),
                          "reasons": errors})
            reasons.update(errors)
            continue
        by_sku[sku_key(row)].append(row)
    accepted = []
    suppressed = []
    for key, variants in sorted(by_sku.items(), key=lambda x: repr(x[0])):
        signatures = {identity_signature(x) for x in variants}
        prices = {float(x["price"]) for x in variants}
        if len(signatures) != 1 or len(prices) != 1:
            # Preserve all as review candidates, not silently choose a winner.
            holds.append({"sku_key": list(key),
                          "observation_ids": [x.get("observation_id") for x in variants],
                          "reasons": ["conflicting_sku_identity_or_price"]})
            reasons["conflicting_sku_identity_or_price"] += 1
            continue
        winner = choose_source(variants)
        accepted.append(winner)
        suppressed.extend(x.get("observation_id") for x in variants if x is not winner)
    return {"accepted": accepted, "holds": holds,
            "duplicates_suppressed": suppressed, "reasons": dict(reasons)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(ROOT / "reports/scanner_v2_reconciled.json"))
    parser.add_argument("--output", default=str(ROOT / "reports/scanner_v2_validated.json"))
    args = parser.parse_args()
    original = json.loads(Path(args.input).read_text(encoding="utf-8"))
    rows = original["rows"]
    result = validate(rows)
    result.update({"schema_version": 2,
                   "purpose": "validation_shadow_only_not_deployed",
                   "observations": len(rows),
                   "accepted_count": len(result["accepted"]),
                   "held_count": len(result["holds"]),
                   "deduplicated_count": len(result["duplicates_suppressed"])})
    assert (len(rows) == result["accepted_count"] + result["deduplicated_count"]
            + sum(len(h.get("observation_ids", [h.get("observation_id")])) for h in result["holds"])), (
            "V2 observation accounting mismatch")
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("accepted", "holds", "duplicates_suppressed")},
                     indent=2))


if __name__ == "__main__":
    main()
