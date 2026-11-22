#!/usr/bin/env python3
"""Batch-2 triage: preserve only distinct, obvious size/brand/strain offers.

Never auto-publish historical or unverified third-party menu observations.
"""
import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PREVIOUS=ROOT/"collector/data/thcminnesota-prior/obvious_candidates.csv"
BATCH=ROOT/"collector/data/thcminnesota-batch-2"
APPROVAL=ROOT/"data/thc_keeper_approval.json"

def read_csv(path):
    with path.open(newline="",encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def norm(s):
    return re.sub(r"[^a-z0-9]+","",str(s or "").casefold())

def signature(row):
    # Known source identity first; same brand/strain/size/category/store is also one offer
    # regardless of whether two observations have different timestamps or prices.
    return (str(row.get("source_dispensary_id") or ""),
            norm(row.get("category")),norm(row.get("brand")),
            norm(row.get("strain_match_candidate")),
            str(float(row.get("size_g_from_product_label") or 0)))

def main():
    prior=read_csv(PREVIOUS)
    approved=json.loads(APPROVAL.read_text())
    if len(prior)!=approved["expected_count"]:
        raise ValueError("First-batch comparison source does not match approval count")
    expected=Counter(approved["category_counts"])
    observed=Counter(x["category"] for x in prior)
    if observed!=expected: raise ValueError("First-batch category counts differ")
    batch=read_csv(BATCH/"obvious_candidates.csv") if (BATCH/"obvious_candidates.csv").exists() else []
    seen_ids={(r["source_product_id"],r["source_dispensary_id"]) for r in prior}
    seen_signatures={signature(r) for r in prior}
    kept=[];duplicate=[];within=set()
    for row in batch:
        if row["triage"]!="obvious_three_fields_review" or not row.get("brand") or not row.get("strain_match_candidate"):
            raise ValueError("Non-obvious product in obvious candidates")
        grams=float(row.get("size_g_from_product_label") or 0)
        if grams<=0 or row.get("size_evidence") not in ("single_explicit_grams","explicit_total"):
            raise ValueError("Unqualified weight")
        direct=(row["source_product_id"],row["source_dispensary_id"])
        sig=signature(row)
        if direct in seen_ids or sig in seen_signatures or direct in within or sig in within:
            duplicate.append({**row,"batch_2_reason":"already_covered_or_repeated_observation"})
        else:
            kept.append({**row,"batch_2_reason":"new_obvious_candidate_pending_verification"})
        within.add(direct);within.add(sig)
    for name,rows in (("new_obvious_candidates.csv",kept),("already_seen.csv",duplicate)):
        fields=list(batch[0])+["batch_2_reason"] if batch else ["batch_2_reason"]
        with (BATCH/name).open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    report={"batch":2,"pricing_offsets":[300,400,500],"per_category_requested":300,
            "prior_owner_approved_rows":len(prior),
            "obvious_candidates_scanned":len(batch),
            "new_obvious_candidates":len(kept),
            "observations_already_seen_or_repeated":len(duplicate),
            "by_category":dict(Counter(r["category"] for r in kept)),
            "status":"REVIEW_ONLY_NOT_PUBLISHED",
            "dedupe_policy":"Matching source product/store IDs or same store/brand/strain/grams/category",
            "limitations":["Not a current-stock check","Retailer names and license identities still need verification",
                           "Independent permission and first-party price verification required"]}
    (BATCH/"batch_2_summary.json").write_text(json.dumps(report,indent=2)+"\n")
    print("Batch 2:",json.dumps(report,sort_keys=True))

if __name__=="__main__":
    main()
