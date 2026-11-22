#!/usr/bin/env python3
"""Verify candidate offers against product detail pages. Review-only, no publishing.

A product is confirmed only when Product JSON-LD on its direct detail page has
the same product name and USD offer price. Ambiguous/missing markup is
inconclusive, never approval. One failed request cannot erase published data.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit
from collector import fetch, jsonld_products

PROJECT = Path(__file__).resolve().parents[1]
SPACE = re.compile(r"\s+")

def canonical_name(value):
    return SPACE.sub(" ", str(value or "").strip()).casefold()

def detail_offer(product):
    offers = product.get("offers") or []
    if isinstance(offers, dict):
        offers = [offers]
    if not isinstance(offers, list):
        return []
    prices = []
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        if str(offer.get("priceCurrency") or "USD").upper() != "USD":
            continue
        try:
            amount = float(str(offer.get("price", "")).replace("$", "").replace(",", ""))
        except (ValueError, TypeError):
            continue
        if 0 < amount < 10000:
            prices.append(round(amount, 2))
    return prices

def compare_detail(candidate, product_nodes):
    target_name = canonical_name(candidate.get("product_name"))
    try:
        target_price = round(float(candidate.get("price")), 2)
    except (ValueError, TypeError):
        return {"status": "invalid_candidate_price"}
    matched = [node for node in product_nodes if canonical_name(node.get("name")) == target_name]
    if len(matched) != 1:
        return {"status": "inconclusive", "reason": "missing_or_ambiguous_exact_product_name",
                "detail_product_nodes": len(product_nodes), "exact_name_nodes": len(matched)}
    prices = detail_offer(matched[0])
    if len(prices) != 1:
        return {"status": "inconclusive", "reason": "ambiguous_or_missing_detail_price",
                "detail_prices": prices}
    if target_price != prices[0]:
        return {"status": "mismatch", "reason": "detail_price_changed",
                "candidate_price": target_price, "detail_price": prices[0]}
    return {"status": "confirmed", "reason": "exact_jsonld_product_name_and_price",
            "verified_price": prices[0]}

def verify(candidates, fetcher=fetch, parser=jsonld_products):
    output = []
    for candidate in candidates:
        row = {"id": candidate.get("id"), "store_id": candidate.get("store_id"),
               "retailer": candidate.get("retailer"), "url": candidate.get("url"),
               "product_name": candidate.get("product_name"), "candidate_price": candidate.get("price")}
        if candidate.get("source_method") == "flowhub_html_card_review_only":
            row.update(status="unverified_card_only",
                       reason="Source-linked advertised price; independent detail comparison not performed")
            output.append(row)
            continue
        url = str(candidate.get("url") or "")
        if urlsplit(url).scheme != "https" or "/products/" not in urlsplit(url).path:
            row.update(status="invalid_url")
            output.append(row)
            continue
        result = fetcher(url)
        if not result.get("ok"):
            row.update(status="unreachable", reason=result.get("error", "fetch_failed"),
                       http_status=result.get("status"))
            output.append(row)
            continue
        # Require the detail page to remain on the same store-specific product path.
        requested = urlsplit(url)
        actual = urlsplit(result.get("url") or "")
        if (actual.hostname != requested.hostname or
            actual.path.rstrip("/") != requested.path.rstrip("/")):
            row.update(status="inconclusive", reason="detail_url_redirected")
            output.append(row)
            continue
        nodes = list(parser(result.get("html") or ""))
        row.update(compare_detail(candidate, nodes))
        output.append(row)
    counts = {status: sum(x["status"] == status for x in output) for status in
              ("confirmed", "inconclusive", "mismatch", "unreachable", "invalid_url", "invalid_candidate_price", "unverified_card_only")}
    return {"count": len(output), "counts": counts, "auto_published": 0,
            "publication_allowed": False, "records": output}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=PROJECT/"collector/data/candidate_products.json")
    parser.add_argument("--output", type=Path, default=PROJECT/"collector/data/detail_verification.json")
    args = parser.parse_args()
    candidates = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(candidates, list):
        raise SystemExit("Expected a list of candidate offers")
    report = verify(candidates)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"verified": report["counts"], "published": False}, indent=2))

if __name__ == "__main__":
    main()
