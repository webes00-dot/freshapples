"""Owner-approved, source-constrained repairs for nine MNtrees scan defects.

Never edit original feeds or invent a cultivar from fuzzy similarity. The
catalog builder invokes this only for non-overridden observations and checks
candidate strain names against the approved Strain Master snapshot.
"""
import re
from urllib.parse import urlparse, unquote


def _key(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _verified(name, master, aliases):
    key = _key(name)
    if key in master:
        return master[key]
    target = aliases.get(key)
    if target and _key(target) in master:
        return master[_key(target)]
    return None


def repair_scan_identity(item, master, aliases):
    """Return an approved identity/variant, otherwise None (review or exclusion).

    Names are parsed only for specific source templates and exact master matches.
    Retailer name and product URL here are a source-identity guard, not an
    assertion of current live inventory or producer ownership.
    """
    title = str(item.get("raw_scanned_product_name") or item.get("product_name")
                or item.get("strain") or "").strip()
    strain = str(item.get("strain") or "").strip()
    retailer = str(item.get("retailer") or "")
    url = str(item.get("url") or "")
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    result = None

    # Greenhouse cards sometimes scrape an "add to cart" button as the title.
    # Recovery is permitted ONLY from a named flower-product URL where the
    # cultivar slug itself matches a canonical master label.
    if (host == "thegreenhousecannabisco.com"
            and re.fullmatch(r"(?:sale\s+)?0\s+0\s+in\s+cart", strain, re.I)):
        path = unquote(urlparse(url).path)
        m = re.search(r"/buds-(?:sativa|indica|hybrid)-([a-z0-9-]+?)-"
                      r"(?:\d+(?:-\d+)?g)-\d+(?:/|$)", path, re.I)
        if m:
            cultivar = _verified(m.group(1).replace("-", " "), master, aliases)
            if cultivar:
                result = {"strain": cultivar}

    # Green Goods titles: type + cultivar + named brand + merchandising grade.
    if host == "visitgreengoods.com":
        m = re.fullmatch(
            r"(?:hybrid|indica|sativa)\s+flower\s+(.+?)\s+"
            r"(RYTHM|Good Green|Vireo|Boundary Waters|Limited Salad|Simple)\s+"
            r"(Premium Flower|Mini Buds?|Mixed Buds?|Ground Flower|Whole Flower|Flower)",
            title, re.I)
        if m:
            cultivar = _verified(m.group(1), master, aliases)
            if cultivar:
                brands = {"rythm": "RYTHM", "good green": "Good Green",
                          "vireo": "Vireo", "boundary waters": "Boundary Waters",
                          "limited salad": "Limited Salad", "simple": "Simple"}
                result = {"strain": cultivar, "brand": brands[m.group(2).casefold()],
                          "product_variant": m.group(3).title()}

    # Green Apple uses "Brand Strain | size/format" and the scraper mistakenly
    # takes the final package segment as cultivar.
    if "green apple" in retailer.casefold():
        m = re.fullmatch(
            r"(Redwood County Weed Management|Minny Grown|Float Cannabis)\s+(.+?)"
            r"\s*\|\s*(?:(?:\d+\s*[- ]\s*Pack)\s*\|\s*)?"
            r"(?:\d+(?:\.\d+)?\s*(?:g|gm)\s*(?:Flower|Preroll|Pre[- ]?Roll))",
            title, re.I)
        if m:
            cultivar = _verified(m.group(2), master, aliases)
            if cultivar:
                brand_lookup = {"redwood county weed management": "Redwood County Weed Management",
                                "minny grown": "Minny Grown", "float cannabis": "Float Cannabis"}
                result = {"strain": cultivar, "brand": brand_lookup[m.group(1).casefold()]}

    # Waabigwan labels sometimes have an explicit 'Popcorn-' grade and
    # terminal separator. An unrecognized underlying cultivar stays in review.
    if "waabigwan" in retailer.casefold():
        m = re.fullmatch(r"(?:Popcorn\s*[-–]\s*)?(.+?)\s*[-–]\s*", strain, re.I)
        if m:
            cultivar = _verified(m.group(1), master, aliases)
            if cultivar:
                result = {"strain": cultivar}
                if re.match(r"Popcorn\s*[-–]", strain, re.I):
                    result["product_variant"] = "Popcorn"

    # Retailer promotion, explicit product brand and separately stated form.
    m = re.fullmatch(r"(?:ON SALE\s+)?FL[OÖ]R\s+(.+?)\s+Flower", title, re.I)
    if m:
        cultivar = _verified(m.group(1), master, aliases)
        if cultivar:
            result = {"strain": cultivar, "brand": "FLÖR"}

    # Explicit Verist name with lot-potency prefix. Preserve differing
    # source IDs, prices, retailer locations, weights and genuine variants.
    m = re.fullmatch(r"THC:\s*\d+(?:\.\d+)?%\s+VERIST\s+"
                     r"(Double Sour Grapes?)\s*\(\s*3\.5\s*g\s*\)", title, re.I)
    if m:
        cultivar = _verified("Double Sour Grape", master, aliases)
        if cultivar:
            result = {"strain": cultivar, "brand": "Verist Fields"}

    # Known transcription error in a named Unbound product, not a general
    # edit-distance alias for unrelated cultivar names.
    m = re.fullmatch(r"Unbound\s+Hawiaain\s+Fanta\s+3\.5g", title, re.I)
    if m:
        cultivar = _verified("Hawaiian Fanta", master, aliases)
        if cultivar:
            result = {"strain": cultivar, "brand": "Unbound"}

    # MN Roots labels the brand on both sides of the variant + strain.
    if "mn roots" in retailer.casefold() or "mnroots" in host:
        m = re.fullmatch(r"Rythm\s*\|\s*(Popcorn|Mixed Buds)\s*\|\s*"
                         r"(Velvet Glove)\s+RYTHM", title, re.I)
        if m:
            cultivar = _verified(m.group(2), master, aliases)
            if cultivar:
                result = {"strain": cultivar, "brand": "RYTHM",
                          "product_variant": m.group(1).title()}
    return result
