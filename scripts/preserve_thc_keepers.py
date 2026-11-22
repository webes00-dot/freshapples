#!/usr/bin/env python3
"""Freeze owner-approved THC discovery list; do not publish unverified offers."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"data/thc_keeper_approval.json"
SRC=ROOT/"collector/data/thcminnesota-product-review/obvious_candidates.csv"
OUT=ROOT/"collector/data/thcminnesota-approved"
ALLOWED={"flower","pre-rolls","concentrates"}

def main():
    approval=json.loads(MANIFEST.read_text())
    source_bytes=SRC.read_bytes()
    digest=hashlib.sha256(source_bytes).hexdigest()
    if digest!=approval["sha256"]:
        raise ValueError("THC keeper file does not match approved snapshot; refusing promotion")
    rows=list(csv.DictReader(source_bytes.decode("utf-8").splitlines()))
    if len(rows)!=approval["expected_count"]:
        raise ValueError("Unexpected keeper count")
    counts=Counter(x["category"] for x in rows)
    if set(counts)-ALLOWED or dict(counts)!=approval["category_counts"]:
        raise ValueError("Category counts or types differ from approved snapshot")
    identities=set()
    for row in rows:
        key=(row["source_product_id"],row["source_dispensary_id"],row["observed_date"])
        if not all(key) or key in identities:
            raise ValueError("Duplicate or missing source identity")
        identities.add(key)
        if row.get("triage")!="obvious_three_fields_review" or not row.get("brand") or not row.get("strain_match_candidate"):
            raise ValueError("Unqualified candidate encountered")
        if not row.get("size_g_from_product_label") or float(row["size_g_from_product_label"])<=0:
            raise ValueError("Missing explicit positive package grams")
        if not row.get("source_weight_label") or row.get("size_evidence") not in ("single_explicit_grams","explicit_total"):
            raise ValueError("Unverified grams evidence")
    OUT.mkdir(parents=True,exist_ok=True)
    fields=list(rows[0])+["owner_approval","publication_status","verification_requirements"]
    with (OUT/"approved_for_verification.csv").open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in rows:
            writer.writerow({**row,"owner_approval":"2026-11-19: proceed to verification",
                             "publication_status":"NOT_PUBLISHABLE",
                             "verification_requirements":"storefront; grams; brand; strain; first-party menu and current price; rights; dedupe"})
    (OUT/"approval_manifest.json").write_text(json.dumps(approval,indent=2)+"\n")
    print("Owner-approved for verification:",len(rows),dict(counts))
    print("Publication remains prohibited until all verification gates pass.")

if __name__=="__main__": main()
