"""Product form evidence used before identity matching."""
import re
from urllib.parse import unquote, urlsplit

DETAIL = re.compile(r"/(?:pdp|product|p)/([^/]+)(?:/v/[^/]+)?$|/products/(?:[^/]+/)?([^/]+)$|/menu/[^/]+-\d+/([^/]+-\d+)$", re.I)
GEAR = re.compile(
    r"^\s*(?:gear|merch|accessor(?:y|ies))\b|\b(?:functional art|electronics/vaping|apparel|"
    r"hand[ -]?blown|dry pipe|water pipe|carb cap|lighter|pinchies?|grinders?|dab straw|rolling papers?|"
    r"rolling machine|plastic jar|chillum|ashtray|puffco|hoodies?|hoody|t-shirts?|crewneck|backpack|"
    r"rolling tray|kodo pro|boveda|zig[ -]?zag|empty cones|ocb|lookah|storage bag|ceramic taster|pipe cleaners|dugout|humidity control|glass spoon|shroom pipe|plastic jar|merch|ceramic cigarette taster|"
    r"batteries|battery|merch|sweatshirts?|shirts?|beanie|trucker hat|winter hat|sweat shirts?|cannanbis caps|robins crafts|blazy susan paper|perforated prism|grav.{0,15}taster|raw (?:classic )?(?:cones|papers)|papers? (?:ultra|organic)|dug ?out|glass spoon|"
    r"grow bag|roach wand|hemp wraps|pipe cleaners|seed pack|seeds|feminized)\b", re.I)
NONFLOWER = re.compile(r"\b(?:capsules?|topicals?|tinctures?|salve|balm|lotion|body oil|cbd oil|bath bomb|"
                       r"gummies|edibles?|seltzers?|single can|mocktail|cocktail|spirits mixer|hard candy|"
                       r"chocolate bar|beverages?|low potency hemp|lphe|fruit tonic|single shot|sparkling (?:cbd )?water|pretzels|cbd cream|cooling roll on|spectrum oil|roll-on|ice[d] tea|ginger ale|mojito|martini|infusion vial|lemonade shot|pet cbd|body oil|quick fix.{0,10}(?:gel|cream))\b", re.I)
FLAVOR = re.compile(r"\b(?:soda|root beer|elixir|shooter|sorbet|lemonade|chocolate|infusions?|pieces|tea)\b", re.I)
TARGET = re.compile(r"\b(?:flower|buds?|pre[- ]?rolls?|cartridges?|carts?|disposables?|dispo|vapes?|concentrates?|distillate|rosin|resin|wax|badder)\b", re.I)
NON_TARGET_PATH = re.compile(r"/(?:edibles?|beverages?|accessories|apparel|gear|seeds|topicals?|tinctures?|functional-art)(?:/|$)", re.I)

def product_slug(url):
    match = DETAIL.search(unquote(urlsplit(url).path).rstrip("/"))
    return next(x for x in match.groups() if x).replace("-", " ") if match else ""

def excluded(title, url):
    path = unquote(urlsplit(url).path)
    if GEAR.search(title) or NON_TARGET_PATH.search(path) or title.strip().lower() in {"previously", "2 for"}:
        return True
    if NONFLOWER.search(title):
        return True
    if TARGET.search(title):
        return False
    if re.search(r"\b(?:soda|rootbeer|root beer|tonic|shooter)\b", title, re.I) and not re.search(r"\d\s*(?:%|g\b)", title, re.I):
        return True
    return bool(re.search(r"\d\s*mg\b", title, re.I) and
                (FLAVOR.search(title) or re.search(r"\d+\s*(?:ct|count)\b|\b(?:12|16)\s*(?:fl\.?\s*)?oz\b", title, re.I)))

def flower_weight(title, grams, count):
    if count or grams not in {3.5, 4, 7, 8, 28} or re.search(r"\b(?:pack|pk|ct|count)\b|\d\s*[x×]\s*\d", title, re.I):
        return False
    weights = re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:g|grams?)\b", title, re.I)
    distinct = {float(weight) for weight in weights}
    for denominator in re.findall(r"(?<![\d/])1\s*/\s*(8|4|2)\s*(?:oz|ounces?)\b", title, re.I):
        distinct.add(28 / int(denominator))
    return distinct == {grams}
