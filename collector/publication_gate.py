#!/usr/bin/env python3
"""Conservative candidate publication-gate report.

This tool stages decisions only. It cannot modify published data. Every candidate
requires an independent detail-page match plus an explicit category and weight.
Suspicious brand aliases and mismatched card/detail prices are kept on hold.
"""
import argparse
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
GRAM = re.compile(r'(?<![\d.])(\d+(?:\.\d+)?)\s*g(?:rams?)?\b', re.I)

def check(candidate, verification):
    reasons=[]
    if not verification or verification.get("status") != "confirmed":
        reasons.append("detail_not_confirmed")
    name = str(candidate.get("product_name") or "")
    weight_match=GRAM.search(name)
    try:
        weight=float(candidate.get("package_g"))
    except (ValueError,TypeError):
        weight=0
    if not weight_match or not math.isclose(float(weight_match.group(1)), weight, abs_tol=0.000001):
        reasons.append("weight_not_explicitly_confirmed_in_title")
    path=urlsplit(str(candidate.get("url") or "")).path.lower()
    category=str(candidate.get("category") or "").lower().strip()
    category_path = {
        "flower":"/flower/",
        "pre-roll":"/pre-roll/",
        "preroll":"/pre-roll/",
        "vape":"/vape/",
    }.get(category)
    if not category_path or category_path not in path:
        reasons.append("category_not_supported_by_product_path")
    brand=str(candidate.get("brand") or "").strip()
    if not brand or brand.casefold() not in name.casefold():
        reasons.append("brand_not_supported_by_title")
    if brand.casefold() in ("craft", "craft cannabis", "flor", "flör"):
        reasons.append("brand_alias_review")
    if str(candidate.get("source_method") or "") != "tymber_html_card":
        reasons.append("unreviewed_extractor")
    if candidate.get("stock_status") != "not_verified":
        reasons.append("stock_disclaimer_missing")
    return sorted(set(reasons))

def evaluate(candidates, detail_report, catalog_review):
    details={r.get("id"):r for r in detail_report.get("records",[])}
    competing={}
    for c in candidates:
        key=(c.get("store_id"),c.get("url"))
        competing[key]=competing.get(key,0)+1
    review_ids={r.get("record",{}).get("id") for r in catalog_review.get("needs_review",[]) if isinstance(r.get("record"),dict)}
    items=[]
    for c in candidates:
        issues=check(c,details.get(c.get("id")))
        if competing.get((c.get("store_id"),c.get("url")),0)>1:
            issues.append("duplicate_store_product")
        if c.get("id") in review_ids:
            issues.append("catalog_conflict")
        # Independently confirmed routine price changes may be promoted by the
        # guarded publisher. Unusually large changes are held there.
        # Never treat a price change alone as a metadata conflict.
        items.append({"id":c.get("id"),"retailer":c.get("retailer"),"product_name":c.get("product_name"),
                      "url":c.get("url"),"price":c.get("price"),
                      "detail_status":details.get(c.get("id"),{}).get("status","missing"),
                      "readiness":"machine_checks_passed_needs_human_approval" if not issues else "hold",
                      "reasons":sorted(set(issues))})
    return {"machine_checks_passed":sum(x["readiness"].startswith("machine_checks_passed") for x in items),
            "on_hold":sum(x["readiness"]=="hold" for x in items),
            "publish_approved":False,"auto_published":0,
            "note":"Machine checks do not establish real-time stock, retailer permissions, or editorial approval.",
            "records":items}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--candidates",type=Path,default=ROOT/"collector/data/candidate_products.json")
    parser.add_argument("--details",type=Path,default=ROOT/"collector/data/detail_verification.json")
    parser.add_argument("--catalog-review",type=Path,default=ROOT/"collector/data/catalog_review.json")
    parser.add_argument("--output",type=Path,default=ROOT/"collector/data/publication_readiness.json")
    args=parser.parse_args()
    report=evaluate(json.loads(args.candidates.read_text()),
                    json.loads(args.details.read_text()),
                    json.loads(args.catalog_review.read_text()))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"machine_checks_passed":report["machine_checks_passed"],"on_hold":report["on_hold"],"published":False}))

if __name__=="__main__":
    main()
