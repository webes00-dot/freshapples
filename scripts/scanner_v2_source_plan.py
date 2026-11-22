#!/usr/bin/env python3
"""Scanner V2 first-party-first URL planning. No network requests, no publishing.

Treat known shop URLs as *candidates*, not proven first-party product evidence.
Only explicit source-domain evidence can elevate a secondary link to official.
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from scanner_v2_master import load_snapshot

ROOT = Path(__file__).resolve().parents[1]
SECONDARY = (
    "leafly.com", "weedmaps.com", "jointcommerce.com",
    "twincitycannabis.com", "mncannabishub.com", "thcminnesota.com",
)
NONSHOP = ("google.com", "maps.google.com", "facebook.com", "instagram.com")
MENU_TERMS = ("/shop", "/menu", "/store", "/rec/", "/products", "/dispensary/")
PROVIDERS = ("dispensary.shop", "dutchie.com", "iheartjane.com", "tymber.io")

def hostname(value):
    try:
        p = urlsplit(str(value or "").strip())
        if p.scheme not in ("https", "http") or p.username or p.password:
            return ""
        return (p.hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""

def is_domain(host, domain):
    return host == domain or host.endswith("." + domain)

def source_class(url):
    host = hostname(url)
    if not host:
        return "missing"
    if any(is_domain(host, x) for x in SECONDARY):
        return "secondary"
    if any(is_domain(host, x) for x in NONSHOP):
        return "directory_or_social"
    if any(is_domain(host, x) for x in PROVIDERS):
        return "commerce_provider_candidate"
    return "retailer_or_brand_domain_candidate"

def discover_plan(stores):
    output = []
    for x in stores:
        rid = str(x.get("id") or x.get("license_id") or "").strip()
        if not rid:
            continue
        name = x.get("name") or x.get("legal_name") or rid
        shop = str(x.get("menu_url") or "").strip()
        site = str(x.get("website_url") or "").strip()
        fallback = str(x.get("fallback_menu_url") or "").strip()
        shop_class = source_class(shop)
        website_class = source_class(site)
        official_candidates = []
        secondary_candidates = []
        if shop_class not in ("missing", "secondary", "directory_or_social"):
            official_candidates.append({"url": shop, "origin": "retailer_master_menu",
                                        "verification": "needs_store_association_check"})
        elif shop_class == "secondary":
            secondary_candidates.append({"url": shop, "origin": "retailer_master_menu"})
        if website_class not in ("missing", "secondary", "directory_or_social"):
            if not any(item["url"] == site for item in official_candidates):
                official_candidates.append({"url": site, "origin": "retailer_master_website",
                                            "verification": "needs_official_shop_discovery"})
        elif website_class == "secondary":
            secondary_candidates.append({"url": site, "origin": "retailer_master_website"})
        if (source_class(fallback) not in ("missing", "directory_or_social")
                and fallback not in {item["url"] for item in official_candidates}):
            secondary_candidates = [item for item in secondary_candidates if item["url"] != fallback]
            secondary_candidates.append({"url": fallback, "origin": "retailer_master_fallback"})
        if official_candidates:
            next_step = "verify_first_party_menu_and_extract"
        else:
            next_step = "discover_official_website_and_shop"
        output.append({
            "retailer_id": rid, "retailer": name,
            "menu_platform": x.get("menu_platform", ""),
            "platform_location_id": x.get("platform_location_id", ""),
            "shop_source_type": shop_class,
            "website_source_type": website_class,
            "first_party_candidates": official_candidates,
            "secondary_candidates": secondary_candidates,
            "next_step": next_step,
            "fallback_policy": "Use attributed secondary evidence only after official-source search fails",
            "source_status": "planned_not_scanned",
        })
    return output

def main():
    ap = argparse.ArgumentParser()
    source = ap.add_mutually_exclusive_group()
    source.add_argument("--retailers", type=Path, default=ROOT / "data/retailer_locations.json")
    source.add_argument("--master-snapshot", type=Path)
    ap.add_argument("--output", default=str(ROOT / "reports/scanner_v2_source_plan.json"))
    args = ap.parse_args()
    stores = (load_snapshot(args.master_snapshot)["retailers"] if args.master_snapshot
              else json.loads(args.retailers.read_text(encoding="utf-8")))
    plan = discover_plan(stores)
    if len(plan) != len({p["retailer_id"] for p in plan}):
        raise ValueError("Duplicate retailer/location ID in V2 source registry")
    counts = Counter(p["next_step"] for p in plan)
    output = {"schema_version": 2, "status": "source_candidates_not_verified",
              "retailers_total": len(plan), "counts": dict(counts),
              "retailers": plan}
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"retailers": len(plan), "status": output["status"], "counts": dict(counts)}))

if __name__ == "__main__":
    main()
