#!/usr/bin/env python3
"""Build a read-only runtime snapshot from the approved master workbook."""
import argparse
import json
import os
from collections import defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile


RANGES = {
    "Retailer Master": "A:X",
    "Brand Master": "A:B",
    "Strain Master": "A:B",
    "Entity Aliases": "A:E",
}
APPROVED_ACTIONS = {"normalize", "canonical", "merge"}


class WorkbookAccessError(Exception):
    """A workbook access failure that is safe to report in a public run."""


def google_api_failure(status, payload):
    details = payload.get("error", {}).get("details", [])
    if any(entry.get("reason") == "SERVICE_DISABLED" for entry in details):
        return "sheets_api_disabled"
    return f"google_http_{status}"


def read_workbook(workbook_id):
    from google.auth.exceptions import GoogleAuthError
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2.service_account import Credentials
    from requests.exceptions import RequestException

    try:
        auth = Credentials.from_service_account_info(
            json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]),
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
        )
    except (GoogleAuthError, KeyError, TypeError, ValueError):
        raise WorkbookAccessError("invalid_service_account_json") from None
    with AuthorizedSession(auth) as session:
        try:
            response = session.get(
                f"https://sheets.googleapis.com/v4/spreadsheets/{workbook_id}/values:batchGet",
                params={
                    "ranges": [f"'{tab}'!{columns}" for tab, columns in RANGES.items()],
                    "valueRenderOption": "UNFORMATTED_VALUE",
                },
                timeout=45,
            )
        except GoogleAuthError:
            raise WorkbookAccessError("token_exchange_failed") from None
        except RequestException:
            raise WorkbookAccessError("google_network_error") from None
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if not response.ok:
        raise WorkbookAccessError(google_api_failure(response.status_code, payload))
    return payload


def records(tabs, tab, *columns, optional=()):
    headers, *body = tabs[tab]
    missing = set(columns) - set(headers)
    if missing:
        raise ValueError(f"{tab} is missing columns: {', '.join(sorted(missing))}")
    indexes = [headers.index(name) if name in headers else None for name in (*columns, *optional)]
    for row in body:
        yield tuple(str(row[i]).strip() if i is not None and i < len(row) and row[i] is not None else ""
                    for i in indexes)


def approved_aliases(entries, canonical_names, entity):
    names = {name.casefold(): name for name in canonical_names}
    owners = defaultdict(set)
    spellings = defaultdict(set)
    aliases = {}
    for alias, target in entries:
        if not alias:
            continue
        canonical = names.get(target.casefold())
        if not canonical:
            raise ValueError(f"Approved {entity} alias has no canonical target: {alias}")
        owners[alias.casefold()].add(canonical)
        spellings[alias.casefold()].add(alias)
    conflicts = []
    for alias, targets in owners.items():
        if alias in names:
            targets.add(names[alias])
        if len(targets) > 1:
            conflicts.append({"entity": entity, "alias": alias, "targets": sorted(targets)})
        elif alias not in names:
            canonical, = targets
            aliases.update(dict.fromkeys(sorted(spellings[alias]), canonical))
    return aliases, conflicts


def make_snapshot(values, workbook_id):
    if values.get("spreadsheetId") != workbook_id:
        raise ValueError("Input values do not belong to the configured master workbook")
    tabs = {
        entry["range"].split("!", 1)[0].strip("'"): entry["values"]
        for entry in values["valueRanges"]
    }
    if any(not tabs.get(tab) for tab in RANGES):
        raise ValueError("One or more master tabs returned no values")

    retailers = []
    retailer_ids = set()
    for license_id, legal, display, address, map_address, menu, override, website, platform, location, fallback in records(
        tabs, "Retailer Master", "License ID", "Retailer / legal name",
        "Store display name (YOUR CORRECTION)", "Address on record",
        "Map address (YOUR CORRECTION)", "Existing menu URL",
        "Menu URL (YOUR CORRECTION)", "Website URL",
        optional=("Menu platform", "Platform location ID", "Fallback menu URL"),
    ):
        if not license_id:
            continue
        if license_id in retailer_ids or not legal or not address:
            raise ValueError(f"Invalid or duplicate retailer master entry: {license_id}")
        retailer_ids.add(license_id)
        retailers.append({
            "id": license_id, "name": display or legal, "legal_name": legal,
            "address": address, "map_address": map_address,
            "menu_url": override or menu, "website_url": website,
            "menu_platform": platform.casefold(), "platform_location_id": location,
            "fallback_menu_url": fallback,
        })

    brand_rows = [(observed, corrected or observed) for observed, corrected in records(
        tabs, "Brand Master", "Brand as observed", "Canonical brand (YOUR CORRECTION)",
    ) if observed]
    strain_rows = [(canonical, alias) for canonical, alias in records(
        tabs, "Strain Master", "Canonical strain", "Alias / retailer spelling",
    ) if canonical]
    brand_names = list(dict.fromkeys(canonical for _, canonical in brand_rows))
    strain_names = list(dict.fromkeys(canonical for canonical, _ in strain_rows))
    if not all((retailers, brand_names, strain_names)):
        raise ValueError("Master workbook returned an empty identity or retailer list")

    registry = defaultdict(list)
    for entity, alias, canonical, action in records(
        tabs, "Entity Aliases", "Entity type", "Observed name / alias", "Canonical name", "Action",
    ):
        if action.casefold() in APPROVED_ACTIONS:
            registry[entity.casefold()].append((alias, canonical))
    brand_aliases, brand_conflicts = approved_aliases(
        brand_rows + registry["brand"], brand_names, "brand",
    )
    strain_aliases, strain_conflicts = approved_aliases(
        [(alias, canonical) for canonical, alias in strain_rows] + registry["strain"],
        strain_names, "variety",
    )
    by_brand = defaultdict(list)
    for alias, canonical in brand_aliases.items():
        by_brand[canonical].append(alias)
    return {
        "schema_version": 1,
        "spreadsheet_id": workbook_id,
        "retailers": retailers,
        "brands": [{"name": name, "aliases": by_brand[name]} for name in brand_names],
        "strain_master": {"canonical_strains": strain_names, "approved_aliases": strain_aliases},
        "alias_conflicts": brand_conflicts + strain_conflicts,
    }


def load_snapshot(path):
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    if snapshot.get("schema_version") != 1 or not snapshot.get("spreadsheet_id"):
        raise ValueError("Unsupported or incomplete master snapshot")
    workbook_id = os.environ.get("MNTREES_MASTER_SHEET_ID")
    if workbook_id and snapshot["spreadsheet_id"] != workbook_id:
        raise ValueError("Snapshot does not belong to the configured master workbook")
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook-id", default=os.environ.get("MNTREES_MASTER_SHEET_ID"))
    parser.add_argument("--values-json", type=Path, help="Use a saved Sheets batchGet response")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.workbook_id:
        parser.error("set MNTREES_MASTER_SHEET_ID or pass --workbook-id")
    try:
        values = (json.loads(args.values_json.read_text(encoding="utf-8"))
                  if args.values_json else read_workbook(args.workbook_id))
        snapshot = make_snapshot(values, args.workbook_id)
    except WorkbookAccessError as exc:
        raise SystemExit(f"Workbook connection reason: {exc}") from None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.output.parent, delete=False) as pending:
        json.dump(snapshot, pending, ensure_ascii=False)
        pending.write("\n")
    Path(pending.name).replace(args.output)
    print(json.dumps({
        "retailers": len(snapshot["retailers"]),
        "brands": len(snapshot["brands"]),
        "canonical_varieties": len(snapshot["strain_master"]["canonical_strains"]),
        "alias_conflicts": len(snapshot["alias_conflicts"]),
    }))


if __name__ == "__main__":
    main()
