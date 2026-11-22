#!/usr/bin/env python3
"""Compare third-party dispensary directory against MNtrees; report only.

Never inserts a store, replaces a master, or changes the published catalog.
"""
import csv
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "collector/data/thcminnesota-dispensary-review"
API = "https://thcminnesota.com/api/v1/dispensaries"
LIMIT = 1000

def normalize(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())

def license_root(value):
    # A parent/operator license without a location suffix is not a unique location.
    return str(value or "").strip().upper()

def retrieve(token):
    rows = []
    total = None
    for offset in range(0, 10000, LIMIT):
        req = urllib.request.Request(
            API + "?" + urllib.parse.urlencode({"limit": LIMIT, "offset": offset}),
            headers={"Authorization": "Bearer " + token,
                     "Accept": "application/json",
                     "User-Agent": "MNtrees-Dispensary-Discovery/1.0"})
        with urllib.request.urlopen(req, timeout=35) as response:
            doc = json.load(response)
        page = doc.get("data")
        if not isinstance(page, list):
            raise ValueError("Unexpected dispensary response schema")
        total = doc.get("total", total)
        rows.extend(page)
        if len(page) < LIMIT or (isinstance(total, int) and len(rows) >= total):
            break
    if isinstance(total, int) and len(rows) < total:
        raise ValueError("Incomplete API pagination; refusing partial comparison")
    return rows, total

def compare(external, existing):
    exact = {}
    names = {}
    for row in existing:
        for key in (row.get("id"), row.get("license_id")):
            if key:
                exact.setdefault(license_root(key), []).append(row)
        namekey = normalize(row.get("name")) + "|" + normalize(row.get("address"))
        names.setdefault(namekey, []).append(row)
    output = []
    for row in external:
        if not row.get("is_active"):
            continue
        key = license_root(row.get("license_number"))
        # External licenses may identify the parent authorization, not the store.
        matches = exact.get(key, []) if key else []
        matched_by = "exact_license" if matches else ""
        if not matches:
            address_key = normalize(row.get("name")) + "|" + normalize(row.get("address"))
            matches = names.get(address_key, [])
            if matches:
                matched_by = "exact_name_address"
        status = "already_listed" if matches else "review_candidate"
        output.append({
            "status": status, "match_basis": matched_by,
            "external_id": row.get("id"), "name": row.get("name"),
            "address": row.get("address"), "city": row.get("city"),
            "zip": row.get("zip"), "license_number": row.get("license_number"),
            "menu_platform": row.get("menu_platform"),
            "last_scraped_at": row.get("last_scraped_at"),
            "matching_mntrees_ids": sorted({str(x.get("id")) for x in matches}),
            "review_note": ("License may be operator-level; verify specific storefront, "
                            "active MN license, menu URL and product coverage before import"),
        })
    return output

def main():
    token = os.getenv("THCMINNESOTA_API_KEY", "").strip()
    if not token:
        raise SystemExit("Missing THCMINNESOTA_API_KEY")
    external, total = retrieve(token)
    existing = json.loads((ROOT / "data/retailer_locations.json").read_text())
    findings = compare(external, existing)
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"source": API, "checked_at": datetime.now(timezone.utc).isoformat(),
              "api_reported_total": total, "api_rows_fetched": len(external),
              "active_rows_reviewed": len(findings),
              "already_listed": sum(r["status"] == "already_listed" for r in findings),
              "review_candidates": sum(r["status"] == "review_candidate" for r in findings),
              "matching_policy": "Exact full license OR exact normalized name+address only; no fuzzy auto-merge",
              "candidates": findings}
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    with (OUT / "candidates.csv").open("w", newline="") as fh:
        fields = ["status", "name", "address", "city", "zip", "license_number",
                  "menu_platform", "last_scraped_at", "external_id",
                  "match_basis", "matching_mntrees_ids", "review_note"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in findings:
            if row["status"] == "review_candidate":
                writer.writerow({k: "; ".join(row[k]) if isinstance(row[k], list) else row[k] for k in fields})
    print("API reported:", total, "Fetched:", len(external),
          "Listed:", report["already_listed"], "Review:", report["review_candidates"])
    print("No changes to retailer master or public site.")

if __name__ == "__main__":
    main()
