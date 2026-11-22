#!/usr/bin/env python3
"""Append verified offers and refresh independently verified prices.

Fail closed. Never deletes offers or promotes conflicting / ambiguous products.
Publishing is enabled only after scan + detail + publication gate all agree.
The caller is responsible for committing and deploying the resulting file.
"""
import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
from review_catalog import identity
from publication_gate import check
from product_families import annotate

def load_stores(csv_path):
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        return {r["license"]:r for r in csv.DictReader(handle)}

def store_location(candidate, stores):
    store_id = candidate.get("store_id")
    store = stores.get(store_id)
    if not store:
        return None
    url = urlsplit(candidate.get("url") or "")
    segment = url.path.strip("/").split("/")[0].lower()
    # Only publish sources explicitly supported by an audited location adapter.
    if candidate.get("source_method") != "tymber_html_card" or url.hostname != "shop.mnthc.co":
        return None
    if segment not in ("lakeville","dundas"):
        return None
    city = segment.capitalize()
    if city.lower() not in store.get("address","").lower():
        return None
    if store.get("retailer") != candidate.get("retailer"):
        return None
    return {"city": city,"state":"MN","address":store["address"],
            "retailer":store["retailer"]+" — "+city}

def same_description(old, new):
    for k in ("strain","brand","category"):
        if str(old.get(k) or "").strip().casefold() != str(new.get(k) or "").strip().casefold():
            return False
    try:
        return math.isclose(float(old["package_g"]),float(new["package_g"]),rel_tol=0,abs_tol=1e-9)
    except (ValueError,TypeError,KeyError):
        return False

def promote(published, candidates, scan, details, readiness, stores):
    verified = {r.get("id"):r for r in details.get("records",[])}
    eligible = {r.get("id"):r for r in readiness.get("records",[])}
    existing = {identity(x):i for i,x in enumerate(published) if identity(x)}
    result = [dict(x) for x in published]
    seen_keys = set()
    key_counts = {}
    for item in candidates:
        item_key = identity(item)
        key_counts[item_key] = key_counts.get(item_key, 0) + 1
    events = []
    hold = []
    scan_ids = {s.get("license") for s in scan.get("statuses",[])
                if s.get("connection") == "reachable"}
    if not scan.get("checked_at") or not isinstance(published,list) or not isinstance(candidates,list):
        raise ValueError("Invalid scan or catalog")
    for c in candidates:
        pid=c.get("id")
        key=identity(c)
        problems=[]
        gate=eligible.get(pid)
        detail=verified.get(pid)
        loc=store_location(c,stores)
        if not gate or gate.get("readiness")!="machine_checks_passed_needs_human_approval":
            problems.append("failed_readiness_gate")
        if not detail or detail.get("status")!="confirmed":
            problems.append("detail_not_confirmed")
        if check(c,detail):
            problems.append("failed_product_quality_check")
        if not loc:
            problems.append("unsupported_store_or_adapter")
        if c.get("store_id") not in scan_ids:
            problems.append("retailer_not_reached")
        if key is None or key in seen_keys or key_counts.get(key, 0) > 1:
            problems.append("missing_or_duplicate_identity")
        seen_keys.add(key)
        # Candidate must come from this scan, not a leftover file.
        if c.get("checked_at") != scan.get("checked_at"):
            problems.append("stale_candidate")
        if problems:
            hold.append({"id":pid,"product_name":c.get("product_name"),"reasons":problems})
            continue
        prior=result[existing[key]] if key in existing else None
        if prior is not None:
            if not same_description(prior,c):
                hold.append({"id":pid,"reasons":["metadata_changed_requires_review"]})
                continue
            try:
                old_price=float(prior["price"])
                new_price=float(c["price"])
            except (ValueError,TypeError,KeyError):
                hold.append({"id":pid,"reasons":["invalid_price"]})
                continue
            if not math.isfinite(new_price) or new_price<=0 or new_price>old_price*1.5 or new_price<old_price*.5:
                hold.append({"id":pid,"reasons":["large_price_change_requires_review"]})
                continue
            if not math.isclose(new_price,old_price,abs_tol=.001):
                result[existing[key]]["price"]=round(new_price,2)
                result[existing[key]]["checked_at"]=c["checked_at"]
                result[existing[key]]["source_reference"]="Verified detail page in scan "+str(scan["checked_at"])
                events.append({"action":"price_updated","id":prior["id"],"old_price":old_price,"price":new_price})
        else:
            if any(x.get("id")==pid for x in result):
                hold.append({"id":pid,"reasons":["id_collision"]})
                continue
            new={
                "id":pid, "retailer":loc["retailer"],
                "strain":c["strain"],"brand":c["brand"],"category":c["category"],
                "package_g":c["package_g"],"price":round(float(c["price"]),2),
                "city":loc["city"],"state":"MN","address":loc["address"],
                "url":c["url"],"checked_at":c["checked_at"],
                "source_method":"tymber_html_card_verified_jsonld",
                "stock_status":"not_verified","record_status":"verified_advertised_menu",
                "product_name":c["product_name"],"source_id":c.get("source_id") or "",
                "store_id":c["store_id"],"source_reference":"Verified detail page in scan "+str(scan["checked_at"])
            }
            result.append(annotate(new))
            existing[key]=len(result)-1
            events.append({"action":"added","id":pid,"price":new["price"]})
    if len(result)<len(published) or len({x["id"] for x in result})!=len(result):
        raise RuntimeError("Catalog safety check failed")
    return result, {"scan_checked_at":scan["checked_at"],"previous_count":len(published),
                    "new_count":len(result),"events":events,"holds":hold,"removed":0}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--catalog",type=Path,default=ROOT/"data/listings.json")
    p.add_argument("--manifest",type=Path,default=ROOT/"data/manifest.json")
    p.add_argument("--candidates",type=Path,default=ROOT/"collector/data/candidate_products.json")
    p.add_argument("--scan",type=Path,default=ROOT/"collector/data/latest_scan.json")
    p.add_argument("--details",type=Path,default=ROOT/"collector/data/detail_verification.json")
    p.add_argument("--gate",type=Path,default=ROOT/"collector/data/publication_readiness.json")
    p.add_argument("--stores",type=Path,default=ROOT/"collector/config/menu_targets.csv")
    p.add_argument("--report",type=Path,default=ROOT/"collector/data/published_diff.json")
    args=p.parse_args()
    current=json.loads(args.catalog.read_text())
    candidate=json.loads(args.candidates.read_text())
    scan=json.loads(args.scan.read_text())
    detail=json.loads(args.details.read_text())
    gate=json.loads(args.gate.read_text())
    result,report=promote(current,candidate,scan,detail,gate,load_stores(args.stores))
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+"\n")
    if report["events"]:
        args.catalog.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
        manifest=json.loads(args.manifest.read_text())
        manifest["listings"]=len(result)
        manifest["retailers"]=len(set(x["retailer"] for x in result))
        manifest["snapshot_date"]=scan["checked_at"]
        manifest["verification"]="Advertised menu prices verified on detail pages for automated changes; inventory not verified"
        manifest["last_auto_promotion"]=scan["checked_at"]
        args.manifest.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"added":sum(e["action"]=="added" for e in report["events"]),
                      "price_updates":sum(e["action"]=="price_updated" for e in report["events"]),
                      "held":len(report["holds"]),"catalog_total":len(result)},indent=2))

if __name__=="__main__":
    main()
