#!/usr/bin/env python3
"""Read-only deployment smoke check. Does not edit the website or product data."""
import json
import os
import sys
from pathlib import Path
import urllib.error
import urllib.request

BASE = os.getenv("MNTREES_PREVIEW_URL", "https://mntrees.shawn-18c.workers.dev").rstrip("/")
USER_AGENT = "MNtrees-healthcheck/1.0"

def request(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.status, response.headers.get("Content-Type", ""), response.read(4_000_000)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{path} returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{path} could not be reached: {exc.reason}") from exc

def main():
    print("Checking", BASE)
    status, ctype, page = request("/")
    if status != 200 or "text/html" not in ctype.lower():
        raise RuntimeError(f"Website returned HTTP {status}, content type {ctype!r}")
    html = page.decode("utf-8", "replace")
    if "MNtrees" not in html and "mntrees" not in html.lower():
        raise RuntimeError("Website response does not contain MNtrees branding")
    if "app.js" not in html:
        raise RuntimeError("Website response is missing app.js reference")
    status, ctype, raw = request("/data/listings.json")
    if status != 200:
        raise RuntimeError(f"Catalog returned HTTP {status}")
    try:
        products = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Catalog response is not valid JSON") from exc
    if not isinstance(products, list):
        raise RuntimeError("Catalog must be a JSON list")
    expected = json.loads((Path(__file__).resolve().parents[1] / "data/listings.json").read_text(encoding="utf-8"))
    if len(products) != len(expected):
        raise RuntimeError(f"Live catalog has {len(products)} offers, but GitHub has {len(expected)}. Deployment is stale or not connected.")
    expected_ids = {str(x.get("id")) for x in expected}
    live_ids = {str(x.get("id")) for x in products}
    if live_ids != expected_ids:
        raise RuntimeError("Live catalog product IDs differ from the current GitHub release")
    # Matching IDs alone is insufficient: name, brand, classification and price
    # can remain stale in Cloudflare even when the same source IDs were uploaded.
    def listing_identity(item):
        fields = ("strain", "brand", "category", "package_g", "price", "retailer", "product_family")
        return {key: item.get(key) for key in fields}
    live_by_id = {str(x.get("id")): x for x in products}
    expected_by_id = {str(x.get("id")): x for x in expected}
    stale = [source_id for source_id in expected_ids
             if listing_identity(live_by_id[source_id]) != listing_identity(expected_by_id[source_id])]
    if stale:
        raise RuntimeError(f"Live listings contain {len(stale)} stale product identities/prices (sample IDs: {', '.join(sorted(stale)[:8])})")
    if any(not x.get("retailer") or not x.get("strain") or float(x.get("price") or 0) <= 0 for x in products):
        raise RuntimeError("At least one catalog offer lacks a valid retailer, strain or price")
    status, ctype, manifest_bytes = request("/data/manifest.json")
    manifest = json.loads(manifest_bytes)
    if manifest.get("listings") != len(expected):
        raise RuntimeError("Live manifest count does not match GitHub catalog")
    status, ctype, review_raw = request("/data/review_candidates.json")
    review = json.loads(review_raw)
    expected_review = json.loads((Path(__file__).resolve().parents[1] / "data/review_candidates.json").read_text(encoding="utf-8"))
    if not isinstance(review.get("candidates"), list) or len(review["candidates"]) != len(expected_review["candidates"]):
        raise RuntimeError("Live editorial review feed count differs from GitHub")
    live_review_ids = {x.get("candidate_id") for x in review["candidates"]}
    expected_review_ids = {x.get("candidate_id") for x in expected_review["candidates"]}
    if live_review_ids != expected_review_ids or None in live_review_ids:
        raise RuntimeError("Live editorial review candidate IDs differ from GitHub")
    built_catalog = Path(__file__).resolve().parents[1] / "dist/data/catalog.json"
    if built_catalog.exists():
        expected_unified = json.loads(built_catalog.read_text(encoding="utf-8"))
        _, _, live_unified = request("/data/catalog.json")
        live_catalog = json.loads(live_unified)
        if {str(x["id"]) for x in live_catalog} != {str(x["id"]) for x in expected_unified}:
            raise RuntimeError("Live unified catalog IDs do not match the built catalog")
        if {str(x["id"]): listing_identity(x) for x in live_catalog} != {str(x["id"]): listing_identity(x) for x in expected_unified}:
            raise RuntimeError("Live unified catalog identities, brands, categories, weights or prices differ from the built catalog")
    # Verify actual badge and cultivation data, not just an unchanged catalog JS asset.
    # A successful code deploy with stale site-data.json must fail this smoke test.
    _, _, live_site_raw = request("/data/site-data.json")
    live_site = json.loads(live_site_raw)
    source = Path(__file__).resolve().parents[1] / "data"
    expected_tags = json.loads((source / "business_tags.json").read_text(encoding="utf-8"))
    live_tags = live_site.get("business_tags", {})
    if live_tags != expected_tags:
        raise RuntimeError("Live SEA/Tribal/Corporate badges differ from canonical GitHub tag data")
    expected_brands = json.loads((source / "brands.json").read_text(encoding="utf-8"))
    if live_site.get("brands") != expected_brands:
        raise RuntimeError("Live brand cultivation or directory data differs from GitHub")
    if sum("SEA" in x.get("verified_tags", []) for x in live_tags.get("retailers", [])) < 25:
        raise RuntimeError("Live retailer site-data does not publish the 25 SEA-positive records")
    if sum("SEA" in x.get("verified_tags", []) for x in live_tags.get("brands", [])) < 17:
        raise RuntimeError("Live brand site-data does not publish the 17 SEA-positive rows")
    for filename in ("retailers.js", "brands.js"):
        _, _, live_js = request("/" + filename)
        if live_js != (Path(__file__).resolve().parents[1] / filename).read_bytes():
            raise RuntimeError("Live " + filename + " differs from GitHub release")
    status, ctype, js = request("/app.js")
    if status != 200 or len(js) < 100:
        raise RuntimeError("app.js is missing")
    if "catalog-model.js" not in html:
        raise RuntimeError("Live HTML does not load strain/type/size/brand normalization")
    status, ctype, catalog_js = request("/catalog-model.js")
    if status != 200 or b"Float Cannabis" not in catalog_js or b"Dizgo Collective" not in catalog_js:
        raise RuntimeError("Live catalog model is missing or stale")
    local_catalog_js = (Path(__file__).resolve().parents[1] / "catalog-model.js").read_bytes()
    if catalog_js != local_catalog_js:
        raise RuntimeError("Live catalog-model.js differs from the GitHub release")
    if b"renderComparisons" not in js or b"catalog.groupOffers" not in js:
        raise RuntimeError("Live app does not use grouped comparisons")
    history_path = Path(__file__).resolve().parents[1] / "data/market-price-history.json"
    if history_path.exists():
        _, _, market_page = request("/market-prices.html")
        if b"market-prices.html" not in page or b"market-price-reference.png" not in market_page:
            raise RuntimeError("Live market prices page or homepage link is stale")
        _, _, history = request("/data/market-price-history.json")
        if json.loads(history) != json.loads(history_path.read_text()):
            raise RuntimeError("Live market price history differs from the GitHub release")
    print(f"PASS: MNtrees page, app.js and {len(products)} advertised menu records are accessible.")
    print("Note: this checks published data accessibility, not retailer inventory or freshness.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("FAIL:", exc, file=sys.stderr)
        sys.exit(1)
