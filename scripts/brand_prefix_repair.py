"""Exact-source brand/variant title cleanup before the MNtrees catalog publisher.

This is not a fuzzy alias engine. Only approved brand/store and product-title
templates can be parsed, and the proposed cultivar must be in the Strain Master.
Retain immutable observed source names and every offered price/weight/URL.
"""
import re


def norm(text):
    return re.sub(r"\s+", " ", str(text or "").strip()).casefold()


def approved(name, canonical, aliases):
    key = norm(name)
    return canonical.get(key) or aliases.get(key)


def repair_brand_prefix_title(item, canonical, aliases):
    raw = str(item.get("strain") or item.get("product_name") or "").strip()
    name = re.sub(r"^(?:(?:OFFER CONDITIONS APPLY|OFFER BUY \d+|ON SALE)\s+)+", "", raw, flags=re.I).strip()
    retailer = str(item.get("retailer") or "").casefold()
    if not name:
        return None
    # Verist Fields prefixed product grades (including 5x .35g preroll).
    m = re.fullmatch(
        r"Verist(?:\s+Fields)?\s+(Gush\s+Kush|Swedish\s+OG|Mimosa\s+Ice|Valley\s+Frost)"
        r"(?:\s+(Little\s+Sticks))?"
        r"(?:\s+(?:(?:5\s*x\s*\.35|1|3\.5)\s*g(?:\s+Pre[- ]?Roll)?|Flower\s+3\.5g|3\.5))?",
        name, re.I,
    )
    if m:
        names = {"gush kush": "Gush Kush", "swedish og": "Swedish OG",
                 "mimosa ice": "Mimosa Ice", "valley frost": "Valley Frost"}
        canonical_strain = approved(names[norm(m.group(1))], canonical, aliases)
        if canonical_strain:
            result = {"strain":canonical_strain,"brand":"Verist Fields"}
            if m.group(2):
                result["product_variant"] = "Little Sticks"
            return result
    # Trailhead's Reserve is a product grade and not part of Octane Mintz.
    if re.fullmatch(r"Trailhead\s+Reserve\s+Octane\s+Mintz", name, re.I):
        strain = approved("Octane Mintz",canonical,aliases)
        if strain:
            return {"strain":strain,"brand":"Trailhead Cannabis","product_variant":"Reserve"}
    # The Highnorth prefix identifies the retailer source. Do not infer brand.
    m = re.fullmatch(
        r"Highnorth\s+(Froot\s+by\s+the\s+Foot|Mendo\s+Breath|Turtle\s+Taffy|White\s+Widow)"
        r"\s+Discovery\s+Pack\s*[-–]\s*2\s*g",
        name,re.I,
    )
    if m and "highnorth" in retailer:
        names = {"froot by the foot":"Froot by the Foot",
                 "mendo breath":"Mendo Breath","turtle taffy":"Turtle Taffy",
                 "white widow":"White Widow"}
        strain = approved(names[norm(m.group(1))],canonical,aliases)
        if strain:return {"strain":strain,"product_variant":"Discovery Pack"}
    # Rewind is explicit brand; the final words are format/weight, not strain.
    m = re.fullmatch(
        r"Rewind\s+(Aloha\s+Sugar|Daily\s+Grape|Kanobi\s+Sunset|Killer\s+Cupcake)"
        r"\s*[-–]\s*(?:\.5|0\.5)\s*g\s+"
        r"(?:Live\s+Rosin\s+Disposable|Distillate\s+Syringe)",
        name,re.I,
    )
    if m:
        names={"aloha sugar":"Aloha Sugar","daily grape":"Daily Grape",
               "kanobi sunset":"Kanobi Sunset","killer cupcake":"Killer Cupcake"}
        strain=approved(names[norm(m.group(1))],canonical,aliases)
        if strain:return {"strain":strain,"brand":"Rewind"}
    return None
