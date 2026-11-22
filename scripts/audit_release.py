#!/usr/bin/env python3
"""Deterministic source/mirror/public quality report for MNtrees.

Do not silently delete observations or invent cultivar identities to make this
report green. Incomplete editorial master synchronization is an explicit
exception, not a successful upsert.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from master_config import ROOT, authority, master_sheet_id

DIST = ROOT / "dist" / "data"
DATA = ROOT / "data"
REPORT = ROOT / "reports" / "release_quality.json"
PREFIX = re.compile(r"^(?:highnorth|rewind|trailhead|verist(?:\s+fields)?|mr\.?\s+birch)\s+", re.I)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def key(name):
    return re.sub(r"\s+", " ", str(name or "").strip()).casefold()


def main():
    cfg = authority()
    master = read(DATA / "strain_master.json")
    catalog = read(DIST / "catalog.json")
    site = read(DIST / "site-data.json")
    genes = read(DATA / "strain_genetics.json")
    brands = read(DATA / "brands.json")
    retailers = read(DATA / "retailer_locations.json")

    errors = []
    if master["source_spreadsheet_id"] != master_sheet_id():
        errors.append("GitHub strain master points to a different Google workbook")
    if site.get("catalog") != catalog:
        errors.append("Public site-data catalog diverged from the canonical builder")
    ids = [str(x.get("id") or "") for x in catalog]
    if any(not x for x in ids) or len(set(ids)) != len(ids):
        errors.append("Missing or duplicated offer source IDs in public catalog")
    bad_separator = [{"id":x.get("id"),"strain":x.get("strain")}
                     for x in catalog if "|" in str(x.get("strain") or "")
                     or "|" in str(x.get("master_strain") or "")]
    if bad_separator:
        errors.append("Pipe delimiter leaked into public strain identities")
    known = {key(n) for n in master["canonical_strains"]}
    genetics = {key(x.get("strain")) for x in genes}
    duplicates = [name for name,count in Counter(key(n) for n in master["canonical_strains"]).items() if count > 1]
    if duplicates:
        errors.append("Canonical strain names duplicated")
    bad_names = [
        {"id":x.get("id"),"strain":x.get("strain"),"brand":x.get("brand"),"retailer":x.get("retailer")}
        for x in catalog if PREFIX.match(str(x.get("strain") or "").strip())
    ]
    if bad_names:
        errors.append("Known brand/retailer/product-line prefix escaped into published strain headings")
    pending = [
        {"id":x.get("id"),"strain":x.get("strain"),"retailer":x.get("retailer"),
         "match_status":x.get("strain_match_status")}
        for x in catalog if key(x.get("strain")) not in known
    ]
    pending_without_marker = [
        x for x in pending if x["match_status"] != "pending_master_review"
    ]
    if pending_without_marker:
        errors.append("Unknown cultivar appears without pending-master-review status")
    brand_names = {key(x.get("name")) for x in brands}
    retailer_ids = {str(x.get("id")) for x in retailers}
    uncovered_brands = Counter(x.get("brand") for x in catalog if x.get("brand")
                               and key(x["brand"]) not in brand_names)
    unknown_retailer_ids = Counter(str(x.get("retailer_id")) for x in catalog
                                   if x.get("retailer_id") and str(x["retailer_id"]) not in retailer_ids)
    report = {
        "schema_version":1,
        "status":"pass" if not errors else "fail",
        "source_of_truth":cfg["spreadsheet"]["id"],
        "source_of_truth_tabs":cfg["spreadsheet"]["tabs"],
        "output_paths":cfg["outputs"],
        "metrics":{
            "published_offers":len(catalog),
            "canonical_strains":len(known),
            "genetics_records":len(genes),
            "brand_mirror_rows":len(brands),
            "retailer_mirror_locations":len(retailers),
            "pending_master_offers":len(pending),
            "master_strains_without_genetics":len(known-genetics),
            "genetics_without_master":len(genetics-known),
            "catalog_brand_prefix_cases":len(bad_names),
            "pipe_delimiter_cases":len(bad_separator),
            "catalog_brands_absent_from_github_brand_mirror":len(uncovered_brands),
            "catalog_retailer_ids_absent_from_github_location_mirror":len(unknown_retailer_ids)
        },
        "exceptions":{
            "brand_prefixed_strain_cards":bad_names[:75],
            "pending_master_offers":pending[:75],
            "master_strains_without_genetics":sorted(known-genetics)[:100],
            "genetics_without_master":sorted(genetics-known),
            "unmatched_catalog_brand_names":[{"brand":name,"offers":count} for name,count in uncovered_brands.most_common(100)],
            "unknown_catalog_retailer_ids":unknown_retailer_ids.most_common(100),
            "duplicate_canonical_names":duplicates,
            "unmarked_unknown_strains":pending_without_marker[:30],
            "delimiter_names":bad_separator[:30]
        },
        "publication_errors":errors,
        "not_proven":["Live Google Sheets row parity for all tabs", "Authenticated discovery-to-master writeback",
                      "Cloudflare deployment", "Producer-specific genetic identity when only a menu was available",
                      "Live stock or real-time price freshness"],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("MNtrees quality:",report["status"],json.dumps(report["metrics"],ensure_ascii=False))
    if errors:
        raise SystemExit("; ".join(errors))


if __name__ == "__main__":
    main()
