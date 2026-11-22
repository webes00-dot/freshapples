#!/usr/bin/env python3
"""Restore a dated MNtrees catalog snapshot from private Cloudflare KV into NEW D1.

The restored data never originates from old repositories or legacy databases.
Requires CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, snapshot KV ID.
By default this script is read-only; --apply requires explicit --target-db-id.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

PRODUCTION_DATABASE_IDS = {
    "457785f2-ab73-4858-b524-ba613a2b5388",  # current catalog
    "9d62cb7c-0f35-4e66-a47f-9cb3cb465a49",  # reviews
    "369472cb-6f59-415f-97ed-d3d955839ad1",  # preview reviews
}
DEFAULT_NAMESPACE = "760f5a98a3dd4cb688e5c52bb357403e"


def request(method: str, url: str, token: str, data=None):
    body = None if data is None else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method=method,
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/json",
                 **({"Content-Type": "application/json"} if body is not None else {})},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read()
    if "/values/" in url:
        return json.loads(raw)
    response = json.loads(raw)
    if not response.get("success"):
        raise RuntimeError(response.get("errors", response))
    return response["result"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", default="2026-11-22")
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    parser.add_argument("--target-db-id", help="EXISTING isolated D1 database UUID; never production")
    parser.add_argument("--apply", action="store_true", help="Write only after explicit target and safety checks")
    args = parser.parse_args()
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not account or not token:
        parser.error("CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN required")
    if args.apply and not args.target_db_id:
        parser.error("--target-db-id is required for --apply")
    if args.target_db_id in PRODUCTION_DATABASE_IDS:
        parser.error("Refusing to use a known production database ID")
    api = f"https://api.cloudflare.com/client/v4/accounts/{account}"
    prefix = f"{args.snapshot}/d1/catalog"
    def kv_value(path: str):
        encoded = urllib.parse.quote(f"{prefix}/{path}", safe="/")
        return request("GET", f"{api}/storage/kv/namespaces/{args.namespace}/values/{encoded}", token)
    manifest = kv_value("manifest.json")
    tables = manifest["counts"]
    assert sum(x["rows"] for x in tables) > 0, "Empty or invalid snapshot"
    print(f"Snapshot {args.snapshot}: {len(tables)} tables; {sum(x['rows'] for x in tables)} rows")
    if not args.apply:
        print("Dry-run only; no database writes. Use --apply --target-db-id on an isolated empty D1 database.")
        return
    url = f"{api}/d1/database/{args.target_db_id}/query"
    def sql(statement, params=None):
        payload = {"sql": statement}
        if params is not None:
            payload["params"] = params
        return request("POST", url, token, payload)
    has_tables = sql("SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='_cf_KV'")[0]["results"][0]["n"]
    if has_tables:
        raise RuntimeError("Refusing to overwrite nonempty schema. Create a new empty D1 first.")
    for item in manifest["schema"]:
        if item["type"] == "table":
            sql(item["sql"])
    for item in manifest["schema"]:
        if item["type"] == "index":
            sql(item["sql"])
    names = [v["table"] for v in tables]
    # Load parent tables before dependent products.
    if "products" in names:
        names.remove("products")
        names.append("products")
    counts = {v["table"]: v for v in tables}
    for name in names:
        meta = counts[name]
        for chunk in range(meta["parts"]):
            rows = kv_value(f"{name}/{chunk:04d}.json")["rows"]
            if not rows:
                continue
            columns = list(rows[0])
            quoted = ",".join('"' + c.replace('"', '""') + '"' for c in columns)
            fields = ",".join("json_extract(value, '$." + c + "')" for c in columns)
            statement = f'INSERT OR REPLACE INTO "{name}" ({quoted}) SELECT {fields} FROM json_each(?)'
            sql(statement, [json.dumps(rows, separators=(",", ":"))])
        actual = sql(f'SELECT COUNT(*) AS n FROM "{name}"')[0]["results"][0]["n"]
        if actual != meta["rows"]:
            raise RuntimeError(f"Restore row mismatch: {name}: {actual} != {meta['rows']}")
        print(f"Verified {name}: {actual} records")
    violations = sql("PRAGMA foreign_key_check")[0]["results"]
    if violations:
        raise RuntimeError(f"Foreign key violations: {violations[:5]}")
    print("RESTORE VERIFIED: every table count matches; zero foreign-key violations")


if __name__ == "__main__":
    main()