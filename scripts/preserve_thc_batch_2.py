#!/usr/bin/env python3
"""Lock the second owner-approved THC Minnesota batch for verification."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"data/thc_keeper_batch2_approval.json"
SOURCE=ROOT/"collector/data/thcminnesota-batch-2/new_obvious_candidates.csv"
OUT=ROOT/"collector/data/thcminnesota-batch-2-approved"

def main():
    approval=json.loads(MANIFEST.read_text())
    content=SOURCE.read_bytes()
    if hashlib.sha256(content).hexdigest()!=approval["sha256"]:
        raise ValueError("Batch 2 owner-approved source digest does not match")
    with SOURCE.open(newline="",encoding="utf-8-sig") as f:
        rows=list(csv.DictReader(f))
    if len(rows)!=approval["expected_count"] or dict(Counter(r["category"] for r in rows))!=approval["category_counts"]:
        raise ValueError("Wrong approved Batch 2 row count or categories")
    seen=set()
    for row in rows:
        key=(row.get("source_product_id"),row.get("source_dispensary_id"))
        if not all(key) or key in seen:
            raise ValueError("Missing or repeated product/store identity")
        seen.add(key)
        if row.get("batch_2_reason")!="new_obvious_candidate_pending_verification":
            raise ValueError("Unapproved Batch 2 candidate")
        if row.get("triage")!="obvious_three_fields_review" or not row.get("brand") or not row.get("strain_match_candidate"):
            raise ValueError("Brand or obvious canonical strain missing")
        if row.get("size_evidence") not in ("single_explicit_grams","explicit_total") or float(row.get("size_g_from_product_label") or 0)<=0:
            raise ValueError("Unverified size")
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/"approved_for_verification.csv").open("w",newline="",encoding="utf-8") as f:
        fields=list(rows[0])+["owner_approval","publication_status","verification_requirements"]
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in rows:
            writer.writerow({**row,"owner_approval":"2026-11-19: proceed to final verification",
                             "publication_status":"NOT_PUBLISHABLE",
                             "verification_requirements":"storefront; weight; brand; strain; first-party menu/price; rights; catalog dedupe"})
    (OUT/"approval_manifest.json").write_text(json.dumps(approval,indent=2)+"\n")
    print("Batch 2 approved for verification:",len(rows),dict(Counter(r["category"] for r in rows)))
    print("Nothing published; verification gate remains enforced")

if __name__=="__main__":
    main()
