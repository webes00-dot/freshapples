#!/usr/bin/env python3
"""Build a single validated public data snapshot from canonical build outputs.

Raw observations and approval records remain private, versioned build inputs.
Never use this artifact as the authority for corrections.
"""
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path("data")
DIST = Path("dist/data")
INPUTS = {
    "catalog": DIST / "catalog.json",
    "retailers": ROOT / "retailer_locations.json",
    "brands": ROOT / "brands.json",
    "business_tags": ROOT / "business_tags.json",
    "strain_types": ROOT / "strain_types.json",
    "strain_genetics": ROOT / "strain_genetics.json",
    "rcwm_strains": ROOT / "rcwm-strains.json",
    "manifest": ROOT / "manifest.json",
}
OUTPUT = DIST / "site-data.json"



# Research references and market offers have distinct evidence standards.
# Strain Master E is a Minnesota product URL; Strain Master R (and Genetics H)
# must be a cultivar research URL, never a copied dispensary/menu URL.
from master_config import master_sheet_id
CANONICAL_STRAIN_SHEET_ID = master_sheet_id()
MARKET_SOURCE_HOSTS = {
    "visitgreengoods.com", "risecannabis.com", "blainedispensary.com",
    "shop.minneorganix.com", "shop.mnthc.co", "thcminnesota.com",
}


def validate_cultivar_sources(strains):
    for record in strains:
        url = str(record.get("source_url") or "").strip()
        if not url:
            continue  # Unknown is honest; never fill from a retail product URL.
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().removeprefix("www.")
        path = parsed.path.lower()
        if parsed.scheme not in ("http", "https") or not host:
            raise ValueError("Invalid genetics research source URL: " + str(record.get("strain")))
        if (host.endswith(".dispensary.shop") or host in MARKET_SOURCE_HOSTS
                or (host == "leafly.com" and path.startswith(("/shop", "/dispensary-info")))
                or (host == "weedmaps.com" and path.startswith(("/brands", "/dispensaries", "/deliveries")))):
            raise ValueError("Retail market URL found in cultivar research source: " + str(record.get("strain")))



def entity_key(value):
    """Conservative label comparison; does not establish ownership or aliases."""
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def entity_reconciliation(payload):
    """Write a non-public audit of catalog identities versus local registry mirrors.

    This is deliberately NOT an automated Google Sheets upsert. A candidate
    discovered here needs a native Brand/Retailer Master row and stable identity.
    """
    from collections import Counter
    catalog = payload["catalog"]
    brand_rows = payload["brands"]
    retailer_rows = payload["retailers"]
    tag_rows = payload["business_tags"]
    known_brands = {}
    for item in brand_rows:
        for name in [item.get("name"), *(item.get("aliases") or [])]:
            if entity_key(name):
                known_brands.setdefault(entity_key(name), item.get("name"))
    known_retailers = {}
    for item in retailer_rows:
        for name in [item.get("name"), item.get("legal_name"), *(item.get("retailer_aliases") or [])]:
            if entity_key(name):
                known_retailers.setdefault(entity_key(name), set()).add(item.get("id"))
    brand_observations = Counter()
    retailer_observations = Counter()
    missing_retailer_ids = Counter()
    known_ids = {str(x.get("id")) for x in retailer_rows if x.get("id")}
    for item in catalog:
        brand = str(item.get("brand") or "").strip()
        if brand and entity_key(brand) not in {"unknown", "unconfirmed", "na", "brandnotconfirmed"}:
            brand_observations[brand] += 1
        rid = str(item.get("retailer_id") or "").strip()
        if rid and rid not in known_ids:
            missing_retailer_ids[rid] += 1
        retailer = str(item.get("retailer") or "").strip()
        if retailer:
            retailer_observations[retailer] += 1
    unmatched_brands = [
        {"observed_name": name, "offer_count": count, "status": "pending_master_reconciliation"}
        for name, count in sorted(brand_observations.items(), key=lambda x: x[0].casefold())
        if entity_key(name) not in known_brands
    ]
    unmatched_retailers = [
        {"observed_name": name, "offer_count": count, "status": "pending_master_reconciliation"}
        for name, count in sorted(retailer_observations.items(), key=lambda x: x[0].casefold())
        if entity_key(name) not in known_retailers
    ]
    brand_tag_names = {entity_key(x.get("name")) for x in tag_rows.get("brands", [])}
    retailer_tag_ids = {str(x.get("id")) for x in tag_rows.get("retailers", [])}
    overlapping_labels = sorted(
        [x.get("name") for x in brand_rows if entity_key(x.get("name")) in known_retailers],
        key=lambda x: str(x).casefold()
    )
    audit = {
        "schema_version": 1,
        "status": "audit_only_not_sheet_sync",
        "source": "versioned_repository_mirrors_not_live_google_sheet",
        "unmatched_brand_observations": unmatched_brands,
        "unmatched_retailer_name_observations": unmatched_retailers,
        "unknown_retailer_ids": dict(sorted(missing_retailer_ids.items())),
        "brands_missing_classification_record": sorted(
            [x.get("name") for x in brand_rows if entity_key(x.get("name")) not in brand_tag_names],
            key=lambda x: str(x).casefold()
        ),
        "retailer_ids_missing_classification_record": sorted(
            [x.get("id") for x in retailer_rows if x.get("id") and str(x.get("id")) not in retailer_tag_ids]
        ),
        "brand_retailer_name_overlap_candidates": overlapping_labels,
        "warnings": [
            "Name overlap is a candidate cross-link, never proof of common ownership.",
            "Known repository registries may not match Google Sheet master tabs.",
            "Successful publication does not mean all candidates were written to masters."
        ]
    }
    report = Path("reports/entity_reconciliation.json")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Entity reconciliation audit:", len(unmatched_brands), "unmatched brand names,",
          len(unmatched_retailers), "unmatched retailer labels,",
          len(missing_retailer_ids), "unknown retailer IDs")
    return audit


def build():
    payload = {"schema_version": 1}
    for key, filename in INPUTS.items():
        payload[key] = json.loads(filename.read_text(encoding="utf-8"))
    if not isinstance(payload["catalog"], list) or len(payload["catalog"]) < 1000:
        raise ValueError("Refusing to publish an empty or regressed catalog")
    if not isinstance(payload["retailers"], list) or len(payload["retailers"]) < 110:
        raise ValueError("Refusing to publish an incomplete retailer registry")
    if not isinstance(payload["brands"], list) or not payload["brands"]:
        raise ValueError("Missing brand directory")
    if not isinstance(payload["strain_genetics"], list):
        raise ValueError("Invalid strain genetics")
    validate_cultivar_sources(payload["strain_genetics"])
    master = json.loads((ROOT / "strain_master.json").read_text(encoding="utf-8"))
    if master.get("source_spreadsheet_id") != CANONICAL_STRAIN_SHEET_ID:
        raise ValueError("Strain master points to a retired or unapproved workbook")
    if not isinstance(payload["strain_types"], dict):
        raise ValueError("Invalid strain types")
    if not isinstance(payload["rcwm_strains"], dict):
        raise ValueError("Invalid RCWM strains")
    if not isinstance(payload["business_tags"], dict):
        raise ValueError("Invalid business tags")
    if not isinstance(payload["manifest"], dict):
        raise ValueError("Invalid manifest")
    entity_reconciliation(payload)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print("Unified site data:", len(payload["catalog"]), "offers,",
          len(payload["retailers"]), "retailers,", len(payload["brands"]), "brands")
    return payload


if __name__ == "__main__":
    build()
