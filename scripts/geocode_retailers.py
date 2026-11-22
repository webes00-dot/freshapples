#!/usr/bin/env python3
"""Geocode Minnesota retailers to street-address coordinates, never ZIP centroids."""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

PATH = Path("data/retailer_locations.json")
stores = json.loads(PATH.read_text(encoding="utf-8"))
headers = {"User-Agent": "MNtrees address geocoding/1.1", "Accept": "application/json"}
updated = 0
unresolved = []

def get_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=18) as response:
        return json.load(response)

def geocode(address):
    q = urllib.parse.urlencode({"address": address, "benchmark": "Public_AR_Current", "format": "json"})
    try:
        matches = get_json("https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?" + q).get("result", {}).get("addressMatches", [])
        if matches:
            m = matches[0]
            return float(m["coordinates"]["y"]), float(m["coordinates"]["x"]), "US Census Geocoder", m.get("matchedAddress", "")
    except Exception as exc:
        print("Census geocoder error:", str(exc)[:120])
    # Fallback: accept only address-level matches, never postal, locality, or street-centroid guesses.
    q = urllib.parse.urlencode({"SingleLine": address, "f": "json", "outFields": "Addr_type,Match_addr", "maxLocations": 1})
    try:
        matches = get_json("https://geocode-api.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?" + q).get("candidates", [])
        if matches:
            m = matches[0]
            kind = m.get("attributes", {}).get("Addr_type", "")
            if m.get("score", 0) >= 85 and kind in ("PointAddress", "Subaddress", "StreetAddress"):
                return float(m["location"]["y"]), float(m["location"]["x"]), "ArcGIS World Geocoder", m.get("address", "")
    except Exception as exc:
        print("ArcGIS geocoder error:", str(exc)[:120])
    return None

for store in stores:
    if store.get("coordinate_accuracy") in ("address_verified", "rooftop_verified", "street_geocoded"):
        continue
    address = (store.get("map_address") or store.get("address") or "").strip()
    if not address:
        unresolved.append(store.get("id"))
        continue
    result = geocode(address)
    if result:
        lat, lng, source, matched = result
        if 43 < lat < 50 and -98 < lng < -89:
            store.update(lat=lat, lng=lng, coordinate_accuracy="street_geocoded",
                         geocode_match=matched, geocode_source=source)
            updated += 1
        else:
            unresolved.append(store.get("id"))
    else:
        unresolved.append(store.get("id"))
    time.sleep(0.2)
PATH.write_text(json.dumps(stores, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
Path("data/retailer_geocode_report.json").write_text(json.dumps({"updated": updated, "unresolved_ids": unresolved}, indent=2) + "\n")
print("Street-geocoded:", updated, "Unresolved:", len(unresolved))
print("Unresolved IDs:", ", ".join(str(x) for x in unresolved))
