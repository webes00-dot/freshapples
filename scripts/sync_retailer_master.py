#!/usr/bin/env python3
"""Sync authoritative Retailer Master into the public directory and scan targets.
Requires GOOGLE_SERVICE_ACCOUNT_JSON with spreadsheet read access.
Never replace existing published files on a failed or incomplete fetch.
"""
import json, os, pathlib, sys
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

# Reviewed 2026-11-20 consolidated working master. Fail closed if service account
# cannot read the new workbook; do not silently revert to the old workbook.
from master_config import master_sheet_id, master_tab
CANONICAL_MASTER_SHEET_ID=master_sheet_id()
SHEET_ID=os.environ.get("MNTREES_MASTER_SHEET_ID", CANONICAL_MASTER_SHEET_ID)
if SHEET_ID != CANONICAL_MASTER_SHEET_ID:
    raise RuntimeError("MNTREES_MASTER_SHEET_ID must reference the approved consolidated workbook; refusing retired or alternate sources")
ROOT=pathlib.Path("data")
credentials=json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
auth=service_account.Credentials.from_service_account_info(credentials,scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
url=f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/%27Retailer%20Master%27%21A1%3AN400"
resp=AuthorizedSession(auth).get(url,timeout=45)
resp.raise_for_status()
rows=resp.json().get("values",[])
assert len(rows)>=200 and rows[0][0]=="License ID","Unexpected/incomplete sheet; no changes written"
directory_path=ROOT/"retailer_locations.json"
targets_path=ROOT/"retailer_menu_scan_targets.json"
directory=json.loads(directory_path.read_text())
by_id={x["id"]:x for x in directory}
assert len(by_id)==len(directory),"Duplicate directory IDs"
seen=set()
for row in rows[1:]:
    row=(row+[""]*14)[:14]
    id,legal,display,address,map_address,menu,override,website,google=row[:9]
    if not id:continue
    assert id not in seen,"Duplicate sheet license ID: "+id
    seen.add(id)
    assert legal and address,"Missing legal name or address: "+id
    x=by_id.get(id)
    if x is None:
        x={"id":id,"license_id":id,"source_class":"retailer_master","status":"spreadsheet_directory","lat":None,"lng":None,"coordinate_accuracy":"unresolved"}
        directory.append(x);by_id[id]=x
    old_address=x.get("map_address") or x.get("address")
    new_address=map_address or address
    if old_address!=new_address:
        x.update(lat=None,lng=None,coordinate_accuracy="unresolved")
        for field in ("geocode_match","geocode_source"):x.pop(field,None)
    x.update(name=display or legal,legal_name=legal,address=address,map_address=map_address,menu_url=override or menu,website_url=website,google_business_url=google)
# Deduplicate research-only rows that refer to an existing licensed physical storefront.
# Preserve the research name and source ID as provenance on the licensed location.
def physical_key(value):
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())
licensed_by_address={physical_key(x.get("map_address") or x.get("address")):x for x in directory
                     if x.get("id") and not str(x["id"]).startswith("RESEARCH-PRICED-")}
duplicates=[]
for x in directory:
    if not str(x.get("id","")).startswith("RESEARCH-PRICED-"):continue
    main=licensed_by_address.get(physical_key(x.get("map_address") or x.get("address")))
    if not main or main is x:continue
    main["retailer_aliases"]=list(dict.fromkeys([*(main.get("retailer_aliases") or []),x.get("name","")]))
    main["merged_source_ids"]=list(dict.fromkeys([*(main.get("merged_source_ids") or []),x["id"]]))
    duplicates.append(x["id"])
if duplicates:
    directory=[x for x in directory if x.get("id") not in set(duplicates)]
assert len(seen)>=200,"Incomplete sheet; no changes written"
targets=[{"id":x["id"],"name":x["name"],"url":x["menu_url"]} for x in directory if x.get("id") in seen and x.get("menu_url","").startswith("https://")]
assert len(targets)>=150,"Suspicious menu target loss; no changes written"
directory_path.write_text(json.dumps(directory,ensure_ascii=False,indent=2)+"\n")
targets_path.write_text(json.dumps(targets,ensure_ascii=False,indent=2)+"\n")
print(f"Synced {len(seen)} sheet retailers; {len(targets)} menu targets")
