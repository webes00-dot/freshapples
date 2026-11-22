#!/usr/bin/env python3
"""Batch 3: obvious-only, deduplicated against immutable owner-approved batches."""
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"collector/data/thcminnesota-batch-3"
PRIOR=[
    (ROOT/"collector/data/thcminnesota-prior-1/obvious_candidates.csv", ROOT/"data/thc_keeper_approval.json"),
    (ROOT/"collector/data/thcminnesota-prior-2/new_obvious_candidates.csv", ROOT/"data/thc_keeper_batch2_approval.json"),
]

def load(path):
    with path.open(newline="",encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def clean(value):
    return re.sub(r"[^a-z0-9]+","",str(value or "").casefold())

def offer_key(row):
    return (str(row["source_dispensary_id"]),clean(row["category"]),
            clean(row["brand"]),clean(row["strain_match_candidate"]),
            str(float(row["size_g_from_product_label"])))

def direct_key(row):
    return (str(row["source_product_id"]),str(row["source_dispensary_id"]))

def main():
    prior=[]
    for source,manifest in PRIOR:
        approved=json.loads(manifest.read_text())
        if hashlib.sha256(source.read_bytes()).hexdigest()!=approved["sha256"]:
            raise ValueError("Prior approved snapshot checksum mismatch: "+str(source))
        rows=load(source)
        if len(rows)!=approved["expected_count"] or dict(Counter(x["category"] for x in rows))!=approved["category_counts"]:
            raise ValueError("Prior approval counts changed: "+str(source))
        prior.extend(rows)
    known_direct={direct_key(x) for x in prior}
    known_offer={offer_key(x) for x in prior}
    source=OUT/"obvious_candidates.csv"
    candidates=load(source) if source.exists() else []
    kept=[];duplicates=[]
    within_direct=set();within_offer=set()
    for row in candidates:
        if (row["triage"]!="obvious_three_fields_review" or not row.get("brand")
            or not row.get("strain_match_candidate")
            or row.get("size_evidence") not in ("single_explicit_grams","explicit_total")
            or float(row.get("size_g_from_product_label") or 0)<=0):
            raise ValueError("Non-obvious record in candidate file")
        direct=direct_key(row);signature=offer_key(row)
        if not all(direct):
            raise ValueError("Missing source identity")
        if (direct in known_direct or signature in known_offer
                or direct in within_direct or signature in within_offer):
            duplicates.append({**row,"batch_3_reason":"previously_approved_or_repeated"})
        else:
            kept.append({**row,"batch_3_reason":"new_obvious_candidate_for_review"})
        within_direct.add(direct);within_offer.add(signature)
    for filename,rows in (("new_obvious_candidates.csv",kept),("already_seen.csv",duplicates)):
        fields=list(candidates[0])+["batch_3_reason"] if candidates else ["batch_3_reason"]
        with (OUT/filename).open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=fields)
            writer.writeheader();writer.writerows(rows)
    result={
        "batch":3,"pricing_offsets":[600,700,800],"per_category_requested":300,
        "prior_owner_approved_rows":len(prior),"obvious_candidates_scanned":len(candidates),
        "new_obvious_candidates":len(kept),"already_seen_or_repeated":len(duplicates),
        "by_category":dict(Counter(x["category"] for x in kept)),
        "status":"REVIEW_ONLY_NOT_PUBLISHED",
        "publication_allowed":False,
        "notes":["Historical menu observations are not confirmed live stock",
                 "First-party price, storefront and source rights must be verified before publication"]
    }
    (OUT/"batch_3_summary.json").write_text(json.dumps(result,indent=2)+"\n")
    print("Batch 3:",json.dumps(result,sort_keys=True))

if __name__=="__main__":main()
