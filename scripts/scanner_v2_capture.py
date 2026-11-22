#!/usr/bin/env python3
"""Convert rendered menu card evidence into Scanner V2 observations.

Strictly capture-only. Never derives brand, strain, category, or package
weight from an old scanner's normalized fields. The shared identity engine
does that later. This module does not fetch retailers or write production.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

from scanner_v2_observation import observation, identity_input
from scanner_v2_source_plan import source_class

ROOT = Path(__file__).resolve().parents[1]
PRICE = re.compile(r"\$\s*\d+(?:\.\d{2})?")
NONPRODUCT = re.compile(
    r"\b(?:gummies|edibles?|beverages?|drinks?|tinctures?|topicals?|"
    r"batteries|chargers|lighters|grinders|accessories)\b", re.I)


def capture_rendered(data):
    """Return observations and holds from actual observed rendered cards."""
    captured, holds = [], []
    for store in data.get("results", []):
        retailer_id = str(store.get("id") or "")
        retailer = str(store.get("retailer") or "")
        observed_at = str(store.get("scanned_at") or "")
        # Explicitly skip 'last_successful_products': these are not current
        # captures and must never be presented as fresh observations.
        for index, card in enumerate(store.get("products") or []):
            body = str(card.get("card_text") or "").strip()
            prices = card.get("price_candidates") or []
            url = str(card.get("product_url") or "").strip()
            menu = str(card.get("source_menu_url") or store.get("menu_url") or "").strip()
            reason = ""
            if not body:
                reason = "missing_raw_card"
            elif NONPRODUCT.search(body):
                reason = "non_target_product"
            elif len(prices) != 1:
                reason = "ambiguous_or_missing_price"
            elif not url or not menu:
                reason = "missing_source_url"
            if reason:
                holds.append({"retailer_id": retailer_id, "card_index": index,
                              "reason": reason, "raw_card": body[:650], "source_url": url})
                continue
            title = str(card.get("raw_product_title") or "").strip() or PRICE.split(body, maxsplit=1)[0].strip()
            if not (3 <= len(title) <= 180):
                holds.append({"retailer_id": retailer_id, "card_index": index,
                              "reason": "missing_product_title", "raw_card": body[:650],
                              "source_url": url})
                continue
            try:
                value = observation({
                    "retailer_id": retailer_id, "retailer": retailer,
                    "source_url": menu, "product_url": url,
                    "raw_title": title, "observed_at": observed_at,
                    "adapter": "rendered_menu_card",
                    "source_kind": ("secondary_research" if card.get("secondary_source") or source_class(menu) == "secondary"
                                    else "official_menu_candidate"),
                    "price": prices[0],
                    # Brand may come from an actual card brand element,
                    # never from an earlier normalized offer.
                    "source_brand_text": card.get("brand_candidate") or "",
                    "source_product_id": card.get("source_product_id") or "",
                    "variant_key": card.get("variant_key") or "",
                    "source_metadata": {
                        "card_text": body[:650],
                        "category_hint_unverified": card.get("category_candidate") or "",
                        "weight_candidates_unverified": card.get("weight_candidates") or [],
                        "source_product_url_type": "linked_card" if card.get("product_url") else "none",
                    },
                    "stock_status": "not_verified",
                })
            except (TypeError, ValueError) as exc:
                holds.append({"retailer_id": retailer_id, "card_index": index,
                              "reason": "invalid_observation",
                              "detail": str(exc)[:160], "source_url": url})
                continue
            captured.append(value)
    # Provider snapshots can repeat cards on recommended/category widgets.
    # Deduplicate only *identical evidence*. Conflicts are held, not overwritten.
    unique, observed_ids = [], {}
    for item in captured:
        prior = observed_ids.get(item["observation_id"])
        if prior and prior["evidence_sha256"] != item["evidence_sha256"]:
            holds.append({"retailer_id": item["retailer_id"],
                          "reason": "conflicting_same_product_identity",
                          "observation_id": item["observation_id"],
                          "raw_product_title": item["raw_title"],
                          "brand_candidate": item["source_brand_text"],
                          "raw_card": item["source_metadata"]["card_text"],
                          "source_url": item["product_url"]})
        elif not prior:
            observed_ids[item["observation_id"]] = item
            unique.append(item)
    return unique, holds


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(ROOT / "data/rendered_menu_candidates.json"))
    parser.add_argument("--output", default=str(ROOT / "reports/scanner_v2_captured.json"))
    args = parser.parse_args()
    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    captured, holds = capture_rendered(source)
    report = {"schema_version": 2,
              "purpose": "read_only_raw_rendered_evidence_not_new_retailer_scan",
              "captured": len(captured), "held": len(holds),
              "observations": captured, "holds": holds}
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(json.dumps({"captured": len(captured), "held": len(holds),
                      "status": report["purpose"]}))


if __name__ == "__main__":
    main()
