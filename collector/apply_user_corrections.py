#!/usr/bin/env python3
"""Apply user-reviewed corrections to source-linked catalog IDs without overwriting source evidence."""
import json
from pathlib import Path
from brand_aliases import canonical_brand

ROOT=Path(__file__).resolve().parents[1]

def apply(listings, config):
    mapping=config["by_listing_id"]
    changed=0
    found=set()
    for row in listings:
        item=mapping.get(str(row.get("id")))
        if not item:
            continue
        found.add(str(row["id"]))
        if "strain" in item:
            if row.get("strain")!=item["strain"] or row.get("product_family")!=item["strain"]:
                row["strain"]=item["strain"]
                row["product_family"]=item["strain"]
                row["product_family_decision"]="user_reviewed_exact_listing"
                changed+=1
        if "brand" in item:
            if row.get("brand")!=canonical_brand(item["brand"]) or row.get("brand_family")!=canonical_brand(item["brand"]):
                row["brand"]=canonical_brand(item["brand"])
                row["brand_family"]=canonical_brand(item["brand"])
                row["brand_family_decision"]="user_reviewed_exact_listing"
                changed+=1
        if "category" in item:
            if row.get("category")!=item["category"]:
                row["category"]=item["category"]
                row["category_review_decision"]="reviewed_source_product_type"
                changed+=1
        if "display_size_g" in item:
            # The source reports 0.7g and user reports 0.75g;
            # preserve the actual source measurement instead of silently rewriting.
            row["user_suggested_size_g"]=item["display_size_g"]
            row["size_verification_note"]=item.get("note","")
    return changed,len(found),len(mapping)

def main():
    catalog=ROOT/"data/listings.json"
    config=json.loads((ROOT/"collector/config/user_product_corrections.json").read_text(encoding="utf-8"))
    rows=json.loads(catalog.read_text(encoding="utf-8"))
    changes,found,total=apply(rows,config)
    if changes or any("user_suggested_size_g" in r for r in rows):
        before=catalog.read_text(encoding="utf-8")
        after=json.dumps(rows,indent=2,ensure_ascii=False)+"\n"
        if before!=after:
            catalog.write_text(after,encoding="utf-8")
    print(json.dumps({"changed_fields":changes,"matched_ids":found,"corrections":total,"records":len(rows)}))

if __name__=="__main__":
    main()
