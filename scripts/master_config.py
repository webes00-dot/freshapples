"""Single approved workbook and canonical paths for MNtrees pipeline consumers.

Do not duplicate the workbook ID in publisher, sync or enrichment scripts.
The JSON contract is reviewed alongside the editorial Google Sheet; this
module never authorizes writing to the Sheet.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_FILE = ROOT / "config" / "authority.json"


def authority():
    payload = json.loads(AUTHORITY_FILE.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported MNtrees authority registry")
    book = payload.get("spreadsheet", {})
    if not book.get("id") or not book.get("tabs", {}).get("strains"):
        raise ValueError("Missing approved MNtrees spreadsheet reference")
    return payload


def master_sheet_id():
    return authority()["spreadsheet"]["id"]


def master_tab(role):
    return authority()["spreadsheet"]["tabs"][role]
