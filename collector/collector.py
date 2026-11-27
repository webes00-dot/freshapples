#!/usr/bin/env python3
"""MNtrees read-only public menu scanner. Never publishes partial scan output."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import datetime as dt
import hashlib
import ipaddress
import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from tymber_adapter import extract_cards
from brand_aliases import canonical_brand
from flowhub_adapter import extract_cards as extract_flowhub_cards
from track_menu_misses import menu_page

ROOT = Path(__file__).resolve().parent
UTC = dt.timezone.utc

def now():
    return dt.datetime.now(UTC).isoformat(timespec="seconds")

def rows(filename):
    path = ROOT / "config" / filename
    if path.exists():
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    if filename == "menu_targets.csv":
        # Reuse the existing published target list; do not require a second CSV.
        source = ROOT.parent / "data" / "retailer_menu_scan_targets.json"
        targets = json.loads(source.read_text(encoding="utf-8"))
        return [{"retailer": t["name"], "license": t["id"],
                 "verified_direct_menu_url": t["url"]} for t in targets]
    if filename in ("menu_categories.csv", "naming_corrections.csv"):
        return []
    raise FileNotFoundError(path)

def valid_public_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        return False
    name = parsed.hostname.lower().rstrip(".")
    if name in ("localhost",) or name.endswith((".local", ".internal")):
        return False
    try:
        return ipaddress.ip_address(name).is_global
    except ValueError:
        return True

def fetch(url, timeout=12):
    if not valid_public_url(url):
        return {"ok": False, "error": "invalid_url"}
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "MNtrees-menu-research/0.1", "Accept": "text/html,application/ld+json"}
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            final_url = response.geturl()
            if not valid_public_url(final_url):
                return {"ok": False, "error": "invalid_redirect"}
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type and "json" not in content_type:
                return {"ok": False, "error": "unsupported_content_type", "status": response.status}
            payload = response.read(2_000_001)
            if len(payload) > 2_000_000:
                return {"ok": False, "error": "page_too_large", "status": response.status}
            return {"ok": True, "status": response.status, "url": final_url,
                    "html": payload.decode("utf-8", errors="replace")}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": "http_error", "status": exc.code}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}

def jsonld_products(html):
    pattern = r"<script\b[^>]*type\s*=\s*['\"]application/ld\+json['\"][^>]*>(.*?)</script\s*>"
    for block in re.findall(pattern, html, flags=re.IGNORECASE | re.DOTALL):
        try:
            tree = json.loads(block)
        except ValueError:
            continue
        queue = [tree]
        while queue:
            node = queue.pop()
            if isinstance(node, list):
                queue.extend(node)
            elif isinstance(node, dict):
                if "@graph" in node:
                    queue.append(node["@graph"])
                kind = node.get("@type", [])
                kinds = [kind] if isinstance(kind, str) else kind if isinstance(kind, list) else []
                if any(str(item).lower().split("/")[-1] == "product" for item in kinds):
                    yield node

def extract_product(product, retailer, page_url, checked_at, store_id=''):
    name = str(product.get("name") or "").strip()
    offer = product.get("offers")
    if isinstance(offer, list):
        offer = next((x for x in offer if isinstance(x, dict) and x.get("price") is not None), None)
    if not name or not isinstance(offer, dict):
        return None
    try:
        price = float(str(offer.get("price", "")).replace("$", "").replace(",", ""))
    except (ValueError, TypeError):
        return None
    if not (0 < price < 10000) or offer.get("priceCurrency", "USD") != "USD":
        return None
    url = urllib.parse.urljoin(page_url, product.get("url") or offer.get("url") or page_url)
    if not valid_public_url(url):
        return None
    brand = product.get("brand") or ""
    if isinstance(brand, dict):
        brand = brand.get("name") or ""
    source_id = str(product.get("sku") or product.get("productID") or "").strip()
    identity = f"{store_id or retailer}|{source_id or url}|{name}"
    return {"id": hashlib.sha256(identity.encode()).hexdigest()[:20], "retailer": retailer, "store_id": store_id,
            "product_name": name, "strain": "", "brand": str(brand), "category": "",
            "observed_brand": str(brand),
            "package_g": None, "price": round(price, 2), "url": url,
            "source_id": source_id, "checked_at": checked_at,
            "weight_status": "unverified", "stock_status": "not_verified", "source_method": "jsonld"}

def apply_corrections(products):
    corrections = {}
    for row in rows("naming_corrections.csv"):
        if (row.get("Decision") or "").strip().lower() == "approved":
            key = ((row.get("Retailer") or "").strip().casefold(), (row.get("Source ID") or "").strip())
            if key[1]:
                corrections[key] = row
    for product in products:
        product["brand"] = canonical_brand(product.get("brand"))
        match = corrections.get((product["retailer"].casefold(), product["source_id"]))
        if match:
            for source, target in (("Correct brand", "brand"), ("Correct strain", "strain")):
                if (match.get(source) or "").strip():
                    product[target] = canonical_brand(match[source]) if target == "brand" else match[source].strip()
            try:
                grams = float(match.get("Total grams") or "")
                if grams > 0:
                    product["package_g"] = grams
                    product["weight_status"] = "source_id_correction"
            except ValueError:
                pass
    return products

def consolidate(products):
    # Retailer prices and product formats must never be merged across locations.
    seen, conflicts = {}, []
    for product in products:
        identity = (product.get("store_id") or product["retailer"].casefold(), product["source_id"] or product["url"], product["product_name"])
        prior = seen.get(identity)
        if prior is None:
            seen[identity] = product
        elif prior["price"] != product["price"]:
            conflicts.append({"identity": identity, "old": prior, "new": product})
    return list(seen.values()), conflicts

def supplemental_category_urls(license_id, primary_url, category_rows):
    """Extra category pages for the same licensed store; no duplicate store identities."""
    found = []
    seen = {primary_url.rstrip("/")}
    for row in category_rows:
        if row.get("license") != license_id:
            continue
        url = (row.get("url") or "").strip()
        if url and url.rstrip("/") not in seen and valid_public_url(url):
            found.append((row.get("category") or "Unknown", url))
            seen.add(url.rstrip("/"))
    return found

FLOWHUB_CATEGORIES={"flower","preroll","pre-roll","infused-preroll","vapes","vapes-carts","concentrates"}
def flowhub_category_pages(html,base_url,limit=7):
    """Only follow first-party cannabis-category URLs already linked by store."""
    base=urllib.parse.urlsplit(base_url)
    found=[]
    for href in re.findall(r'<a\b[^>]*\bhref=["\']([^"\']+)["\']',html,re.I):
        dest=urllib.parse.urljoin(base_url,href)
        parsed=urllib.parse.urlsplit(dest)
        if parsed.scheme!="https" or parsed.hostname!=base.hostname:
            continue
        parts=parsed.path.lower().strip("/").split("/")
        if len(parts)<4 or parts[0] not in ("rec","med") or parts[1] not in FLOWHUB_CATEGORIES or parts[2]!="nb":
            continue
        url=urllib.parse.urlunsplit((parsed.scheme,parsed.netloc,parsed.path,"",""))
        if url.rstrip("/") !=base_url.rstrip("/") and url not in found:
            found.append(url)
        if len(found)>=limit:
            break
    return found

def scan_target(target, extra_categories, checked_at, delay):
    statuses, extracted = [], []
    url = (target.get("verified_direct_menu_url") or target.get("menu_or_site_url") or "").strip()
    status = {"retailer": target["retailer"], "license": target["license"],
              "url": url, "checked_at": checked_at, "connection": "not_tested",
              "extraction": "not_tested", "count": 0}
    if not url:
        status["connection"] = "no_url"
    else:
        result = fetch(url)
        status["connection"] = "reachable" if result["ok"] else "failed"
        status["http_status"] = result.get("status")
        if result["ok"]:
            batch = [item for node in jsonld_products(result["html"])
                     if (item := extract_product(node, target["retailer"], result["url"], checked_at, target["license"]))]
            # Tymber menu product cards expose linked products and visible prices,
            # but usually not Product JSON-LD. Keep offers store-specific.
            if "shop.mnthc.co" in urllib.parse.urlsplit(result["url"]).hostname.lower():
                for offer in extract_cards(result["html"], result["url"]):
                    item = {
                        **offer, "retailer": target["retailer"],
                        "store_id": target["license"], "source_id": "",
                        "checked_at": checked_at, "source_method": "ty mber_html_card".replace(" ", ""),
                        "stock_status": "not_verified", "weight_status": "title_explicit",
                    }
                    identity = f'{item["store_id"]}|{item["url"]}|{item["product_name"]}'
                    item["id"] = hashlib.sha256(identity.encode()).hexdigest()[:20]
                    batch.append(item)
            # Flowhub/dispensary.shop product cards have direct product links
            # and advertised price text. Extract as review-only until an
            # independent detail-page validator is implemented.
            hostname = urllib.parse.urlsplit(result["url"]).hostname or ""
            if hostname.endswith(".dispensary.shop"):
                for offer in extract_flowhub_cards(result["html"], result["url"]):
                    item = {
                        **offer, "retailer": target["retailer"],
                        "store_id": target["license"], "source_id": "",
                        "checked_at": checked_at,
                    }
                    source_identity = f'{item["store_id"]}|{item["url"]}|{item["product_name"]}'
                    item["id"] = hashlib.sha256(source_identity.encode()).hexdigest()[:20]
                    batch.append(item)
            status["menu_pages"] = []
            if primary_page := menu_page(url, result, batch):
                status["menu_pages"].append(primary_page)
            if hostname.endswith(".dispensary.shop"):
                category_pages=flowhub_category_pages(result["html"],result["url"])
                status["flowhub_category_pages"]=len(category_pages)
                status["flowhub_category_results"]=[]
                for category_url in category_pages:
                    time.sleep(0.25)
                    category_page=fetch(category_url,timeout=9)
                    category_rows=[]
                    if category_page.get("ok") and (urllib.parse.urlsplit(category_page["url"]).hostname or "")==hostname:
                        for offer in extract_flowhub_cards(category_page["html"],category_page["url"]):
                            item={**offer,"retailer":target["retailer"],"store_id":target["license"],
                                  "source_id":"","checked_at":checked_at}
                            identity=f'{item["store_id"]}|{item["url"]}|{item["product_name"]}'
                            item["id"]=hashlib.sha256(identity.encode()).hexdigest()[:20]
                            category_rows.append(item)
                        batch.extend(category_rows)
                    if covered_page := menu_page(category_url, category_page, category_rows):
                        status["menu_pages"].append(covered_page)
                    status["flowhub_category_results"].append({
                        "url":category_url,"reachable":category_page.get("ok",False),
                        "offers":len(category_rows)
                    })
            # Deduplicate repeated recommended/menu sections before staging.
            batch.sort(key=lambda item: bool(item.get("observed_product_name")))
            batch = list({(x.get("store_id"), x["url"], x["product_name"]): x for x in batch}.values())
            status["count"] = len(batch)
            status["html_bytes"] = len(result["html"].encode("utf-8"))
            status["visible_price_tokens"] = len(re.findall(r"\$\s*\d+(?:\.\d{2})?", result["html"]))
            # Diagnostic evidence for Flowhub: no full HTML is retained.
            # Count product hrefs and capture a handful of sanitized card
            # snippets so adapters can be fixed from reproducible evidence.
            if (urllib.parse.urlsplit(result["url"]).hostname or "").endswith(".dispensary.shop"):
                html_text = result["html"]
                path_hits = list(re.finditer(r"/(?:rec|med)/[^\\\"'<>\\s]{0,250}/pdp/[^\\\"'<>\\s]{0,250}", html_text, re.I))
                anchor_hits = list(re.finditer(r"<a\\b[^>]{0,1500}href=[\\\"']([^\\\"']+)[\\\"']", html_text, re.I))
                product_anchors = [m for m in anchor_hits if "/pdp/" in m.group(1)]
                status["flowhub_diagnostics"] = {
                    "pdp_path_hits": len(path_hits),
                    "path_context_samples": [re.sub(r"\\s+"," ",html_text[max(0,m.start()-500):min(len(html_text),m.end()+700)])[:1400] for m in path_hits[:3]],
                    "pdp_anchor_hits": len(product_anchors),
                    "all_anchor_hits": len(anchor_hits),
                    "samples": [
                        {
                            "href": m.group(1)[:280],
                            "html_structure": re.sub(r"\\s+", " ", html_text[max(0,m.start()-250):min(len(html_text),m.end()+1600)])[:1450],
                        }
                        for m in product_anchors[:3]
                    ],
                }

            status["script_data_markers"] = sorted(set(re.findall(r"<script[^>]*(?:id|type)=[\"\']([^\"\']+)", result["html"], flags=re.I)))[:20]
            # Preserve public-page structural evidence only; never store full HTML or visitor data.
            status["price_snippets"] = [re.sub(r"<[^>]+>", " ", result["html"][max(0,m.start()-120):m.end()+90]).strip()[:230] for m in list(re.finditer(r"\$\s*\d+(?:\.\d{2})?", result["html"]))[:3]]
            status["product_links_near_prices"] = []
            for match in list(re.finditer(r"\\$\\s*\\d+(?:\\.\\d{2})?", result["html"]))[:8]:
                near = result["html"][max(0, match.start()-2500):match.end()+150]
                anchor_matches = list(re.finditer(r'<a\\b[^>]*href=["\\\']([^"\\\']+)["\\\'][^>]*>(.*?)</a>', near, re.I | re.S))
                candidates = []
                for anchor in anchor_matches[-5:]:
                    label = re.sub(r'<[^>]+>', ' ', anchor.group(2))
                    label = re.sub(r'\\s+', ' ', label).strip()[:120]
                    if len(label) >= 6:
                        candidates.append({"text": label, "url": urllib.parse.urljoin(result["url"], anchor.group(1))})
                if candidates:
                    status["product_links_near_prices"].append({"price": match.group(), "anchors": candidates[-3:]})
            status["extraction"] = "jsonld" if batch else "adapter_needed_or_no_products"
            extracted.extend(batch)
        else:
            status["error"] = result["error"]
    statuses.append(status)
    # Record reachability of category-specific menu pages for platforms
    # still awaiting a validated extraction adapter. Do not guess products.
    for category, category_url in supplemental_category_urls(target["license"], url, extra_categories):
        time.sleep(delay)
        category_result = fetch(category_url)
        statuses.append({
            "retailer": target["retailer"], "license": target["license"],
            "category": category, "url": category_url, "checked_at": checked_at,
            "connection": "reachable" if category_result["ok"] else "failed",
            "http_status": category_result.get("status"),
            "extraction": "adapter_needed_or_no_products" if category_result["ok"] else "not_tested",
            "count": 0, "error": category_result.get("error", ""),
            "note": "Category source monitored; not an inventory claim"
        })
    return statuses, extracted


def run_scan(limit=None, delay=1.5, include_license=None, workers=1, targets_path=None):
    targets = rows("menu_targets.csv")
    if targets_path and targets_path.exists():
        targets = json.loads(targets_path.read_text(encoding="utf-8"))
    extra_categories = rows("menu_categories.csv")
    if limit is not None:
        chosen = targets[:limit]
        for wanted in (include_license or []):
            chosen.extend(row for row in targets if row["license"] == wanted and row not in chosen)
        targets = chosen
    checked_at = now()
    statuses, extracted = [], []

    def collect(item):
        index, target = item
        if index:
            time.sleep(delay)
        return scan_target(target, extra_categories, checked_at, delay)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for observations, offers in pool.map(collect, enumerate(targets)):
            statuses.extend(observations)
            extracted.extend(offers)
    products, conflicts = consolidate(apply_corrections(extracted))
    result = {"checked_at": checked_at, "targets_checked": len(targets), "limited": limit is not None, "statuses": statuses,
              "counts": {"extracted": len(extracted), "deduplicated": len(products), "conflicts": len(conflicts)},
              "conflicts": conflicts, "published": False,
              "reason": "read_only_staging; do not overwrite last known good product catalog"}
    output = ROOT / "data"
    output.mkdir(exist_ok=True)
    (output / "latest_scan.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (output / "candidate_products.json").write_text(json.dumps(products, indent=2) + "\n", encoding="utf-8")
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--delay", type=float, default=1.5)
    parser.add_argument("--include-license", type=str, action="append", default=[])
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--targets", type=Path)
    args = parser.parse_args()
    result = run_scan(args.limit, args.delay, args.include_license, args.workers, args.targets)
    print(json.dumps({"checked_at": result["checked_at"], "targets_checked": result["targets_checked"],
                      "counts": result["counts"], "published": result["published"]}, indent=2))
