#!/usr/bin/env python3
"""Normalize V2 raw evidence using only the shared identity rules engine.

Read-only. Does not alter captured evidence or publish catalog offers.
"""
import argparse
import json
import re
from urllib.parse import urlsplit
from collections import Counter, defaultdict
from pathlib import Path

from scanner_v2_observation import identity_input
from unified_scan_rules import infer_category, normalize_observation
from scanner_v2_elimination import rerank
from scanner_v2_master import load_snapshot

ROOT = Path(__file__).resolve().parents[1]


def corroborate_forms(rows):
    """Use only independently labeled, pack-specific offers as witnesses."""
    witnesses = defaultdict(lambda: defaultdict(list))
    def product_key(row):
        return row["brand"], row["strain"], row["package_g"], row["pack_count"]

    for row in rows:
        if row["identity_status"] != "ready" or not row["brand"] or not row["pack_count"]:
            continue
        explicit = infer_category(row["raw_title"], "", "", "")
        path = urlsplit(row["product_url"]).path
        if not explicit and re.search(r"/(?:products?|pdp)/", path, re.I):
            explicit = "Vape" if "/cartsvapes/" in path.lower() else infer_category("", row["product_url"])
        if explicit and explicit == row["category"]:
            witnesses[product_key(row)][explicit].append(row["observation_id"])

    for row in rows:
        reasons = row["identity_reasons"]
        if not row["brand"] or not row["pack_count"] or not reasons or not set(reasons) <= {"missing_type", "category_only_adapter_hint"}:
            continue
        matches = witnesses.get(product_key(row), {})
        if len(matches) == 1:
            form, ids = next(iter(matches.items()))
            row["category"] = form
            row["resolution_evidence"].update(category_basis="matched_brand_strain_weight_count",
                                              category_witness_ids=sorted(ids))
            row["resolution_evidence"].pop("category_hint", None)
            row.update(identity_status="ready", review_group="accepted", identity_reasons=[])


def reconcile(captured, strains, brands, approved_brands=None):
    normalized = []
    for obs in captured:
        first_pass = normalize_observation(identity_input(obs), strains, brands)
        parsed = rerank(first_pass, obs, strains, brands, approved_brands=approved_brands)
        normalized.append({
            "observation_id": obs["observation_id"],
            "evidence_sha256": obs["evidence_sha256"],
            "retailer_id": obs["retailer_id"],
            "source_kind": obs["source_kind"],
            "source_product_id": obs.get("source_product_id") or "",
            "variant_key": obs.get("variant_key") or "",
            "adapter": obs["adapter"],
            "source_url": obs["source_url"],
            "product_url": obs["product_url"],
            "raw_title": obs["raw_title"],
            "observed_at": obs["observed_at"],
            "product_line": parsed.get("product_line") or "",
            "review_group": ("excluded" if "non_target_category" in parsed["identity_reasons"] else
                             "accepted" if parsed["identity_status"] == "ready" else
                             "scope_review" if not parsed.get("category") else "identity_hold"),
            "brand": parsed.get("brand") or "",
            "strain": parsed.get("strain") or "",
            "category": parsed.get("category") or "",
            "package_g": parsed.get("package_g"),
            "pack_count": parsed.get("pack_count"),
            "price": obs.get("price"),
            "identity_status": parsed.get("identity_status"),
            "first_pass_status": first_pass.get("identity_status"),
            "first_pass_reasons": first_pass.get("identity_reasons") or [],
            "resolution_pass": parsed.get("resolution_pass"),
            "resolution_evidence": parsed.get("resolution_evidence") or {},
            "identity_reasons": parsed.get("identity_reasons") or [],
            "identity_evidence": parsed.get("identity_evidence"),
            "stock_status": "not_verified",
        })
    corroborate_forms(normalized)
    return normalized


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(ROOT / "reports/scanner_v2_captured.json"))
    parser.add_argument("--output", default=str(ROOT / "reports/scanner_v2_reconciled.json"))
    parser.add_argument("--master-snapshot", type=Path)
    args = parser.parse_args()
    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if args.master_snapshot:
        master = load_snapshot(args.master_snapshot)
        strains = master["strain_master"]
        brands = approved_brands = master["brands"]
    else:
        strains = json.loads((ROOT / "data/strain_master.json").read_text(encoding="utf-8"))
        brands = json.loads((ROOT / "data/brands.json").read_text(encoding="utf-8"))
        approved_index = json.loads((ROOT / "data/brand_master_index_v2.json").read_text(encoding="utf-8"))
        authority = json.loads((ROOT / "config/authority.json").read_text(encoding="utf-8"))
        if strains.get("source_spreadsheet_id") != authority["spreadsheet"]["id"]:
            raise ValueError("Stale strain master authority")
        if approved_index.get("authority_spreadsheet_id") != authority["spreadsheet"]["id"]:
            raise ValueError("Brand approval index does not match canonical workbook")
        approved_brands = approved_index["brands"]
    observations = source.get("observations") or []
    rows = reconcile(observations, strains, brands, approved_brands=approved_brands)
    counts = Counter(x["identity_status"] for x in rows)
    first = Counter(x["first_pass_status"] for x in rows)
    gains = sum(x["first_pass_status"] != "ready" and x["identity_status"] == "ready" for x in rows)
    report = {
        "review_groups": dict(Counter(x["review_group"] for x in rows)),
        "first_pass_reheld": sum(x["first_pass_status"] == "ready" and x["identity_status"] != "ready" for x in rows),
        "schema_version": 2,
        "purpose": "v2_shadow_identity_reconciliation_not_publication",
        "observations": len(rows),
        "approved_brand_names": len(approved_brands),
        "first_pass_ready": first.get("ready", 0),
        "second_pass_new_ready": gains,
        "ready": counts.get("ready", 0),
        "needs_review": counts.get("needs_review", 0),
        "rows": rows,
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}))


if __name__ == "__main__":
    main()
