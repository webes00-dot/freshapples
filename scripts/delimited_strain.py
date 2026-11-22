"""Conservative parsing of retailer pipe-delimited *product titles*.

The vertical bar is a field delimiter, never part of a cultivar name.
Only exact approved Strain Master/alias segments can become public identities.
Keep the unmodified source record for audit. Any ambiguity stays in review.
"""
import re

BRANDS = {
 "rcwm": "Redwood County Weed Management",
 "redwood county weed management": "Redwood County Weed Management",
 "avio": "Avio", "aquapotic": "Aquapotic",
 "verist fields": "Verist Fields", "mr. birch - little sticks": "Verist Fields",
 "unbound": "Unbound", "rythm": "RYTHM", "big dog": "Big Dog",
 "dizgo collective": "Dizgo Collective", "erba": "ERBA",
 "elevate botanicals": "Elevated Botanicals", "float cannabis": "Float Cannabis",
 "native care": "Native Care", "minny grown": "Minny Grown",
 "good green": "Good Green", "northpark": "Northpark",
 "bud doctor": "Bud Doctor", "lake leaf": "Lake Leaf",
 "stargaze": "Stargaze",
}
SKIP = re.compile(r"(?i)^(?:-?ix|(?:pre[- ]?roll|pre[- ]?packaged|flower)(?:[- ]?ix)?|"
                  r"pre[- ]?rolls?|prerolls?|hash rosin|jar|little sticks?|"
                  r"(?:distillate )?infused|(?:\d+(?:\.\d+)?|\.\d+)\s*(?:gm?|grams?)\s*(?:flower|vapes?|pre[- ]?rolls?)|"
                  r"\d+\s*(?:pk|pack|ct)|(?:pre[- ]?roll )?\d+\s*pk)$")
def k(text):
    return re.sub(r"\s+", " ", str(text or "").strip()).casefold()

def resolve_delimited_strain(title, canonical, aliases):
    if "|" not in str(title or ""):
        return None
    parts = [x.strip(" -\t\r\n") for x in str(title).split("|") if x.strip(" -\t\r\n")]
    candidates = []
    explicit_brands = []
    for part in parts:
        key = k(part)
        if key in BRANDS:
            explicit_brands.append(BRANDS[key])
            continue
        if SKIP.fullmatch(part):
            continue
        # A single observed strain token can contain a harmless product suffix;
        # never edit-distance match or take an arbitrary last pipe field.
        possible = [part]
        possible.append(re.sub(r"(?i)\s+\d+\s*$", "", part).strip())
        possible.append(re.sub(r"(?i)\s+(?:flower|pre[- ]?rolls?|infused)\s*$", "", part).strip())
        # Strong explicit producer prefix from retailer product titles. A
        # cultivar match must still be exact after removing the brand/form.
        # This recovers Float Magic Marker | size and Northpark OG Kush Cart |
        # size without inventing new strain or producer identities.
        cleaned = re.sub(r"(?i)^\$\s*\d+(?:\.\d+)?\s+off\s+", "", part).strip()
        for producer in sorted(BRANDS, key=len, reverse=True):
            if k(cleaned).startswith(producer + " "):
                explicit_brands.append(BRANDS[producer])
                remainder = cleaned[len(producer):].strip(" -")
                possible.extend([
                    remainder,
                    re.sub(r"(?i)\s+(?:hash\s+rosin\s+)?(?:disposable|cart|flower|pre[- ]?rolls?)\s*$","",remainder).strip(" -"),
                ])
                break
        for option in possible:
            key = k(option)
            cultivar = canonical.get(key) or aliases.get(key)
            if cultivar and cultivar not in candidates:
                candidates.append(cultivar)
                break
    if len(candidates) != 1 or len(set(explicit_brands)) > 1:
        return None
    parsed = {"strain": candidates[0]}
    if explicit_brands:
        parsed["brand"] = explicit_brands[0]
    if any(re.fullmatch(r"(?i)little\s+sticks?", x) for x in parts):
        parsed["product_variant"] = "Little Stick"
    if any(re.fullmatch(r"(?i)jar", x) for x in parts):
        parsed["product_variant"] = "Jar"
    return parsed
