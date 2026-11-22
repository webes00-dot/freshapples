#!/usr/bin/env python3
"""Build one public catalog from the existing MNtrees datasets.

Does not mutate source observations. Strains absent from the approved master are held for review.
A bad or missing input aborts the build rather than publishing an empty catalog.
"""
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from strain_rules import match_strain, normalize_brand, identify_product, parse_structured_title, OWNER_STRAIN_BRANDS, brand_from_explicit_title
from strain_rules import government_oranges_variant, ALIASES
from master_resolver import resolve_master, key as master_key
from approved_scan_repair import repair_scan_identity
from brand_prefix_repair import repair_brand_prefix_title
from delimited_strain import resolve_delimited_strain

ROOT = Path("data")
SOURCES = ["listings.json", "researched_menu_offers.json",
           "new_retailer_menu_offers.json", "auto_menu_offers.json",
           "concentrate_research_2026-11-19.json", "highnorth_owner_reviewed_offers.json", "thc_owner_added_offers.json"]
CORRECTIONS = ROOT / "catalog_corrections.json"
MENU_MISS_STATE = ROOT / "menu_miss_state.json"
STRAIN_MASTER = ROOT / "strain_master.json"
from master_config import master_sheet_id
CANONICAL_MASTER_SHEET_ID = master_sheet_id()
MASTER_REVIEW = Path("dist/data/strain_master_review.json")
MASTER_REVIEW_CSV = Path("dist/data/strain_master_review.csv")
OUT = Path("dist/data/catalog.json")
REPORT = Path("dist/data/catalog_build_report.json")
BLOCKED = re.compile(r"\\b(?:edible|gumm(?:y|ies)|beverage|tincture|topical)\\b", re.I)
CONCENTRATE = re.compile(r"\\b(?:concentrates?|extracts?|live\\s+rosin|rosin|live\\s+resin|resin|wax|shatter|badder|budder|batter|diamonds|crumble|hash|sauce)\\b", re.I)
VAPE = re.compile(r"\\b(?:vapes?|cartridges?|disposables?|all[- ]in[- ]one|aio)\\b", re.I)
CATEGORY = re.compile(r"pre.?roll|joint|blunt", re.I)
PACKAGING_ONLY = re.compile(r"^\\s*(?:\\d+(?:\\.\\d+)?\\s*(?:g|gm|grams?|ct|count)|\\d+\\s*x\\s*\\d+(?:\\.\\d+)?\\s*g)(?:\\s*(?:pouch|jar|\\([^)]*\\)))?\\s*$", re.I)

def load(path):
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError("Expected array: " + str(path))
    return data

def strain_key(name):
    return re.sub(r"\\s+", " ", str(name or "").strip()).casefold()

def load_strain_master():
    """Fail closed when the approved sheet snapshot is missing or malformed."""
    payload = json.loads(STRAIN_MASTER.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("source_tab") != "Strain Master":
        raise ValueError("Invalid authoritative Strain Master snapshot")
    if payload.get("source_spreadsheet_id") != CANONICAL_MASTER_SHEET_ID:
        raise ValueError("Strain Master snapshot references a retired or unapproved spreadsheet")
    canonical = {}
    for name in payload.get("canonical_strains", []):
        key = strain_key(name)
        if not key or key in canonical:
            raise ValueError("Duplicate or empty canonical strain in snapshot: " + str(name))
        canonical[key] = name
    if len(canonical) < 100:
        raise ValueError("Strain Master snapshot too small: fail closed")
    aliases = {}
    for alias, target in payload.get("approved_aliases", {}).items():
        key = strain_key(alias)
        target_key = strain_key(target)
        if not key or target_key not in canonical or (key in canonical and key != target_key):
            raise ValueError("Invalid Strain Master alias: " + str(alias))
        aliases[key] = canonical[target_key]
    return canonical, aliases

def address_key(address):
    return re.sub(r"[^a-z0-9]", "", str(address).casefold())

def load_corrections():
    data = json.loads(CORRECTIONS.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported correction schema")
    corrections = {}
    for correction in data.get("corrections", []):
        key = correction["id"]
        if key in corrections:
            raise ValueError("Duplicate correction ID: " + key)
        corrections[key] = correction
    return corrections

# Scanners sometimes use shorter display names than editorial masters. Only
# accept these label pairs when the observation still carries the exact
# licensed location ID; never merge store identities by a fuzzy name.
REVIEWED_STORE_LABELS = {
    ("Dinky Dope", "Dinky Dope — Dinkytown"): "MICRO-L25-000658-01-AUR",
    ("DISPO - Rochester", "DISPO"): "DIS-L25-000080-02-AUR",
}

def correction_retailer_matches(item, correction):
    observed = str(item.get("retailer") or "")
    approved = str(correction["retailer"])
    if observed == approved:
        return True
    expected_license = REVIEWED_STORE_LABELS.get((observed, approved))
    return bool(expected_license and item.get("retailer_id") == expected_license)

def apply_correction(item, corrections, counts):
    correction = corrections.get(str(item.get("id") or ""))
    if correction is None:
        return item
    # A price is a changing offer attribute, not the product's identity.
    # Validate stable ID, licensed retailer, raw title, package weight, and
    # source URL (when pinned) before reusing an approved name/brand decision.
    if (not correction_retailer_matches(item, correction) or
            str(item.get("product_name") or "") != correction["expected_raw_name"] or
            float(item.get("package_g") or 0) != float(correction["expected_weight_g"])):
        raise ValueError("Source changed; correction must be reviewed: " + correction["id"])
    if correction.get("source_url") and str(item.get("url") or "").split("?")[0] != correction["source_url"]:
        raise ValueError("Correction source URL changed: " + correction["id"])
    observed_price = float(item.get("price") or 0)
    if not 0 < observed_price <= 500:
        raise ValueError("Invalid observed price for approved correction: " + correction["id"])
    if observed_price != float(correction["expected_price"]):
        # Keep the current source price, do NOT overwrite it with the historical
        # approval-time amount. Count drifts for the build report/audit.
        counts["approved_identity_with_new_observed_price"] += 1
    status = correction["status"]
    counts["corrections_matched"] += 1
    if status in ("exclude_concentrate", "exclude_vape", "exclude_edible", "exclude_generic", "exclude_hemp", "hold_discount"):
        counts["corrections_" + status] += 1
        return None
    if status != "approved":
        raise ValueError("Unknown correction status: " + status)
    item["raw_scanned_product_name"] = item.get("product_name")
    item["strain"] = correction["strain"]
    # Scanner's cart text is not a product title.
    item["product_name"] = correction["strain"]
    if correction.get("brand"):
        item["brand"] = correction["brand"]
    if correction.get("category"):
        item["category"] = correction["category"]
    if correction.get("package_g") is not None:
        corrected_g = float(correction["package_g"])
        if corrected_g <= 0:
            raise ValueError("Invalid corrected package weight: " + correction["id"])
        item["package_g"] = corrected_g
        counts["corrections_package_weight"] += 1
    if correction.get("reviewed_identity"):
        item["reviewed_identity"] = True
    if correction.get("pack_count") is not None:
        count = correction["pack_count"]
        if type(count) is not int or count < 2 or not item.get("package_g"):
            raise ValueError("Invalid reviewed pack count: " + correction["id"])
        item["pack_count"] = count
    counts["corrections_approved"] += 1
    return item

def infer_missing_brands(result, counts):
    """Fill missing brand from unique strain+form+weight evidence before strain-only.

    Source/product-title explicit brands win. Never force one strain-wide brand when
    the strain is sold under several brands in different forms or package weights.
    """
    exact = defaultdict(set)
    strain_only = defaultdict(set)
    labels = {}
    def category(item):
        raw = str(item.get("category") or "").casefold()
        return "Preroll" if CATEGORY.search(raw) else "Flower" if "flower" in raw else raw
    def grams(item):
        try:
            return round(float(item.get("package_g")), 3)
        except (ValueError, TypeError):
            return None
    for item in result:
        strain = str(item.get("strain") or "").casefold().strip()
        brand = normalize_brand(item.get("brand"))
        if not (strain and brand):
            continue
        key = brand.casefold()
        labels.setdefault(key, brand)
        strain_only[strain].add(key)
        if grams(item) is not None:
            exact[(strain, category(item), grams(item))].add(key)
    for strain, brand in OWNER_STRAIN_BRANDS.items():
        key = normalize_brand(brand).casefold()
        labels.setdefault(key, normalize_brand(brand))
        strain_only[strain.casefold()].add(key)
    for item in result:
        if normalize_brand(item.get("brand")):
            continue
        strain = str(item.get("strain") or "").casefold().strip()
        options = exact.get((strain, category(item), grams(item)), set())
        method = "unique_strain_category_weight"
        if len(options) != 1:
            options = strain_only.get(strain, set())
            method = "unique_strain_brand"
        if len(options) == 1:
            item["brand"] = labels[next(iter(options))]
            item["brand_source"] = method
            counts["brands_inferred_" + method] += 1
        elif len(options) > 1:
            counts["brands_ambiguous_unassigned"] += 1

def package_count_variant(item):
    """Preserve distinct advertised multipacks even when total grams match."""
    if item.get("pack_count"):
        return item["pack_count"]
    title = str(item.get("raw_scanned_product_name") or item.get("product_name") or item.get("strain") or "")
    match = re.search(r"\b(\d{1,2})\s*(?:-?\s*pack|pk|pck|ct|count)\b", title, re.I)
    if not match and CATEGORY.search(str(item.get("category") or "")):
        match = re.search(r"\b(\d{1,2})\s*[x×]\s*(?:\d+(?:\.\d+)?|\.\d+)\s*g\b", title, re.I)
    return int(match.group(1)) if match else None

def main():
    stores = load(ROOT / "retailer_locations.json")
    store_by_id = {s["id"]: s for s in stores}
    # Use physical address as the location identity; do not merge branches by name.
    store_by_address = {address_key(s["address"]): s for s in stores}
    store_by_name = {}
    for s in stores:
        store_by_name.setdefault(s["name"].casefold().strip(), []).append(s)
    # Owner-reviewed store aliases: only resolve when the expected licensed
    # location exists. Never collapse different addresses or retailer licenses.
    unanimous_id = "MICRO-L24-000422-01-AUR"
    unanimous_store = store_by_id.get(unanimous_id)
    if unanimous_store and "2835 Hennepin Ave S" in unanimous_store.get("address", ""):
        for label in ("Unanimous Cannabis", "Unanimous Cannabis — Minneapolis",
                      "Unanimous Cannabis Minneapolis"):
            store_by_name[label.casefold()] = [unanimous_store]
    published = {}
    exact_source_ids = defaultdict(list)
    corrections = load_corrections()
    master_names, master_aliases = load_strain_master()
    owner_aliases = {master_key(alias): target for alias, target in ALIASES.items()
                     if master_key(target) in master_names}
    miss_state = json.loads(MENU_MISS_STATE.read_text()) if MENU_MISS_STATE.exists() else {}
    retired_ids = set(miss_state.get("retired_ids", []))
    matched_ids = set()
    counts = Counter()
    review = []
    delimiter_review = []
    # The owner imports THC observed offers only when this store/brand/strain/
    # product-form/package-weight combination is not already in MNtrees.
    # Do not make price, URL, or scrape timestamp part of this identity.
    seen_store_skus = set()
    def import_sku_identity(item):
        compact = lambda value: re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())
        raw_category = str(item.get("category") or "")
        form = ("Preroll" if CATEGORY.search(raw_category) else
                "Concentrates" if raw_category.casefold() in ("concentrate","concentrates") else
                "Flower" if "flower" in raw_category.casefold() else raw_category)
        try:
            grams = round(float(item.get("package_g") or 0), 3)
        except (TypeError, ValueError):
            grams = 0
        return (str(item.get("retailer_id") or item.get("retailer") or "").strip().casefold(),
                compact(normalize_brand(item.get("brand"))),
                compact(item.get("strain")),form,grams)
    for source in SOURCES:
        records = load(ROOT / source)
        counts["read_" + source] = len(records)
        for record in records:
            item = dict(record)
            if item.get("record_status") == "hold_pending_first_party_price_verification":
                counts["excluded_unverified_price_source"] += 1
                continue
            source_id = str(item.get("id") or "")
            if source_id in corrections:
                matched_ids.add(source_id)
            item = apply_correction(item, corrections, counts)
            if item is None:
                continue
            if source_id in retired_ids:
                counts["excluded_after_ten_menu_misses"] += 1
                continue
            # Never treat smoking accessories or humidity-control packets as cannabis.
            # Retailer scans can mislabel gear as Flower and mistake product capacity
            # (for example an empty 1g cone) for cannabis weight.
            accessory_text = " | ".join(str(item.get(k) or "") for k in
                                       ("strain", "product_name", "brand", "category", "url"))
            if (re.search(r"(?i)\b(?:boveda|humidity\s+control|humidity\s+packets?)\b", accessory_text)
                or re.search(r"(?i)\b(?:rolling\s+papers?|empty\s+(?:cones?|pre[- ]?rolls?)|spiral\s+tip\s+cross\s+cone|filter\s+tips?|rolling\s+trays?|grinders?|lighters?)\b", accessory_text)
                or str(item.get("category") or "").casefold().strip() in
                   {"accessory", "accessories", "gear", "merchandise"}):
                counts["excluded_non_cannabis_accessory"] += 1
                continue
            # Elm Woods is hemp flower, outside this adult-use cannabis catalog.
            if re.search(r"(?i)\belm\s*woods?\b", " | ".join(str(item.get(k) or "") for k in ("strain", "brand", "brand_family", "product_name", "product_family"))):
                counts["excluded_hemp_elm_woods"] += 1
                continue
            name = str(item.get("product_name") or item.get("strain") or "").strip()
            if re.fullmatch(r"(?i)fruit\\s+blend\\s+cured\\s+resin", name) or re.fullmatch(r"(?i)fruit\\s+blend\\s+cured\\s+resin", str(item.get("strain") or "")):
                counts["excluded_generic_fruit_blend"] += 1
                continue
            category = str(item.get("category") or "")
            source_path = str(item.get("url") or "").split("?")[0].lower()
            if re.search(r"\bdizgo\b", name, re.I) and re.search(
                r"\bdizgo\s*\|\s*vape cartridge\s*\|\s*rosin\s*\|\s*mixed\b",
                name, re.I,
            ):
                counts["excluded_dizgo_mixed_cartridge"] += 1
                continue
            # Preserve dabbable concentrates; keep vapes, edibles and generic
            # promotions out of this product class. Source URL and menu category
            # take precedence over potentially misleading product names.
            if re.search(r"/(?:edibles?|beverages?|drinks?)(?:-|/)", source_path):
                counts["excluded_nonflower_url"] += 1
                continue
            if re.fullmatch(r"\\s*(?:staff\\s+pick|budtender\\s+pick|mystery\\s+strain)\\s*", name, re.I):
                counts["excluded_generic_promotion"] += 1
                continue
            if re.fullmatch(r"\s*(?:sativa|indica|hybrid)\s+blend\s*", name, re.I) or re.fullmatch(r"\s*(?:sativa|indica|hybrid)\s+blend\s*", str(item.get("strain") or ""), re.I):
                counts["excluded_generic_blend"] += 1
                continue
            if BLOCKED.search(category):
                counts["excluded_nonflower"] += 1
                continue
            if re.search(r"\\b(?:edible|gumm(?:y|ies)|beverage|tincture|topical)\\b", name, re.I):
                counts["excluded_nonflower"] += 1
                continue
            if re.search(r"\\bsmazey\\b", name, re.I) and re.search(r"\\b(?:4\\s*pack|cherry\\s+lime\\s+blue\\s+raspberry)\\b", name, re.I):
                counts["excluded_nonflower"] += 1
                continue
            is_concentrate = bool(category.casefold() in {"concentrate", "concentrates"}
                                  or CONCENTRATE.search(category)
                                  or re.search(r"/(?:concentrates?|vapes?)(?:-|/)", source_path)
                                  or VAPE.search(category) or VAPE.search(name)
                                  or (CONCENTRATE.search(name) and not re.search(r"pre.?roll", category, re.I)))
            if is_concentrate:
                item["category"] = "Concentrates"
                counts["concentrate_observations_accepted"] += 1
            elif not (re.search(r"flower", category, re.I) or CATEGORY.search(category)):
                counts["excluded_other_category"] += 1
                continue
            # Multipack audit: prevent a per-joint weight from entering a per-gram
            # ranking as though it were the full package weight. Hold ambiguous
            # records for review instead of inventing a total weight.
            if CATEGORY.search(str(item.get("category") or "")):
                pack = package_count_variant(item)
                title = str(item.get("raw_scanned_product_name") or item.get("product_name") or "")
                unit = re.search(r"(?i)\\b(\\d+(?:\\.\\d+)?)\\s*(?:g|gm|grams?)\\s*(?:joint|pre[- ]?roll)", title)
                if unit and pack and pack > 1:
                    expected = float(unit.group(1)) * pack
                    try:
                        recorded = float(item.get("package_g") or 0)
                    except (TypeError, ValueError):
                        recorded = 0
                    if recorded < expected - 0.01:
                        counts["held_preroll_multipack_weight_conflict"] += 1
                        review.append({"id": item.get("id"), "retailer": item.get("retailer"),
                                       "raw_name": title, "recorded_g": recorded,
                                       "expected_total_g": expected, "reason": "multipack_weight_conflict"})
                        continue
            if not item.get("retailer") or (not item.get("url") and source != "thc_owner_added_offers.json"):
                counts["excluded_missing_source"] += 1
                continue
            try:
                price = float(item.get("price") or 0)
            except (TypeError, ValueError):
                price = 0
            if re.search(r"\$\s*\d+(?:\.\d+)?\s*off", name, re.I):
                counts["excluded_promo_price_ambiguous"] += 1
                continue
            if not 0 < price <= 500:
                counts["excluded_invalid_price"] += 1
                continue
            location = store_by_id.get(str(item.get("retailer_id") or ""))
            if location is None and item.get("address"):
                location = store_by_address.get(address_key(item["address"]))
            if location is None:
                possible = store_by_name.get(str(item["retailer"]).casefold().strip(), [])
                if len(possible) == 1:
                    location = possible[0]
            if location:
                item["retailer_id"] = location["id"]
                item["retailer"] = location["name"]
                item["address"] = location["address"]
            # Remove retailer promotion disclaimers before interpreting product identity.
            # Do not alter prices: promotional price validity requires separate review.
            promo = re.match(r"(?i)^offer\s+conditions\s+apply\s+(.+)$", str(item.get("strain") or name).strip())
            if promo:
                promo_name = promo.group(1).strip()
                promo_rules = (
                    (r"doctor\s+dabs\s+guerilla\s+stomper", "Guerilla Stomper", "Doctor Dabs"),
                    (r"good\s+green\s+mystic\s+mint", "Mystic Mint", "Good Green"),
                    (r"good\s+green\s+jack['’]?s\s+delight", "Jack's Delight", "Good Green"),
                    (r"looner\s+looner\s+fruit\s+by\s+the\s+foot", "Fruit by the Foot", "Looner"),
                    (r"unbound\s+unbound\s+wilfunk", "Wilfunk", "Unbound"),
                    (r"verist\s+gush\s+kush", "Gush Kush", "Verist Fields"),
                    (r"verist\s+mimosa\s+ice\s+flower", "Mimosa Ice", "Verist Fields"),
                    (r"verist\s+swedish\s+og", "Swedish OG", "Verist Fields"),
                    (r"verist\s+valley\s+frost\s+flower", "Valley Frost", "Verist Fields"),
                )
                for pattern, clean_name, clean_brand in promo_rules:
                    if re.fullmatch(pattern, promo_name, re.I):
                        item["raw_scanned_product_name"] = item.get("raw_scanned_product_name") or name
                        item["strain"] = clean_name
                        item["product_name"] = clean_name
                        item["brand"] = clean_brand
                        counts["promotion_prefix_normalized"] += 1
                        break
                else:
                    # Strip the generic disclaimer even when no specific product identity is confirmed.
                    # Keep original scanned text and price for auditing; downstream parsing resolves brand/strain.
                    item["raw_scanned_product_name"] = item.get("raw_scanned_product_name") or name
                    item["strain"] = promo_name
                    item["product_name"] = promo_name
                    counts["promotion_prefix_removed"] += 1
            # Recover a brand explicitly printed at the start of a source title
            # before cultivar matching; a blank scanner field is not evidence
            # that the product brand is unknown. Keep the raw title unchanged.
            if not item.get("brand"):
                found_brand = brand_from_explicit_title(
                    item.get("raw_scanned_product_name") or name)
                if found_brand:
                    item["brand"] = found_brand
                    counts["brand_from_explicit_source_title"] += 1
            # Explicit owner-approved correction takes precedence over automatic parsing.
            approved_override = source_id in corrections and corrections[source_id]["status"] == "approved"
            # An owner-authorized THC observation has an explicit source brand
            # and canonical strain. Re-parsing an unbranded strain title can
            # invent a different brand and wrongly merge distinct brands.
            parsed = None if approved_override or source == "thc_owner_added_offers.json" else (
                repair_brand_prefix_title(item, master_names, master_aliases)
                or repair_scan_identity(item, master_names, master_aliases)
                or resolve_delimited_strain(item.get("strain") or name, master_names, master_aliases)
                or identify_product(item.get("strain") or name) or identify_product(name)
                or parse_structured_title(name))
            if parsed:
                item["raw_scanned_product_name"] = item.get("raw_scanned_product_name") or name
                item["strain"] = parsed["strain"]
                item["product_name"] = parsed["strain"]
                if parsed.get("product_variant") and not item.get("product_variant"):
                    item["product_variant"] = parsed["product_variant"]
                if parsed.get("brand") and not item.get("brand"):
                    item["brand"] = parsed["brand"]
                    if (parsed["brand"], parsed["strain"]) in {
                        ("Dizgo Collective", "Medusa"), ("Dizgo Collective", "TriCross"),
                        ("Dizgo Collective", "Hyperion F1"), ("R and D Pharm", "Black Maple 22"),
                        ("Verist Fields", "Torch Top"), ("Verist Fields", "Uffda OG"),
                        ("Verist Fields", "Uptown Tart"),
                    }:
                        item["product_family"] = parsed["strain"]
                counts["product_identity_parsed"] += 1
            variant = government_oranges_variant(
                item.get("strain"), name, item.get("product_family"))
            if variant is not None:
                item["strain"] = "Government Oranges"
                if variant:
                    item["product_variant"] = variant
            # A pipe in the strain field is a scanner structure error. Do not
            # publish it as a cultivar, guess from the last segment, or discard
            # the source. Archive the exact unresolved observation for review.
            if "|" in str(item.get("strain") or ""):
                delimiter_review.append({
                    "id": item.get("id"), "retailer": item.get("retailer"),
                    "raw_title": item.get("raw_scanned_product_name") or name,
                    "raw_strain": item.get("strain"), "url": item.get("url"),
                    "brand": item.get("brand"), "reason": "unresolved_pipe_title",
                    "review_status": "Pending exact master reconciliation"
                })
                counts["held_delimited_strain_unresolved"] += 1
                continue
            matched = match_strain(item.get("strain") or name)
            if matched["match_status"] == "invalid" or re.fullmatch(r"(?:sale\s+)?0\s+0\s+in(?:\s+cart)?", str(item.get("strain") or "").strip(), re.I):
                counts["excluded_invalid_name"] += 1
                continue
            if re.fullmatch(r"pre[- ]?pack(?:aged)?", str(matched["strain"]).strip(), re.I) or PACKAGING_ONLY.fullmatch(matched["strain"]):
                counts["excluded_packaging_only"] += 1
                continue
            # Mandatory scan sequence:
            # first parse -> compare -> reparse with master + owner rules ->
            # suggest (never auto-approve approximate guesses) -> review.
            # Retain public listings under review to avoid another mass purge.
            resolved = resolve_master(
                proposed=matched["strain"],
                raw_title=item.get("raw_scanned_product_name") or name,
                brand=item.get("brand") or "",
                canonical=master_names,
                aliases=master_aliases,
                matched_aliases=owner_aliases,
            )
            if resolved["status"] == "approved":
                item["strain"] = resolved["strain"]
                item["master_strain"] = resolved["strain"]
                item["strain_match_status"] = resolved["method"]
                counts["master_" + resolved["method"]] += 1
            else:
                counts["pending_strain_master_review"] += 1
                review.append({"id": item.get("id"), "retailer": item["retailer"],
                               "source": source, "raw_name": name,
                               "proposed_strain": matched["strain"],
                               "reparsed_candidate": resolved["parsed"],
                               "suggestions": resolved["suggestions"],
                               "brand": item.get("brand", ""),
                               "url": item["url"], "reason": "not_in_strain_master",
                               "review_status": "Pending approval"})
                item["strain"] = matched["strain"]
                item["strain_match_status"] = "pending_master_review"
            if matched["strain_type"]:
                item["strain_type"] = matched["strain_type"]
            # Owner-approved brand labels override broad alias normalization.
            # In particular, this reviewed Popcorn offer must not be rewritten as Zips.
            approved = corrections.get(str(item.get("id") or ""))
            item["brand"] = (approved["brand"] if approved and approved.get("status") == "approved" and approved.get("brand") else normalize_brand(item.get("brand")))
            item["stock_status"] = "not_verified"
            if matched["match_status"] == "unmatched":
                review.append({"id": item.get("id"), "retailer": item["retailer"],
                               "source": source, "raw_name": name,
                               "strain": item["strain"], "url": item["url"]})
            sku_key = import_sku_identity(item)
            if source == "thc_owner_added_offers.json" and sku_key in seen_store_skus:
                counts["thc_skipped_existing_store_brand_strain_form_grams"] += 1
                continue
            seen_store_skus.add(sku_key)
            # Prefer an observation's stable source ID; retain distinct package variants.
            identity = (str(item.get("retailer_id") or item["retailer"]).casefold(),
                        str(item["url"]).split("?")[0].casefold(),
                        # Historic catalogs used URL/strain/weight identity. THC source
                        # records must also retain explicit brand so same-strain same-size
                        # SKUs from different brands are never silently merged.
                        normalize_brand(item.get("brand")).casefold(),
                        str(item["strain"]).casefold(),
                        str(item["category"]).casefold(),
                        str(item.get("package_g") or ""),
                        item.get("product_variant", ""),
                        package_count_variant(item))
            if source_id:
                exact_source_ids[identity].append(source_id)
            old = published.get(identity)
            incoming_approved = source_id in corrections and corrections[source_id]["status"] == "approved"
            old_id = str(old.get("id") or "") if old else ""
            old_approved = old_id in corrections and corrections[old_id]["status"] == "approved"
            if old is None or (incoming_approved and not old_approved) or (
                not old_approved and not incoming_approved and
                source == "auto_menu_offers.json" and old.get("_source") == "auto_menu_offers.json"
            ):
                item["_source"] = source
                published[identity] = item
            else:
                counts["deduplicated"] += 1
    missing = set(corrections) - matched_ids
    if missing:
        raise ValueError("Unmatched correction IDs: " + ", ".join(sorted(missing)))
    if not published:
        raise ValueError("Refusing to publish empty catalog")
    sources_by_published_id = {
        str(item.get("id") or ""): exact_source_ids[key] for key, item in published.items()
    }
    result = list(published.values())
    infer_missing_brands(result, counts)
    # Every retailer SKU has one public offer, even when independently scraped
    # feeds use different URLs. Never collapse distinct prices, package weights,
    # brands, product forms, or explicit flower/preparation grades.
    def sku_variant(item):
        title = str(item.get("raw_scanned_product_name") or item.get("product_name") or "").casefold()
        tags = (
            ("infused", r"\binfused\b"),
            ("mini", r"\bmini(?:s|\s+buds?)?\b"),
            ("premium", r"\bpremium\b"),
            ("popcorn", r"\bpopcorn\b"),
            ("mixed-buds", r"\bmixed\s+buds?\b"),
            ("ground", r"\bground\b"),
            ("shake", r"\bshake\b"),
            ("smalls", r"\bsmalls?\b"),
            ("indoor", r"\bindoor\b"),
            ("outdoor", r"\boutdoor\b"),
        )
        return tuple(name for name, pattern in tags if re.search(pattern, title))

    def product_url_rank(item):
        url = str(item.get("url") or "").lower()
        return (int(bool(re.search(r"/(?:pdp|product|products)/", url))),
                int(bool(item.get("checked_at"))),
                int(bool(item.get("raw_scanned_product_name"))))

    chosen = {}
    grouped_ids = defaultdict(list)
    for item in result:
        store = str(item.get("retailer_id") or item.get("retailer") or "").strip().casefold()
        category = str(item.get("category") or "").casefold()
        form = "preroll" if CATEGORY.search(category) else "flower" if "flower" in category else category
        identity = (store,
                    str(item.get("strain") or "").strip().casefold(),
                    normalize_brand(item.get("brand")).casefold(),
                    form,
                    round(float(item.get("package_g") or 0), 3),
                    round(float(item.get("price") or 0), 2),
                    sku_variant(item),
                    item.get("product_variant", ""),
                    package_count_variant(item))
        if item.get("id"):
            grouped_ids[identity].extend(sources_by_published_id[str(item["id"])])
        previous = chosen.get(identity)
        if previous is None:
            chosen[identity] = item
        else:
            counts["duplicate_retailer_offers_removed"] += 1
            item_id = str(item.get("id") or "")
            prev_id = str(previous.get("id") or "")
            item_approved = item_id in corrections and corrections[item_id]["status"] == "approved"
            prev_approved = prev_id in corrections and corrections[prev_id]["status"] == "approved"
            if (item_approved and not prev_approved) or (
                item_approved == prev_approved and product_url_rank(item) > product_url_rank(previous)
            ):
                chosen[identity] = item
    # Preserve an audit trail for every source capture merged at either deduplication stage.
    merged_source_ids = {
        source_id: str(chosen[key].get("id"))
        for key, members in grouped_ids.items()
        for source_id in members
        if source_id != str(chosen[key].get("id"))
    }
    result = list(chosen.values())
    # Publication invariant: brand abbreviations must not survive as cultivar
    # headings. Normalize exact MN Loon/MNL title patterns in the generated
    # catalog, not merely in the browser, and preserve the original raw title.
    # This is idempotent and leaves package sizes, prices and source URLs intact.
    for item in result:
        candidates = [item.get("strain"), item.get("product_name"),
                      item.get("raw_scanned_product_name")]
        normalized = next((parsed for raw in candidates
                           if raw and (parsed := identify_product(raw))
                           and parsed.get("brand") == "MN Loon"), None)
        if not normalized:
            continue
        cleaned = normalized["strain"]
        if not cleaned:
            continue
        changed = cleaned.casefold() != str(item.get("strain") or "").casefold()
        item["strain"] = cleaned
        item["brand"] = "MN Loon"
        item["product_family"] = cleaned
        canonical = master_names.get(strain_key(cleaned)) or master_aliases.get(strain_key(cleaned))
        if canonical:
            item["strain"] = canonical
            item["master_strain"] = canonical
            item["strain_match_status"] = "master_exact"
        else:
            item.pop("master_strain", None)
            item["strain_match_status"] = "pending_master_review"
        if changed:
            counts["mn_loon_published_title_cleaned"] += 1
    assert not [item for item in result if re.match(r"(?i)^(?:mnl|mnloon|mn\\s+loon)\\s+", str(item.get("strain") or ""))], "MN Loon brand prefix escaped published catalog"
    # Canonicalize the reviewed FLOR/FLÖR typography across source feeds.
    # Source title and identity remain unchanged. Do not normalize unrelated
    # owner-approved brand distinctions (notably Popcorn / Zips).
    for item in result:
        if str(item.get("brand") or "").casefold() in {"flor", "flör"}:
            item["brand"] = "FLÖR"
    # Owner-approved source-ID brands must survive all import and dedup passes.
    for correction in corrections.values():
        if correction.get("status") != "approved" or not correction.get("brand"):
            continue
        if correction["id"] in merged_source_ids:
            continue
        matched_item = next((x for x in result if str(x.get("id")) == correction["id"]), None)
        if matched_item is None:
            continue
        expected_brand = ("FLÖR" if str(correction["brand"]).casefold() in {"flor", "flör"}
                          else correction["brand"])
        if matched_item.get("brand") != expected_brand:
            raise ValueError("Approved source brand drift: " + correction["id"] +
                             " expected " + expected_brand +
                             " got " + str(matched_item.get("brand")))
    # RCWM offers use their published advertised prices in all analytics.
    # Do not apply an RCWM-specific promotional adjustment.
    for item in result:
        item.pop("_source", None)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Publication gate: delimiter-bearing text can never be a strain identity.
    leaked = [(x.get("id"), x.get("strain")) for x in result
              if "|" in str(x.get("strain") or "") or "|" in str(x.get("master_strain") or "")]
    if leaked:
        raise ValueError("Delimiter leaked into published strain name: " + repr(leaked[:12]))
    audit_path = Path("reports/delimited_strain_review.json")
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps({
        "schema_version": 1, "held_count": len(delimiter_review),
        "held_observations": delimiter_review,
        "note": "Nonpublic review; raw source offers remain unchanged."
    }, indent=2) + "\n")
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    MASTER_REVIEW.write_text(json.dumps({"schema_version": 1, "source": "Strain Master",
        "held_count": 0, "pending_count": counts["pending_strain_master_review"],
        "candidates": [row for row in review if row.get("reason") == "not_in_strain_master"]}, indent=2) + "\n")
    REPORT.write_text(json.dumps({"published": len(result), "counts": dict(counts),
                                  "merged_source_ids": merged_source_ids,
                                  "unmatched_for_review": len(review),
                                  "review_sample": review[:200]}, indent=2) + "\n")
    # Spreadsheet-ready approval queue; no proposed name is automatically approved.
    pending = [row for row in review if row.get("reason") == "not_in_strain_master"]
    with MASTER_REVIEW_CSV.open("w", encoding="utf-8", newline="") as stream:
        fields = ["id", "retailer", "source", "raw_name", "proposed_strain",
                  "reparsed_candidate", "suggestions", "brand", "url", "reason", "review_status"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{**row, "suggestions": "; ".join(row.get("suggestions", []))} for row in pending])
    print("Unified catalog:", len(result), "offers;", counts["pending_strain_master_review"], "flagged for Strain Master review (visible pending)")

if __name__ == "__main__":
    main()
