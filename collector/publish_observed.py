#!/usr/bin/env python3
"""Publish directly observed advertised menu offers; NEVER infer inventory or weight.

A source-observed price is suitable for comparison without claiming verified stock.
Retain every location/format/variant; group by family metadata, not by deletion.
Ambiguous card/detail prices are held. Failed scans preserve prior offers.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlsplit
from product_families import annotate

ROOT=Path(__file__).resolve().parents[1]

def key_of(row):
    store=str(row.get("store_id") or "").strip().casefold()
    source=str(row.get("url") or "").strip().split("?")[0].rstrip("/")
    name=str(row.get("product_name") or "").casefold().strip()
    return (store,source,name) if store and source and name else None

def money(value):
    try:
        n=float(value)
        return round(n,2) if math.isfinite(n) and 0<n<10000 else None
    except (TypeError,ValueError):
        return None

def weight(value):
    try:
        n=float(value)
        return n if math.isfinite(n) and 0<n<=112 else None
    except (ValueError,TypeError):
        return None

def resolve_store(c,locations):
    store=locations.get(c.get("store_id"))
    if not store or not store.get("address"):
        return None
    url=urlsplit(str(c.get("url") or ""))
    if url.scheme!="https" or not url.hostname:
        return None
    # No cross-location attribution; only exact scanned retailer license.
    if c.get("retailer")!=store.get("retailer"):
        return None
    address=store["address"]
    known={
        "MICRO-L25-000630-01-AUR":"Saint Paul",
        "MICRO-L25-000584-01-AUR":"East Bethel",
        "DIS-L24-000396-01-AUR":"Lakeville",
        "DIS-L24-000396-02-AUR":"Dundas",
        "MICRO-L25-000395-01-AUR":"Roseville",
        "MICRO-L25-000658-01-AUR":"Minneapolis",
        "MICRO-L24-000244-02-AUR":"Breckenridge",
        "MICRO-L25-000913-01-AUR":"Minneapolis",
        "MICRO-L24-000333-01-AUR":"Detroit Lakes",
        "MICRO-L25-000364-01-AUR":"Richfield",
        "MICRO-L25-000398-01-AUR":"Savage",
        "MICRO-L25-000821-01-AUR":"Lakeland Shores",
        "MICRO-L25-000608-01-AUR":"Moorhead",
        "MICRO-L25-000439-01-AUR":"Minneapolis",
        "MICRO-L25-001117-01-AUR":"Winona",
        "MICRO-L24-000290-04-AUR":"Saint Paul",
        "DIS-L25-000046-01-AUR":"Anoka",
        "MICRO-L25-000436-01-AUR":"Chaska",
        "MICRO-L24-000426-01-AUR":"La Crescent",
        "DIS-L25-000016-01-AUR":"Winona",
        "MICRO-L24-000346-01-AUR":"Winona",
        "MICRO-L25-001282-01-AUR":"Saint Peter",
        "MICRO-L25-001251-01-AUR":"Alexandria",
    }
    city=known.get(c.get("store_id"))
    # An unknown city is displayed as the exact store address instead of guessed.
    return city or "",address

def promote(existing,candidates,scan,detail_report,locations):
    if not isinstance(existing,list) or not isinstance(candidates,list) or not scan.get("checked_at"):
        raise ValueError("Invalid catalog or scan")
    results=[dict(x) for x in existing]
    exact={key_of(x):i for i,x in enumerate(results) if key_of(x)}
    ids={x["id"] for x in results}
    detail={r.get("id"):r for r in detail_report.get("records",[])}
    reachable={r.get("license") for r in scan.get("statuses",[]) if r.get("connection")=="reachable"}
    seen=set()
    report={"added":0,"price_updated":0,"held":0,"removed":0,"total":len(results)}
    for c in candidates:
        ref=key_of(c)
        if not ref or ref in seen:
            report["held"]+=1
            continue
        seen.add(ref)
        if c.get("checked_at")!=scan["checked_at"] or c.get("store_id") not in reachable:
            report["held"]+=1
            continue
        method=c.get("source_method")
        url=str(c.get("url") or "")
        host=urlsplit(url).hostname or ""
        if method=="tymber_html_card":
            if host!="shop.mnthc.co" or "/products/" not in urlsplit(url).path:
                report["held"]+=1
                continue
        elif method=="flowhub_html_card_review_only":
            if not host.endswith(".dispensary.shop") or "/pdp/" not in urlsplit(url).path:
                report["held"]+=1
                continue
        else:
            report["held"]+=1
            continue
        place=resolve_store(c,locations)
        price=money(c.get("price"))
        if not place or price is None or not c.get("product_name") or not c.get("category"):
            report["held"]+=1
            continue
        verification=detail.get(c.get("id"),{})
        if verification.get("status") in ("mismatch","invalid_candidate_price"):
            report["held"]+=1
            continue
        if ref in exact:
            old=results[exact[ref]]
            if old.get("category")!=c.get("category") or old.get("product_name")!=c.get("product_name"):
                report["held"]+=1
                continue
            if money(old.get("price"))!=price:
                previous=money(old.get("price"))
                if previous and .5*previous<=price<=1.5*previous:
                    old["price"]=price
                    old["checked_at"]=scan["checked_at"]
                    report["price_updated"]+=1
                else:
                    report["held"]+=1
            continue
        source_id=str(c.get("id") or "")
        new_id=source_id or "scan-"+hashlib.sha256("|".join(ref).encode()).hexdigest()[:20]
        if new_id in ids:
            report["held"]+=1
            continue
        city,address=place
        entry={
            "id":new_id,"retailer":("Fort Road Cannabis" if c["retailer"].startswith("Fort Road Cannabis") else c["retailer"]+(" — "+city if city and city.lower() not in c["retailer"].lower() else "")),
            "strain":str(c.get("strain") or c["product_name"]),
            "brand":str(c.get("brand") or ""),
            "category":c["category"],
            "package_g":weight(c.get("package_g")),
            "price":price,"city":city,"state":"MN","address":address,
            "url":url,"checked_at":scan["checked_at"],
            "source_method":method,"stock_status":"not_verified",
            "record_status":"observed_advertised_menu",
            "product_name":c["product_name"],
            "source_id":str(c.get("source_id") or ""),
            "store_id":c["store_id"],
            "source_reference":"Public retailer product menu; advertised price not guaranteed at checkout"
        }
        results.append(annotate(entry))
        exact[ref]=len(results)-1
        ids.add(new_id)
        report["added"]+=1
    report["total"]=len(results)
    return results,report

def main():
    p=argparse.ArgumentParser()
    for name,default in (
        ("catalog","data/listings.json"),("candidates","collector/data/candidate_products.json"),
        ("scan","collector/data/latest_scan.json"),("details","collector/data/detail_verification.json"),
        ("stores","collector/config/menu_targets.csv"),("report","collector/data/observed_publication_diff.json"),
        ("manifest","data/manifest.json")):
        p.add_argument("--"+name,type=Path,default=ROOT/default)
    a=p.parse_args()
    import csv
    with a.stores.open(encoding="utf-8-sig",newline="") as f:
        stores={x["license"]:x for x in csv.DictReader(f)}
    old=json.loads(a.catalog.read_text())
    new,report=promote(old,json.loads(a.candidates.read_text()),json.loads(a.scan.read_text()),
                       json.loads(a.details.read_text()),stores)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2)+"\n")
    if report["added"] or report["price_updated"]:
        a.catalog.write_text(json.dumps(new,indent=2,ensure_ascii=False)+"\n")
        manifest=json.loads(a.manifest.read_text())
        manifest["listings"]=len(new)
        manifest["retailers"]=len({x["retailer"] for x in new})
        manifest["snapshot_date"]=json.loads(a.scan.read_text())["checked_at"]
        manifest["verification"]="Advertised public-menu prices. Not verified inventory or guaranteed final checkout prices."
        a.manifest.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    main()
