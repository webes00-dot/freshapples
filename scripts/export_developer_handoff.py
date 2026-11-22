#!/usr/bin/env python3
"""Deterministic internal developer handoff ZIP (tracked source + validated outputs).

No live accounts, credentials, .env, or untracked local material are packed.
The authoritative Google Sheet is included only if an explicitly exported
read-only workbook exists under exports/MNtrees_Master.xlsx.
"""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "release" / "MNtrees_Developer_Handoff.zip"
EXCLUDE = {".env", ".env.local", ".env.production", "service-account.json"}
SENSITIVE = (".pem", ".p12", ".pfx", ".key", ".kdbx", ".age")
ALLOWED_UNTRACKED = (
    "dist/data/catalog_build_report.json",
    "dist/data/strain_master_review.json",
    "dist/data/site-data.json",
    "reports/entity_reconciliation.json",
    "reports/release_quality.json",
    "reports/delimited_strain_review.json",
    "exports/MNtrees_Master.xlsx",
)


def allowed(rel):
    path = Path(rel)
    return (
        not any(p in EXCLUDE or p.startswith(".env") for p in path.parts)
        and not rel.lower().endswith(SENSITIVE)
        and not any(p in {".git", "__pycache__", ".venv", "node_modules"} for p in path.parts)
    )


def main():
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\x00")
    candidates = sorted(set(p for p in tracked if p and allowed(p))
                        | {p for p in ALLOWED_UNTRACKED if (ROOT / p).is_file()})
    if not candidates or not any(p == "scripts/build_catalog.py" for p in candidates):
        raise RuntimeError("Git tracked source missing; export not created")
    manifest = {
        "project": "MNtrees",
        "export_type": "full_versioned_source_and_derived_report_bundle",
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
        "authoritative_workbook": json.loads((ROOT/"config/authority.json").read_text())["spreadsheet"]["id"],
        "contains_native_master_workbook": "exports/MNtrees_Master.xlsx" in candidates,
        "files": {},
        "warning": "Source feeds are observations; successful ZIP creation does not confirm production sync or complete Sheets writeback.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=7) as zipout:
        for rel in candidates:
            source = ROOT / rel
            if source.is_symlink() or not source.is_file():
                continue
            payload = source.read_bytes()
            manifest["files"][rel] = hashlib.sha256(payload).hexdigest()
            zipout.writestr(rel, payload)
        zipout.writestr("DEVELOPER_EXPORT_MANIFEST.json", json.dumps(manifest, indent=2)+"\n")
    print("Developer export:", OUT)
    print("Files:", len(manifest["files"]), "Master workbook included:", manifest["contains_native_master_workbook"])


if __name__ == "__main__":
    main()
