#!/usr/bin/env python3
"""Street-address coordinate audit for MNtrees retailer map.

Geocodes using the US Census public address-range service (not rooftop locations).
Only unique matches with the same house number, MN, ZIP and plausible street are used.
Ambiguous/unmatched records retain their existing coordinates for provenance but must
not be rendered as street-level map pins. Never substitute ZIP-centroid coordinates.
"""
import argparse
import concurrent.futures
import datetime as dt
import difflib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "retailer_locations.json"
AUDIT = ROOT / "data" / "retailer_coordinate_audit.json"
ENDPOINT = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
SUFFIX = re.compile(r"\b(?:street|st\.?|avenue|ave\.?|road|rd\.?|drive|dr\.?|boulevard|blvd\.?|highway|hwy\.?|lane|ln\.?|trail|trl\.?|way|court|ct\.?|circle|cir\.?|place|pl\.?|terrace|ter\.?|parkway|pkwy\.?|loop|broadway)\b", re.I)
TRAILER = re.compile(r"\s+(?:suite|ste\.?|unit|apt\.?|building|bldg\.?|#)\s*#?[\w-]+", re.I)
ZIP = re.compile(r"^(.+?)\s+MN\s+(\d{5})(?:-\d{4})?$", re.I)
HOUSE = re.compile(r"^\s*(\d+[A-Za-z]?)\b")
DIRECTION = re.compile(r"^\s+(?:N|S|E|W|NE|NW|SE|SW|North|South|East|West)\.?\b", re.I)

def query_address(raw):
    address = str(raw or "").strip().replace(",", " ")
    match = ZIP.match(address)
    if not match:
        return address
    prefix, zip_code = match.groups()
    possibilities = list(SUFFIX.finditer(prefix))
    for suffix in possibilities:
        end = suffix.end()
        if suffix.group().lower().rstrip(".") in {"highway", "hwy"}:
            number = re.match(r"\s+\d+", prefix[end:])
            if number:
                end += number.end()
        direction = DIRECTION.match(prefix[end:])
        if direction:
            end += direction.end()
        street, city = prefix[:end].strip(), prefix[end:].strip()
        city = TRAILER.sub("", city).strip()
        if city and HOUSE.match(street):
            return f"{street}, {city}, MN {zip_code}"
    return f"{prefix}, MN {zip_code}"

def normalized(text):
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()

def street_suffix(street):
    """Distinguish Avenue from Street or Place from Road before accepting a pin."""
    kinds = {
        "st": "street", "street": "street",
        "ave": "avenue", "avenue": "avenue",
        "rd": "road", "road": "road",
        "pl": "place", "place": "place",
        "dr": "drive", "drive": "drive",
        "blvd": "boulevard", "boulevard": "boulevard",
        "hwy": "highway", "highway": "highway",
        "ln": "lane", "lane": "lane",
        "trl": "trail", "trail": "trail",
        "ct": "court", "court": "court",
        "cir": "circle", "circle": "circle",
        "pkwy": "parkway", "parkway": "parkway",
        "ter": "terrace", "terrace": "terrace",
        "way": "way", "loop": "loop", "broadway": "broadway",
    }
    candidates = list(SUFFIX.finditer(str(street)))
    if not candidates:
        return None
    return kinds.get(candidates[-1].group().lower().rstrip("."))

def valid_match(original, match):
    components = match.get("addressComponents") or {}
    matching = str(match.get("matchedAddress") or "")
    parsed = ZIP.match(str(original or "").replace(",", " ").strip())
    if not parsed or str(components.get("state", "")).upper() != "MN":
        return False
    if str(components.get("zip", "")) != parsed.group(2):
        return False
    given_house = HOUSE.match(parsed.group(1))
    matched_house = HOUSE.match(matching)
    if not given_house or not matched_house or given_house.group(1).upper() != matched_house.group(1).upper():
        return False
    expected_suffix = street_suffix(query_address(original).split(",")[0])
    matched_suffix = street_suffix(matching.split(",")[0])
    # The geocoder sometimes changes Place into Road or Avenue into Street.
    # Those points are not interchangeable, even with the same ZIP and number.
    if expected_suffix and expected_suffix != matched_suffix:
        county_route = (
            expected_suffix == "highway" and matched_suffix == "road"
            and re.search(r"\bcounty\b|\bco\b", str(original), re.I)
        )
        if not county_route:
            return False
    coords = match.get("coordinates") or {}
    lat, lng = coords.get("y"), coords.get("x")
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        return False
    if not (43.0 < lat < 50.0 and -98.0 < lng < -89.0):
        return False
    street = normalized(str(components.get("streetName") or ""))
    if not street:
        return False
    # Require the returned street name to be present in the submitted address.
    # Avoid accepting a wrong street solely because house number and ZIP agree.
    tokens = [x for x in street.split() if len(x) > 1]
    source = normalized(original)
    if tokens and sum(x in source.split() for x in tokens) < max(1, len(tokens) - 1):
        return False
    return True

def lookup(record, timeout):
    address = record.get("map_address") or record.get("address") or ""
    if not address:
        return record["id"], None, "no_address"
    params = urllib.parse.urlencode({"address": query_address(address), "benchmark": "Public_AR_Current", "format": "json"})
    request = urllib.request.Request(ENDPOINT + "?" + params, headers={"User-Agent": "MNtrees-retailer-coordinate-audit/1.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
        matches = payload.get("result", {}).get("addressMatches", [])
        accepted = [x for x in matches if valid_match(address, x)]
        if len(accepted) != 1 or len(matches) != 1:
            return record["id"], None, "unmatched_or_ambiguous"
        point = accepted[0]["coordinates"]
        return record["id"], {"lat": round(point["y"], 6), "lng": round(point["x"], 6),
                               "matched_address": accepted[0]["matchedAddress"]}, "matched"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
        return record["id"], None, "request_error_" + type(exc).__name__

def rescan(records, workers=4, timeout=12):
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for rid, match, status in pool.map(lambda x: lookup(x, timeout), records):
            results[rid] = (match, status)
    counts = Counter()
    unresolved = []
    for record in records:
        match, status = results[record["id"]]
        counts[status] += 1
        address = record.get("map_address") or record.get("address") or ""
        if match:
            record["lat"], record["lng"] = match["lat"], match["lng"]
            record["coordinate_accuracy"] = "census_address_range_interpolated"
            record["coordinate_source"] = "US Census Geocoding Services - Public_AR_Current"
            record["coordinate_checked_at"] = now
            record["coordinate_for_address"] = address
            record["coordinate_matched_address"] = match["matched_address"]
        else:
            # Preserve previously vetted street-level coordinates only for the same address.
            current_suffix = street_suffix(query_address(address).split(",")[0])
            saved_suffix = street_suffix(str(record.get("coordinate_matched_address") or "").split(",")[0])
            same_route = current_suffix == "highway" and saved_suffix == "road" and bool(re.search(r"\\bcounty\\b|\\bco\\b", address, re.I))
            prior_valid = bool(record.get("coordinate_matched_address")) and (current_suffix == saved_suffix or same_route)
            if record.get("coordinate_accuracy") == "census_address_range_interpolated" and record.get("coordinate_for_address") == address and prior_valid:
                counts["previous_match_retained"] += 1
            else:
                record["coordinate_accuracy"] = "unresolved"
                unresolved.append({"id": record["id"], "name": record["name"], "address": address, "reason": status})
    if counts["matched"] == 0 and counts["request_error_URLError"] + counts["request_error_TimeoutError"] + counts["request_error_OSError"] >= len(records) // 2:
        raise RuntimeError("Census geocoding unavailable; refusing to rewrite retailer coordinates")
    report = {
        "checked_at": now, "source": "US Census Public_AR_Current (street-range interpolation, not rooftop GPS)",
        "retailers": len(records), "results": dict(counts),
        "renderable_street_geocodes": sum(x.get("coordinate_accuracy") == "census_address_range_interpolated" for x in records),
        "unresolved": unresolved,
    }
    return records, report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=12)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    records = json.loads(SOURCE.read_text(encoding="utf-8"))
    if len({x["id"] for x in records}) != len(records):
        raise SystemExit("Duplicate retailer IDs")
    updated, report = rescan(records, workers=max(1, min(args.workers, 6)), timeout=args.timeout)
    print(json.dumps({k: v for k, v in report.items() if k != "unresolved"}, indent=2))
    if not args.dry_run:
        SOURCE.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        AUDIT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
