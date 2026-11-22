#!/usr/bin/env python3
"""Read-only 367-candidate audit against the actual built MNtrees site catalog.

Conservatively distinguish exact SKU overlap, new listings at verified storefronts,
name/address review, and unresolvable stores. No record is approved for publication
without a first-party product URL and current price verification.
"""
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"collector/data/thc-catalog-audit"
MASTER=ROOT/"data/retailer_locations.json"
CATALOG=ROOT/"dist/data/catalog.json"
SOURCES=[
 (1,ROOT/"collector/data/thc-audit-b1/obvious_candidates.csv",ROOT/"data/thc_keeper_approval.json"),
 (2,ROOT/"collector/data/thc-audit-b2/new_obvious_candidates.csv",ROOT/"data/thc_keeper_batch2_approval.json"),
 (3,ROOT/"collector/data/thc-audit-b3/new_obvious_candidates.csv",None),
]
def compact(v):
    return re.sub(r"[^a-z0-9]+","",str(v or "").casefold())
def words(v):
    return re.sub(r"[^a-z0-9]+"," ",str(v or "").casefold()).strip()
def grams(v):
    try:
        return round(float(v),3)
    except (ValueError,TypeError):
        return None
def category(v):
    t=compact(v)
    if t in ("preroll","prerolls","pre rolled","pre-rolls") or "preroll" in t:return "preroll"
    if t in ("concentrate","concentrates"):return "concentrate"
    if t=="flower":return "flower"
    return t
def full_address(v):
    # Conservative: use complete address after only punctuation/case normalization.
    return compact(v)
def read(path):
    with path.open(newline="",encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))
def index_unique(registry,key):
    # Duplicate keys remain ambiguous and cannot produce confirmed retailer identities.
    out=defaultdict(set)
    for store in registry:
        k=key(store)
        if k:out[k].add(store["id"])
    return out
def main():
    candidates=[]
    batch_counts=Counter()
    for batch,path,approval_path in SOURCES:
        rows=read(path)
        if approval_path:
            approval=json.loads(approval_path.read_text())
            if hashlib.sha256(path.read_bytes()).hexdigest()!=approval["sha256"]:
                raise ValueError(f"Batch {batch} approval digest mismatch")
            if len(rows)!=approval["expected_count"] or dict(Counter(x["category"] for x in rows))!=approval["category_counts"]:
                raise ValueError(f"Batch {batch} approval counts mismatch")
        elif len(rows)!=93:
            raise ValueError("Batch 3 source count changed; expected 93")
        for row in rows:
            if not row.get("brand") or not row.get("strain_match_candidate") or grams(row.get("size_g_from_product_label")) is None:
                raise ValueError(f"Batch {batch} contains incomplete keeper")
            if category(row["category"]) not in ("flower","preroll","concentrate"):
                raise ValueError("Out-of-scope category")
            if row.get("size_evidence") not in ("single_explicit_grams","explicit_total"):
                raise ValueError("Weight not evidenced")
            candidates.append((batch,row))
        batch_counts[batch]=len(rows)
    if len(candidates)!=367:
        raise ValueError("Unexpected total: "+str(len(candidates)))
    registry=json.loads(MASTER.read_text())
    offers=json.loads(CATALOG.read_text())
    if not offers:raise ValueError("Empty built catalog")
    stores={x["id"]:x for x in registry}
    by_license=defaultdict(set)
    for item in registry:
        for lic in (item.get("id"),item.get("license_id")):
            if lic:by_license[str(lic).upper().strip()].add(item["id"])
    by_address=index_unique(registry,lambda x:full_address(x.get("address")))
    by_name=index_unique(registry,lambda x:compact(x.get("name")))
    by_name_city=index_unique(registry,lambda x:(compact(x.get("name")),compact(x.get("city"))) if x.get("city") else "")
    # Catalog can contain offers with and without stable retailer IDs.
    by_store=defaultdict(list)
    by_store_name=defaultdict(list)
    for offer in offers:
        oid=str(offer.get("retailer_id") or "").strip()
        if oid:by_store[oid].append(offer)
        if offer.get("retailer"):by_store_name[compact(offer.get("retailer"))].append(offer)
    results=[]
    statuses=Counter()
    for batch,row in candidates:
        ext_license=str(row.get("store_license") or "").upper().strip()
        resolved=""
        store_method="unresolved"
        candidates_license=by_license.get(ext_license,set())
        if len(candidates_license)==1:
            resolved=next(iter(candidates_license))
            store_method="unique_location_license"
        else:
            src_addr=full_address(row.get("store_address"))
            possibilities=by_address.get(src_addr,set()) if src_addr else set()
            if len(possibilities)==1:
                resolved=next(iter(possibilities))
                store_method="unique_full_address"
            else:
                names=by_name.get(compact(row.get("store")),set())
                # Name-only is a clue, never a confirmed storefront match.
                samecity={x for x in names if compact(row.get("city")) in compact(stores[x].get("address")) or
                          compact(stores[x].get("city"))==compact(row.get("city"))}
                possibilities=samecity if samecity else names
                if len(possibilities)==1:
                    resolved=next(iter(possibilities))
                    store_method="name_only_needs_address_verification"
                elif len(possibilities)>1:
                    store_method="ambiguous_store"
        src_brand=compact(row["brand"])
        src_strain=compact(row["strain_match_candidate"])
        src_cat=category(row["category"])
        src_grams=grams(row["size_g_from_product_label"])
        store=stores.get(resolved,{})
        storeoffers=by_store.get(resolved,[]) if resolved else []
        # Some published entries have no retailer_id. Use only the exact resolved
        # store name, not alternate guessed labels, to guard against branch collisions.
        storeoffers+= [o for o in by_store_name.get(compact(store.get("name")),[])
                       if not o.get("retailer_id")]
        def matches(o):
            return (compact(o.get("strain"))==src_strain and
                    compact(o.get("brand"))==src_brand and
                    category(o.get("category"))==src_cat and
                    grams(o.get("package_g"))==src_grams)
        exact=[o for o in storeoffers if matches(o)]
        global_matches=[o for o in offers if matches(o)]
        same_store_strain=[o for o in storeoffers if compact(o.get("strain"))==src_strain and category(o.get("category"))==src_cat]
        confirmed_store=store_method in ("unique_location_license","unique_full_address")
        if exact and confirmed_store:
            status="existing_same_store_sku"
        elif exact:
            status="probable_existing_sku_store_needs_review"
        elif confirmed_store:
            status="new_sku_at_confirmed_store_needs_first_party_verification"
        elif resolved:
            status="possible_new_sku_store_identity_needs_review"
        else:
            status="store_unresolved_no_import"
        statuses[status]+=1
        results.append({
            "batch":batch,"comparison_status":status,"retailer_match_method":store_method,
            "mntrees_retailer_id":resolved,"mntrees_retailer":store.get("name",""),
            "mntrees_menu_url":store.get("menu_url",""),
            "existing_exact_sku_count":len(exact) if confirmed_store else 0,
            "same_sku_anywhere_in_mntrees":len(global_matches),
            "same_store_strain_different_offer_count":len(same_store_strain),
            "existing_matching_offer_ids":"; ".join(str(o.get("id","")) for o in exact[:5]) if confirmed_store else "",
            "first_party_product_url_verified":"NO",
            "live_price_verified":"NO",
            "import_status":"NOT_READY_FOR_IMPORT",
            **row,
        })
    OUT.mkdir(parents=True,exist_ok=True)
    fields=list(results[0])
    with (OUT/"all_367_catalog_comparison.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(results)
    for status,filename in (
        ("existing_same_store_sku","already_on_site.csv"),
        ("new_sku_at_confirmed_store_needs_first_party_verification","new_at_confirmed_store.csv"),
        ("probable_existing_sku_store_needs_review","possible_duplicates.csv"),
        ("possible_new_sku_store_identity_needs_review","store_review.csv"),
        ("store_unresolved_no_import","unresolved.csv")):
        with (OUT/filename).open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
            w.writeheader();w.writerows(x for x in results if x["comparison_status"]==status)
    report={
       "input_count":len(candidates),"batch_counts":dict(batch_counts),"catalog_offer_count":len(offers),
       "status_counts":dict(statuses),
       "confirmed_duplicate_count":statuses["existing_same_store_sku"],
       "new_at_matched_store_needs_menu_and_price_verification":statuses["new_sku_at_confirmed_store_needs_first_party_verification"],
       "still_requires_store_identity_review":statuses["probable_existing_sku_store_needs_review"]+statuses["possible_new_sku_store_identity_needs_review"]+statuses["store_unresolved_no_import"],
       "ready_to_import_now":0,
       "publication_allowed":False,
       "comparison_method":"Canonical brand, strain, category and actual grams at uniquely identified physical store",
       "notes":["First-party product link, current price and permissions unavailable in THC pricing feed",
                "Catalog comparison is against currently built GitHub main snapshot, not independently verified browser live stock",
                "Source labels need actual package grams check before any price per gram publication"]
    }
    (OUT/"summary.json").write_text(json.dumps(report,indent=2)+"\n")
    print("THC 367 catalog comparison:",json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
