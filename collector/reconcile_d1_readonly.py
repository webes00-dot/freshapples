#!/usr/bin/env python3
"""Read-only comparison of staging scanner offers against current Cloudflare D1.
Never writes catalog rows, review queues, schema, or production assets.
Requires CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID and D1 catalog ID.
"""
import datetime
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUT = ROOT / "collector/data/candidate_products.json"
OUTPUT = ROOT / "collector/data/d1_reconciliation.json"
DB_ID = os.getenv("MNTREES_CATALOG_D1_ID", "457785f2-ab73-4858-b524-ba613a2b5388")


def query(sql):
    token = os.environ["CLOUDFLARE_API_TOKEN"]
    account = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/d1/database/{DB_ID}/query"
    body = json.dumps({"sql": sql}).encode()
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "MNtrees-read-only-reconcile/1.0"})
    with urllib.request.urlopen(request, timeout=40) as response:
        payload = json.load(response)
    if not payload.get("success"):
        raise RuntimeError("Cloudflare D1 read failed: " + str(payload.get("errors", []))[:300])
    result = payload.get("result") or []
    if not result or not result[0].get("success", False):
        raise RuntimeError("Cloudflare D1 query returned no successful result")
    return result[0].get("results") or []


def source_identity(row):
    # The collector produces a stable, source-derived id where available.
    # Name-only or URL-only guesses must not silently match or alter catalog rows.
    source_id = str(row.get("source_id") or "").strip()
    offer_id = str(row.get("id") or "").strip()
    if source_id:
        return source_id
    return offer_id


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    report = {"checked_at": stamp, "read_only": True, "published": False,
              "database_id": DB_ID, "status": "not_checked",
              "counts": {}, "matches": [], "unmatched": [], "ambiguous": [],
              "employee_edited": [], "errors": []}
    try:
        candidates = json.loads(INPUT.read_text(encoding="utf-8"))
        if not isinstance(candidates, list):
            raise ValueError("Scan candidates must be an array")
        products = query("SELECT id,source_key,retailer_id,updated_at FROM products")
        edits = query("SELECT entity_type,entity_key,action,logged_at FROM admin_audit_log")
        edited = set()
        for row in edits:
            if row.get("action") in ("update", "create", "delete"):
                edited.add((str(row.get("entity_type", "")).lower(), str(row.get("entity_key", ""))))
        index = {}
        for row in products:
            # D1 source_key format is 'Product Catalog - Edit Here:<source identity>'.
            # Exact suffix matches are candidates ONLY, never sufficient for writes.
            source_key = str(row.get("source_key") or "")
            suffix = source_key.split(":", 1)[1] if ":" in source_key else ""
            if suffix:
                index.setdefault(suffix, []).append(row)
        for candidate in candidates:
            identity = source_identity(candidate)
            key = {"offer_id": str(candidate.get("id", "")),
                   "source_id": str(candidate.get("source_id", "")),
                   "retailer": str(candidate.get("retailer", "")),
                   "store_id": str(candidate.get("store_id", ""))}
            if not identity:
                report["unmatched"].append({**key, "reason": "missing_stable_identity"})
                continue
            rows = index.get(identity) or []
            if not rows:
                report["unmatched"].append({**key, "reason": "not_in_d1_exact_source_key"})
                continue
            if len(rows) != 1:
                report["ambiguous"].append({**key, "reason": "multiple_exact_source_keys",
                                            "d1_keys": [r["source_key"] for r in rows]})
                continue
            record = rows[0]
            match = {**key, "d1_id": record["id"], "d1_key": record["source_key"],
                     "d1_retailer_id": record["retailer_id"],
                     "verification": "source_key_only_retailer_not_verified"}
            # No retail crosswalk is yet proven: even exact source IDs are not write-safe.
            if any((entity, str(record["id"])) in edited or
                   (entity, str(record["source_key"])) in edited
                   for entity in ("products", "product")):
                match["employee_edit_protected"] = True
                report["employee_edited"].append(match)
            else:
                report["matches"].append(match)
        report["status"] = "read_only_checked"
        report["counts"] = {"candidate_offers": len(candidates),
                            "existing_products": len(products),
                            "audit_events": len(edits),
                            "matched_source_keys_only": len(report["matches"]),
                            "employee_edited": len(report["employee_edited"]),
                            "ambiguous": len(report["ambiguous"]),
                            "unmatched": len(report["unmatched"])}
        report["writeback_authorized"] = False
        report["writeback_blockers"] = [
            "Canonical retailer crosswalk not verified",
            "Existing employee edits must have field-level preservation",
            "Candidate source identity and product variants require validation",
            "No automatic D1 writes are authorized"]
    except Exception as exc:
        report["status"] = "blocked"
        # Do not include API headers or any credentials in diagnostics.
        reason = f"{type(exc).__name__}: {str(exc)}"
        if "CLOUDFLARE_API_TOKEN" in reason:
            reason = "Cloudflare token is missing or not configured"
        report["errors"].append(reason[:350])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "counts": report["counts"],
                      "errors": report["errors"], "published": False}))
    return 0 if report["status"] == "read_only_checked" else 2


if __name__ == "__main__":
    sys.exit(main())
