#!/usr/bin/env python3
"""Prepare THC Minnesota observed SKUs under the owner's explicit import rule.

A new offer requires an identified retailer, brand, canonical strain, product form,
and explicit grams. The catalog builder will independently skip identities
already present. Source prices are observed historical prices, NOT live stock.
"""
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"collector/data/thc-store-reconciled/new_skus_to_verify.csv"
OUT=ROOT/"data/thc_owner_added_offers.json"
STORES=ROOT/"data/retailer_locations.json"
CATEGORY={"flower":"Flower","pre-rolls":"Preroll","concentrates":"Concentrates"}

def main():
    with SOURCE.open(newline="",encoding="utf-8-sig") as file:
        rows=list(csv.DictReader(file))
    if len(rows)!=335:
        raise ValueError("Expected the 335 owner-selected missing SKU candidates")
    stores={str(s["id"]):s for s in json.loads(STORES.read_text())}
    seen=set()
    output=[]
    for row in rows:
        if row.get("reconciled_status")!="new_sku_at_verified_location_pending_menu_price":
            raise ValueError("Invalid promotion status in input")
        store_id=str(row.get("reconciled_store_id") or "")
        store=stores.get(store_id)
        if store is None:
            raise ValueError("Unidentified physical retailer: "+store_id)
        kind=CATEGORY.get(str(row.get("category") or ""))
        # Keep reruns idempotent with the owner-reviewed canonical brand names.
        # Do not conflate Grasslands with the independently listed Grasslandz.
        from strain_rules import normalize_brand
        brand=normalize_brand(str(row.get("brand") or "").strip())
        strain=str(row.get("strain_match_candidate") or "").strip()
        if not (kind and brand and strain):
            raise ValueError("Incomplete brand/strain/category")
        if row.get("size_evidence") not in ("single_explicit_grams","explicit_total"):
            raise ValueError("Missing explicit package weight evidence")
        grams=round(float(row.get("size_g_from_product_label") or 0),3)
        price=round(float(row.get("observed_price") or 0),2)
        if not (0<grams<=56 and 0<price<=500):
            raise ValueError("Invalid grams or source price")
        def key(s):
            return re.sub(r"[^a-z0-9]","",str(s).casefold())
        signature=(store_id,key(brand),key(strain),kind,grams)
        if signature in seen:
            raise ValueError("Source contains duplicate store/brand/strain/form/size")
        seen.add(signature)
        sid=str(row.get("source_product_id") or "")
        did=str(row.get("source_dispensary_id") or "")
        if not sid or not did:
            raise ValueError("Source product/store identity not present")
        doc_id=hashlib.sha256((sid+"|"+did+"|"+kind+"|"+str(grams)).encode()).hexdigest()[:18]
        # A store menu/homepage link is useful even when the particular product has
        # no first-party URL. Do not manufacture a product-level URL.
        url=(str(row.get("mntrees_menu_url") or "").strip()
             or str(store.get("menu_url") or "").strip()
             or str(store.get("website_url") or "").strip())
        if url and not url.startswith(("https://","http://")):
            url=""
        output.append({
            "id":"thc-mn-"+doc_id,
            "retailer":store["name"],
            "retailer_id":store_id,
            "address":store.get("address") or row.get("store_address") or "",
            "city":row.get("city") or "",
            "state":"MN",
            "strain":strain,
            "master_strain":strain,
            "product_name":strain,
            "product_family":strain,
            "brand":brand,
            "category":kind,
            "package_g":grams,
            "price":price,
            "url":url,
            "checked_at":row.get("observed_date") or "",
            "source_method":"thc_minnesota_historical_price_observation",
            "source_reference":"THC Minnesota API observation; price is not independently checked on today's first-party retailer menu",
            "source_product_id":sid,
            "source_dispensary_id":did,
            "weight_source":row.get("source_weight_label") or "",
            "stock_status":"not_verified",
            "record_status":"owner_authorized_observed_offer",
            "reviewed_identity":True,
        })
    OUT.write_text(json.dumps(output,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("Prepared",len(output),"owner-authorized missing SKUs across",
          len({x["retailer_id"] for x in output}),"retailers")
    print("Source methods remain explicitly historical and not live-stock verified.")

if __name__=="__main__":main()
