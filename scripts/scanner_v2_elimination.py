"""Resolve catalog identity from captured product evidence and approved names."""
import re
import unicodedata
from functools import lru_cache
from urllib.parse import unquote, urlsplit

from scanner_v2_scope import excluded, flower_weight, product_slug, TARGET
from unified_scan_rules import clean_candidate, WEIGHT, PACK, THC, extract_weight, infer_category

FORM = re.compile(r"(?i)\b(?:pre[- ]?rolls?|joints?|blunts?|flower|buds?|vapes?|vaporizers?|"
                  r"cartridges?|carts?|disposables?|510|concentrates?|extracts?|hash|"
                  r"wax|shatter|badder|budder|crumble|rosin|resin|pre[- ]?packed|"
                  r"pre[- ]?packaged|infused|premium|small buds|mixed buds|"
                  r"craft cannabis|sativa(?:-dom(?:inant)?)?|indica(?:-dom(?:inant)?)?|"
                  r"hybrid|distillate|live|cured)\b")
POTENCY = re.compile(r"(?i)\b(?:THC|CBD|CBG|CBC|TERPS?)\s*:?\s*\d+(?:\.\d+)?\s*%?")
PER_100 = re.compile(r"(?i)\b\d+(?:\.\d+)?\s*(?:mg|milligrams?)\b")
LEADING_BADGE = re.compile(r"(?i)^\s*(?:(?:staff pick|on sale|sale|deal)(?:\b|!)\s*[!:|–-]*\s*)+")
TRAIL = re.compile(r"(?i)\b(?:spend more|offer conditions apply|add to cart)\b.*$")
CARD_BRAND = re.compile(
    r"(?im)(?:\bbrand\s*[:|]|^[ \t]*(?:(?:made|grown|produced|"
    r"flower|pre[- ]?rolls?|vapes?|concentrates?) )?by[ \t]+)"
    r"\s*([^\r\n|$]+)")
NON_TARGET = re.compile(
    r"(?i)(?:/(?:edibles?|beverages?|drinks?|topicals?|tinctures?|accessories)/|"
    r"\b(?:gummies|gummy|edibles?|beverages?|drinks?|seltzers?|soda|root[ -]beer float|topicals?|"
    r"tinctures?|salves?|balms?|cream|lotion|battery|charger|grinder)\b)")
WEIGHT_TOKEN = re.compile(r"(?i)(?<![a-z])(?:\d+(?:\.\d+)?|\.\d+)\s*(?:g|gm|grams?|oz)\b")
PACK_EXPR = re.compile(
    r"(?i)(?<![\w.])(?P<unit>\d+(?:\.\d+)?|\.\d+)\s*(?:g|grams?)"
    r"\s*(?:x|\u00d7|each\s*[xX]?)\s*(?P<count>\d{1,2})(?!\d)")
COUNT_FIRST_PACK = re.compile(
    r"(?i)(?<![\w.])(?P<count>\d{1,2})\s*[x×]\s*"
    r"(?P<unit>\d+(?:\.\d+)?|\.\d+)\s*(?:g|grams?)\b")
DECORATION = re.compile(r"(?i)\b(?:50/50|1/8\s*oz|1/4\s*oz|1/2\s*oz|"
                         r"\d{1,2}\s*(?:pack|pk|ct|count))\b")
ID_NUMBER = re.compile(r"(?<![a-z])\d{8,12}(?![a-z])")
MAX_TITLE = 750


def ascii_words(value):
    value = unicodedata.normalize("NFKD", str(value or "")).casefold()
    value = "".join(x for x in value if not unicodedata.combining(x))
    # Keep punctuation inside candidate names as optional token separators.
    return re.findall(r"[a-z0-9]+", value)


@lru_cache(maxsize=8192)
def entity_pattern(name):
    words = ascii_words(name)
    if not words:
        return None
    # Do not infer short names like 'OG' or 'A' from random title fragments.
    if len("".join(words)) < 3:
        return None
    return re.compile(r"(?<![a-z0-9])" + r"[^a-z0-9|·•]*".join(map(re.escape, words))
                      + r"(?![a-z0-9])", re.I)


def folded(value):
    value = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return "".join(x for x in value if not unicodedata.combining(x))


@lru_cache(maxsize=8192)
def first_token(alias):
    tokens = ascii_words(alias)
    return tokens[0] if tokens else ""


def entity_matches(text, aliases):
    """Return bounded, approved aliases; no fuzzy merging or partial tokens."""
    normalized = folded(text)
    tokens = set(re.findall(r"[a-z0-9]+", normalized))
    found = {}
    for alias, canonical in aliases.items():
        if first_token(alias) not in tokens:
            continue
        pat = entity_pattern(alias)
        if not pat:
            continue
        for match in pat.finditer(normalized):
            if canonical not in found or len(match.group()) > len(found[canonical][1]):
                found[canonical] = (match.span(), match.group(), alias)
    return found


def brand_library(brands):
    aliases = {}
    for row in brands:
        canonical = str(row.get("name") or "").strip()
        if not canonical:
            continue
        for alias in [canonical, *(row.get("aliases") or [])]:
            alias = str(alias or "").strip()
            if alias and len("".join(ascii_words(alias))) >= 3:
                if alias in aliases and aliases[alias] != canonical:
                    # Ambiguous alias deliberately cannot resolve.
                    aliases[alias] = None
                else:
                    aliases[alias] = canonical
    return {a: c for a, c in aliases.items() if c}


def strain_library(master):
    canonical = master.get("canonical_strains", [])
    aliases = {str(x): str(x) for x in canonical if str(x).strip()}
    for alias, target in (master.get("approved_aliases") or {}).items():
        if target in canonical:
            aliases[str(alias)] = str(target)
    return aliases


def cleaned_title(raw):
    text = folded(raw)
    text = LEADING_BADGE.sub("", text)
    text = re.sub(r"\b(?:best seller|staff pick|bundle|on sale|offer conditions apply)\b", " ", text)
    text = TRAIL.sub(" ", text)
    text = POTENCY.sub(" ", text)
    text = THC.sub(" ", text)
    text = ID_NUMBER.sub(" ", text)
    text = PER_100.sub(" ", text)
    return text


def best_match(matches, source, forbidden=()):
    """Only one distinct canonical entity; suppress nested substring matches.

    A cultivar may be nested inside another name ('Guava' / 'Guava Cake').
    Pick the longest only when the shorter occurrence is fully contained in
    that longer match; otherwise HOLD conflicting candidates.
    """
    if not matches:
        return None, "no_library_hit"
    ordered = sorted(matches.items(), key=lambda x: len(x[1][1]), reverse=True)
    winner, evidence = ordered[0]
    a, b = evidence[0]
    if len(ordered) == 1:
        return winner, "unique_bounded_alias"
    for candidate, entry in ordered[1:]:
        left, right = entry[0]
        if left >= a and right <= b:
            continue
        return None, "multiple_distinct_master_matches"
    return winner, "unique_longest_bounded_alias"


def package_size(title, source_metadata, category, product_url=""):
    """Resolve unit x count and ounce/gram equivalence without guessing."""
    # Normalize common fractional grams before WEIGHT can read the denominator as grams.
    title = re.sub(r"(?i)(?<![\w./])1\s*/\s*([248])\s*(?:g|grams?)\b",
                   lambda m: f"{1 / int(m[1])}g", title)
    per = PACK_EXPR.search(title) or COUNT_FIRST_PACK.search(title)
    if per:
        unit, count = float(per["unit"]), int(per["count"])
        total = round(unit * count, 3)
        if 0 < total <= 28:
            return total, count, "unit_times_quantity"
    from unified_scan_rules import WEIGHT, OZ
    matches = list(WEIGHT.finditer(title))
    grams = []
    for m in matches:
        qty = OZ.get(re.sub(r"\s+", "", m.group("oz"))) if m.group("oz") else float(m.group("grams"))
        if qty and 0 < qty <= 28:
            grams.append(round(qty, 3))
    count_match = PACK.search(title)
    count = int(count_match.group(1)) if count_match else None
    if count and count > 1 and len(set(grams)) == 2:
        smallest, largest = min(grams), max(grams)
        if abs(smallest * count - largest) < .012:
            return largest, count, "unit_and_total_agree"
    if grams and len(set(grams)) == 1:
        if count and count > 1:
            # Explicitly labeled unit weights only. An unexplained 1g 2ct
            # might be the total pack weight; do not assume a product size.
            has_unit = re.search(r"(?i)(?:\bg\s+ea\b|(?<=g)\s+ea\b|per\s*(?:joint|stick|unit)|each|"
                                 r"\d+(?:\.\d+)?\s*g\s*(?:pre[- ]?roll|joint))", title)
            if has_unit:
                return round(grams[0]*count, 3), count, "explicit_unit_times_count"
            return None, count, "ambiguous_unit_vs_total"
        return grams[0], count, "unique_weight"
    if grams:
        parenthetical = re.search(r"(?i)\((\d{1,2})\)\s*(\d+(?:\.\d+)?|\.\d+)\s*g\s*pre[- ]?rolls?\b", title)
        if parenthetical:
            units, unit_g = int(parenthetical[1]), float(parenthetical[2])
            total = round(units * unit_g, 3)
            if units > 1 and 0 < total <= 28 and set(grams) == {unit_g, total}:
                return total, units, "unit_and_total_agree"
        before, marker, after = title.lower().partition(" selected ")
        if marker and after.strip():
            option = re.search(r"(\d+\s*[- ]pack\s*\(\s*(?:\d+(?:\.\d+)?|\.\d+)\s*g\s*ea\s*\)|(?:\d+(?:\.\d+)?|\.\d+)\s*g)\s*$", before)
            slug = product_slug(product_url)
            if option and slug:
                tokens = re.findall(r"[a-z0-9]+", option[1])
                slug_tokens = re.findall(r"[a-z0-9]+", slug.lower())
                # Some menus encode 0.5g as 05g in the option's product link.
                option_key = " ".join(re.findall(r"[a-z0-9]+", option[1].replace(".", "")))
                if (" "+option_key+" ") in (" "+" ".join(slug_tokens)+" ") or (" "+" ".join(tokens)+" ") in (" "+" ".join(slug_tokens)+" "):
                    value, units, _ = package_size(option[1], {}, category)
                    if value:
                        return value, units, "selected_option_confirmed_by_product_url"
        return None, count, "conflicting_weights"
    return None, count, "missing_weight"


def rerank(row, observation, master, brands, approved_brands=None):
    """Recheck scope and resolve identity against the approved catalog."""
    initially_ready = row.get("identity_status") == "ready"
    raw = str(observation.get("raw_title") or row.get("raw_title") or "")
    product_url = str(observation.get("product_url") or row.get("product_url") or "")
    source_url = str(observation.get("source_url") or row.get("source_url") or "")
    metadata = observation.get("source_metadata") or {}
    proposed = dict(row)
    evidence = {"brand_library": "approved_sheet_index" if approved_brands is not None else "fixture_or_legacy"}
    if excluded(raw, product_url):
        proposed["identity_status"] = "needs_review"
        proposed["identity_reasons"] = ["non_target_category"]
        proposed["resolution_pass"] = "library_elimination_v2"
        proposed["resolution_evidence"] = {"filter": "non_target_product"}
        return proposed
    text = cleaned_title(raw)
    # Brand matching uses known master aliases anywhere in the title (not
    # only prefixes), or explicit source brand. Retailer name is never a brand.
    master_brands = brand_library(approved_brands if approved_brands is not None else brands)
    # Approved here for producer attribution in product sources.
    if "Verist Fields" in master_brands.values():
        master_brands.setdefault("Verist", "Verist Fields")
    # Bounded commercial labels for existing canonical producers.
    product_labels = {
        "Campfire": "Campfire Cannabis", "Trailhead": "Trailhead Cannabis",
        "North Park": "Northpark", "Redwood Weed Management": "Redwood County Weed Management",
        "Valhalla": "Valhalla Cannabis", "Emerald Fire": "Emerald Farms",
        "Elevate": "Elevate Botanicals",
    }
    if re.search(r"\bbig dogs?\b", text) and re.search(r"\bpre[- ]?roll", text) and re.search(r"(?<!\d)0?\.75\s*g", text):
        product_labels.update({"Big Dog": "Dogwalkers", "Big Dogs": "Dogwalkers"})
    if re.search(r"\bcured resin\b", text):
        product_labels["Sappy Pappy"] = "Verist Fields"
    canonical_names = set(master_brands.values())
    for label, producer in product_labels.items():
        if producer in canonical_names:
            master_brands.setdefault(label, producer)
    title_brands = master_brands
    if not TARGET.search(text) and not re.search(r"\bby\s+float\b", text):
        # A bare 'Float' can also be a flavor or a beverage name.
        title_brands = {alias: name for alias, name in master_brands.items()
                        if not (alias.casefold() == "float" and name == "Float Cannabis")}
    brand_found = entity_matches(text, title_brands)
    retailer_names = set(entity_matches(observation.get("retailer", ""), master_brands))
    retailer_names.update({"Unwind", "Feelin' MN"})
    for name in retailer_names:
        # A vertically integrated operator may explicitly label its own SKU.
        # A captured retailer name alone is never producer evidence.
        if name in {"Waabigwan Mashkiki", "Aurora Cannabis", "Marawanna"} and name in brand_found and len(brand_found) == 1:
            continue
        if name in brand_found and not re.search(r"\bby\s+" + re.escape(brand_found[name][1]) + r"\b", text):
            del brand_found[name]
    if proposed.get("brand") in retailer_names or proposed.get("brand") not in master_brands.values():
        proposed["brand"] = ""
    title_brand, brand_status = best_match(brand_found, text)
    sources = {"title": title_brand} if title_brand else {}
    declared = observation.get("source_brand_text") or ""
    card_brands = CARD_BRAND.findall(str(metadata.get("card_text") or ""))
    source_matches = []
    slug = product_slug(product_url)
    if slug:
        url_matches = entity_matches(slug, title_brands)
        for name in retailer_names:
            url_matches.pop(name, None)
        url_brand, url_status = best_match(url_matches, slug)
        if url_status == "multiple_distinct_master_matches":
            brand_status = url_status
        if url_brand:
            source_matches.append(("product_url", url_matches[url_brand][2]))
    if declared:
        source_matches.append(("source_brand", str(declared)))
    source_matches.extend(("card_brand", value) for value in card_brands)
    conflicting_brand = brand_status == "multiple_distinct_master_matches"
    aliases = {brand_found[title_brand][2]} if title_brand else set()
    for source, value in source_matches:
        matches = entity_matches(value, master_brands)
        candidate, status = best_match(matches, value)
        if status == "multiple_distinct_master_matches" or (candidate and sources and
                candidate not in sources.values()):
            conflicting_brand = True
        if candidate:
            sources[source] = candidate
            aliases.add(matches[candidate][2])
            if not title_brand:
                brand_status = status
    brand = next(iter(sources.values()), None)
    if conflicting_brand:
        brand = None
        brand_status = "multiple_distinct_master_matches"
        proposed["brand"] = ""
    if brand:
        proposed["brand"] = brand
        evidence["brand"] = {"canonical": brand, "basis": brand_status,
                             "aliases": sorted(aliases), "sources": sorted(sources)}
    elif not proposed.get("brand"):
        evidence["brand"] = {"status": brand_status}
    # Strain matching eliminates brand tokens from the whole title. A brand
    # and strain may occur in either order, and repeats are allowed.
    for name, label in (("Zips", "Zips Popcorn"), ("Verist Fields", "Little Stick")):
        token = "popcorn" if name == "Zips" else "little stick"
        if brand == name and re.search(r"\b" + token + r"\b", text):
            proposed["product_line"] = label
    if brand == "Dogwalkers" and re.search(r"\bbig dogs?\b", text):
        proposed["product_line"] = "Big Dog"
    if brand == "Verist Fields" and "sappy pappy" in text:
        proposed["product_line"] = "Sappy Pappy"
    remaining = text
    if brand:
        brand_aliases = [alias for alias, canonical in title_brands.items() if canonical == brand]
        for alias in sorted(brand_aliases, key=len, reverse=True):
            pat = entity_pattern(alias)
            if pat:
                remaining = pat.sub(" ", remaining)
    # Known descriptive terms removed for matching only. Never remove
    # constituent cultivar words such as Sour, OG, Purple, Flower, or Kush
    # blindly from a master strain match: compare the raw remaining text too.
    strain_aliases = strain_library(master)
    found = entity_matches(remaining, strain_aliases)
    strain, strain_status = best_match(found, remaining)
    if strain:
        proposed["strain"] = strain
        evidence["strain"] = {"canonical": strain, "basis": strain_status,
                              "alias": found[strain][2]}
    elif initially_ready and strain_status == "no_library_hit" and proposed.get("strain") in master.get("canonical_strains", []):
        strain = proposed["strain"]
    else:
        candidate = re.sub(r"\b(?:hybrid|indica|sativa)(?:\s*/\s*(?:hybrid|indica|sativa))?\b", " ", POTENCY.sub(" ", raw), flags=re.I)
        proposed["strain"] = clean_candidate(candidate, brand or "").strip(" -|/")
    # Category from product form + context, NOT generic retailer identity.
    form_title = re.sub(r"\b(?:in|add to) cart\b", " ", raw, flags=re.I)
    category = infer_category(form_title, product_url, "", source_url)
    explicit_form = infer_category(form_title, "", "", "")
    if not explicit_form and re.search(r"/cartsvapes(?:/|$)", urlsplit(product_url).path, re.I):
        category = "Vape"
        evidence["category_basis"] = "product_url_category"
    elif not explicit_form and re.search(r"\bdeli[- ]style\b|\bpre[- ]pack(?:aged)?\s*\(popcorn\)", raw, re.I):
        category = "Flower"
        evidence["category_basis"] = "flower_product_descriptor"
    if not category:
        hint = str(metadata.get("category_hint_unverified") or "")
        if hint.lower() in ("flower", "preroll", "vape", "concentrates"):
            category = infer_category("", product_url, hint, source_url)
            evidence["category_hint"] = "adapter_hint_needs_corrob"
    if re.search(r"\bdistillate\b", raw, re.I) and not infer_category(form_title, "", "", ""):
        category = "Vape" if category == "Vape" else "Concentrates"
        evidence.pop("category_hint", None)
    if initially_ready and not evidence.get("category_basis") and not re.search(r"\bdistillate\b", raw, re.I) and not infer_category(form_title, "", "", ""):
        category = row.get("category") or category
    if category:
        proposed["category"] = category
    package_g, count, weight_status = package_size(raw, metadata, category, product_url)
    if package_g is not None:
        proposed["package_g"] = package_g
        if count:
            proposed["pack_count"] = count
    if (not category or (category == "Flower" and evidence.get("category_hint"))) and flower_weight(raw, proposed.get("package_g"), proposed.get("pack_count")):
        proposed["category"] = category = "Flower"
        evidence.pop("category_hint", None)
        evidence["category_basis"] = "single_flower_package_weight"
    if weight_status == "conflicting_weights":
        proposed["package_g"] = None
    evidence["weight"] = weight_status
    reasons = []
    if not proposed.get("brand") or brand_status == "multiple_distinct_master_matches":
        reasons.append("missing_or_conflicting_approved_brand")
    if strain_status == "multiple_distinct_master_matches":
        reasons.append("missing_or_conflicting_approved_strain")
    elif not strain:
        reasons.append("strain_not_in_master")
    if not proposed.get("category"):
        reasons.append("missing_type")
    if proposed.get("package_g") is None:
        reasons.append(weight_status)
    if category and package_g is not None and not (0 < package_g <= 28):
        reasons.append("invalid_weight")
    # A second-pass guess of the category from adapter hint alone isn't proof.
    if evidence.get("category_hint"):
        reasons.append("category_only_adapter_hint")
    proposed["identity_status"] = "needs_review" if reasons else "ready"
    proposed["identity_reasons"] = reasons
    proposed["resolution_pass"] = "library_elimination_v2"
    proposed["resolution_evidence"] = evidence
    return proposed
