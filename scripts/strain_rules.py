"""Canonical strain matching and user-approved MNtrees naming rules.

Unknown names are retained, never silently mapped to a different strain.
"""
import json
import re
from pathlib import Path

DATABASE = Path("data/strain_types.json")
ALIASES = {
    "sky walker": "Skywalker",
    "skywalker strain": "Skywalker",
    "skywalker flower": "Skywalker",
    "sky walker og": "Skywalker OG",
    "skywalker og flower": "Skywalker OG",
    "sky walker kush": "Skywalker Kush",
    "skywalker kush flower": "Skywalker Kush",
    "froot by the foot": "Froot by the Foot",
    "cereal milk blend": "Cereal Milk",
    "sunset sherbert": "Sunset Sherbet",
    "grandaddy purple": "Granddaddy Purple",
    "grand daddy purp": "Granddaddy Purple",
    "granddaddy purple": "Granddaddy Purple",
    "looner wild grape": "Wild Grape",
    "looner looner wild grape": "Wild Grape",
    "elevate strawberry lemonade": "Strawberry Lemonade",
    "elevated botanicals strawberry lemonade": "Strawberry Lemonade",
    "grand daddy purple": "Granddaddy Purple",
    "granddaddy purp": "Granddaddy Purple",
    "cannabis turtle taffy": "Turtle Taffy",
    "cannabis fog dog": "Fog Dog",
    "trailhead cherry lady slipper": "Cherry Lady Slipper",
    "dizgo medusa": "Medusa",
    "fruit by the foot": "Froot by the Foot",
    "government orange": "Government Oranges",
    "government oranges": "Government Oranges",
    "government orange alpha": "Government Oranges",
    "government oranges alpha": "Government Oranges",
    "government oranges sour": "Government Oranges",
    "government oranges (sour)": "Government Oranges",
    "gg4": "Gorilla Glue #4",
    "gg#4": "Gorilla Glue #4",
    "gorilla glue 4": "Gorilla Glue #4",
    "gorilla glue #4": "Gorilla Glue #4",
    "gods breath": "God's Breath",
    "god's breath": "God's Breath",
    "hawiaain fanta": "Hawaiian Fanta",
    "reserve killer cupcake": "Killer Cupcake",
    "the soap": "Soap",
    "trop cherry": "Tropicana Cherry",
    "tropical cherry": "Tropicana Cherry",
    "tropicana cherry": "Tropicana Cherry",
    "turtletaffy": "Turtle Taffy",
    "runtz s1": "Runtz",
    "cherry k": "Cherry Kush",
    "runtz s1": "Runtz",
    "the soap": "Soap",
    "cultivation campfire cannabis soap": "Soap",
    "select granola funk": "Granola Funk",
    "co. lime ice": "Lime Ice",
    "tricross 3 pck": "TriCross",
    "cherry k 3 pck": "Cherry Kush",
    "the soap": "Soap",
    "alien rock candy-": "Alien Rock Candy",
    "auto pilot": "Autopilot",
    "autopilot": "Autopilot",
    "auto pilot - distillate infused pre roll": "Autopilot",
    "autopilot-infused preroll-packaged preroll": "Autopilot",
    "apple fritter flower flower": "Apple Fritter",
}
BRAND_ALIASES = {    "elevate": "Elevated Botanicals",    "elevated botanicals": "Elevated Botanicals",    "elevate botanicals": "Elevated Botanicals",
    "r & d pharms": "R & D Farms",    "r and d pharms": "R & D Farms",
    "r & d farms": "R & D Farms",    "r d pharms": "R & D Farms",
    "r d farms": "R & D Farms", "rd farms": "R & D Farms",
    "rd pharms": "R & D Farms", "r and d farms": "R & D Farms",
    "r and d pharm": "R & D Farms", "r & d pharm": "R & D Farms",
    "little stick": "Verist Fields",    "little sticks": "Verist Fields",
    "big stick": "Verist Fields",    "big sticks": "Verist Fields",    "mnloon": "MN Loon",    "mn loon": "MN Loon",    "mnl": "MN Loon",
    "aurora cannabis": "Aurora",
    "aurora cannabis mn dispensary": "Aurora",
    "aurora's": "Aurora",
    "aurora cannabis llc": "Aurora",
    "float canna": "Float Cannabis",
    "d'ope": "D'Ope",
    "d’ope": "D'Ope",
    "dizgo": "Dizgo Collective",
    "nativecare": "Native Care",
    "flor fina": "FLÖR",
    "mr. birch": "Verist Fields",
    "mr birch": "Verist Fields",
    "big dog": "Big Dog",
    "big dogs": "Big Dog",
    "grasslandz": "Grasslandz",
    "grasslands": "Grasslandz",
    "popcorn": "Zips",
    "zips": "Zips",
    "bud doctor": "Bud Doctor",
    "the bud doctor": "Bud Doctor",
    "unbound": "Unbound",
    "unbound cannabis": "Unbound",
    # THC Minnesota source aliases: retain true separate brands.
    "flor": "FLÖR",
    "flör": "FLÖR",
    "flor fina": "FLÖR",
    "avio supply co.": "Avio",
    "zips cannabis": "Zips",
    "northpark cannabis co.": "Northpark",
    "trailhead cannabis co.": "Trailhead Cannabis",
    "the greenest pastures": "Greenest Pastures",
    "trawa": "Trawa",
    "pot corn": "Potcorn",
    "redwood weed management": "Redwood County Weed Management",
    "verist": "Verist Fields",
    "mischief": "Mischief Cannabis",
    "valhalla cannabis co": "Valhalla Cannabis",
    "valhalla cannabis co.": "Valhalla Cannabis",
    "grasslandz": "Grasslandz",
    "grasslandz cannabis": "Grasslandz",
    # Owner confirms Grasslands is an alias of Grasslandz.
}
INVALID = re.compile(r"^(?:hybrid|indica|sativa|flower|pre[- ]?roll|thc|cbd|0\s+0\s+in|&shine|\.5gm\s+vapes|(?:little|big)\s+sticks?)$", re.I)
NON_FLOWER = re.compile(r"\b(?:vape|vapes|cartridge|concentrate|edible|gummy|gummies|tincture|beverage|topical)\b", re.I)
PROMO = re.compile(r"^\s*(?:\$\s*\d+(?:\.\d+)?\s*off|sale|special)\s+", re.I)
PREFIX = re.compile(r"^(?:pre[- ]?packed|small buds|select)\s+", re.I)

def normalize_name(name):
    name = PROMO.sub("", str(name or "").strip())
    name = name.split("|")[-1].strip()
    name = PREFIX.sub("", name).strip()
    return re.sub(r"\s+", " ", name).strip(" -")

GOVERNMENT_ORANGES = re.compile(
    r"\bgovernment\s+oranges?\b(?:\s+\(?(alpha|sour)\b)?", re.I)


def government_oranges_variant(*titles):
    """Return the offer label, an empty string for plain Oranges, or None."""
    variant = None
    for title in titles:
        match = GOVERNMENT_ORANGES.search(str(title or ""))
        if match and match.group(1):
            return match.group(1).title()
        if match:
            variant = ""
    return variant

# Owner-confirmed brand association. Only source-specific associations belong here;
# other brands are inferred from a unique set of explicitly branded catalog offers.
OWNER_STRAIN_BRANDS = {"alien rock candy": "Native Cuts", "animal scout": "RYTHM", "autopilot": "Avio", "beaver cookies": "Green Goods", "hyperion f1": "Dizgo Collective"}

# The brand is explicit in the title; only the residual verified strain token is
# looked up. Keep extraction independent of strain classification availability.
RCWM_BRAND = "Redwood County Weed Management"
RCWM_KNOWN_STRAINS = {
    "cake mix": "Cake Mix",
    "cap junky": "Cap Junky",
    "halle berry": "Halle Berry",
    "lemon cherry gelato": "Lemon Cherry Gelato",
    "sunset tea": "Sunset Tea",
    "gastro pop": "Gastro Pop",
    "jelly breath": "Jelly Breath",
    "apple fritter": "Apple Fritter",
}
RCWM_PREFIX = re.compile(r"^\s*redwood\s+county\s+weed\s+management\b", re.I)
RCWM_SIZE = re.compile(r"(?:[-\s]+(?:1(?:[.,]0)?|3(?:[.,]5)?)\s*(?:g|gm|grams?)?|[-\s]+1g|[-\s]+3[.,]5)\s*$", re.I)
RCWM_COUNT = re.compile(r"(?:[-\s]+1\s*(?:ct|count))\s*$", re.I)
RCWM_FORMAT = re.compile(r"(?:[-\s]+(?:flower|pre[-\s]?rolls?|preroll))\s*$", re.I)
RCWM_MARKER = re.compile(r"(?:^|[-\s]+)rcwm(?:[-\s]+|$)", re.I)


def parse_rcwm_title(title):
    """Resolve explicitly branded RCWM products, without guessing a strain."""
    raw = str(title or "").strip()
    match = RCWM_PREFIX.match(raw)
    if not match:
        return None
    rest = raw[match.end():].strip(" -")
    # Listings also use "Preroll | Gastro Pop | 1g | RCWM" or
    # "Gastro Pop | 3.5gm Flower". The item preceding the size is the strain.
    if "|" in rest:
        parts = [part.strip(" -") for part in rest.split("|") if part.strip(" -")]
        if parts and re.fullmatch(r"pre[- ]?rolls?", parts[0], re.I) and len(parts) > 1:
            rest = parts[1]
        elif parts:
            rest = parts[0]
    # The scanner sometimes starts the SKU with 'Preroll-RCWM-...'.
    rest = re.sub(r"^pre[-\s]?roll[-\s]+", "", rest, flags=re.I)
    rest = RCWM_MARKER.sub(" ", rest).strip(" -")
    for _ in range(5):
        prev = rest
        rest = RCWM_COUNT.sub("", rest).strip(" -")
        rest = RCWM_SIZE.sub("", rest).strip(" -")
        rest = RCWM_FORMAT.sub("", rest).strip(" -")
        if rest == prev:
            break
    rest = RCWM_MARKER.sub(" ", rest).strip(" -")
    rest = re.sub(r"\bcapjunky\b", "Cap Junky", rest, flags=re.I)
    rest = re.sub(r"\s+", " ", rest).strip(" -")
    # Consult the versioned strain lookup first, then confirmed owner exceptions
    # whose names are not yet present in the type/classification database.
    try:
        database = json.loads(DATABASE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        database = {}
    strain = RCWM_KNOWN_STRAINS.get(rest.casefold())
    if not strain and rest.casefold() in database:
        strain = rest
    return {"strain": strain, "brand": RCWM_BRAND} if strain else None


SAPPY_PAPPY_CULTIVARS = {
    "dream berry": "Dream Berry",
    "glacier valley sour": "Glacier Valley Sour",
    "sour luxx": "Sour Luxxe",
    "sour luxxe": "Sour Luxxe",
}

def parse_sappy_pappy_title(name):
    """Verist Sappy Pappy is a resin product line, never a cultivar."""
    title = str(name or "").strip()
    if not re.search(r"\bsappy\s+pappy\b", title, re.I):
        return None
    patterns = (
        r"(?:verist(?:\s+fields)?\s+){0,2}\|?\s*(?:cured\s+(?:live\s+)?resin\s*\|\s*)?sappy\s+pappy\s*\|\s*(.+?)(?:\s*\|\s*1\s*g)?",
        r"(?:verist(?:\s+fields)?\s+)?sappy\s+pappy(?:\s+by\s+verist\s+fields)?\s+(.+?)(?:\s+1\s*g\s+cured\s+(?:live\s+)?resin)?",
        r"(.+?)\s*[-|]\s*cured\s+(?:live\s+)?resin\s*[-|]\s*sappy\s+pappy(?:\s*[-|]\s*1\s*g)?",
    )
    for pattern in patterns:
        m = re.fullmatch(pattern, title, re.I)
        if not m:
            continue
        candidate = re.sub(r"\s+", " ", m.group(1)).strip(" |–-")
        strain = SAPPY_PAPPY_CULTIVARS.get(candidate.casefold())
        if strain:
            return {"strain": strain, "brand": "Verist Fields",
                    "product_variant": "Sappy Pappy"}
    return None


def identify_product(name):
    """Return only narrowly confirmed strain/brand parsing rules."""
    raw = str(name or "").strip()
    clean = re.sub(r"(?i)^(?:(?:ON SALE|OFFER CONDITIONS APPLY|OFFER BUY \d+)\s+)+", "", raw)
    sappy = parse_sappy_pappy_title(clean)
    if sappy:
        return sappy
    # Aurora's actual 3.5g menu title is Strawneapple, not Strawnapple.
    if re.fullmatch(r"aurora\s+cannabis\s+(?:llc\s+)?strawneapple(?:\s*\|\s*3\.5\s*g)?", clean, re.I):
        return {"strain": "Strawneapple", "brand": "Aurora"}
    # Exact source-title templates: normalize before resolving against Strain Master.
    # Preserve observed package size, price, original product name and source URL.
    public_titles = (
        (r"d['’]ope(?:\s+cannabis)?\s+anthos\s+blend\s*\|?", "Anthos Blend", "D'Ope"),
        (r"minny\s+grown(?:\s+minny\s+grown)?\s*(?:\|\s*flower\s*\|?\s*|\s+)franken\s*pine", "Franken Pine", "Minny Grown"),
        (r"minny\s+grown\s+sour\s+lemons", "Sour Lemons", "Minny Grown"),
        (r"mischief\s+premium\s+atlas\s+froot\s+by\s+the\s+foot", "Froot by the Foot", "Mischief Cannabis"),
        (r"north\s*park\s+510\s+vape\s+cart[- ]?ix\s*\|\s*gelato\s*#?\s*41", "Gelato 41", "Northpark"),
        (r"north\s*park\s+og\s+kush\s+cart", "OG Kush", "Northpark"),
        (r"r\s*&?\s*d\s+r\s*&?\s*d\s+pharms?\s*\|\s*black\s+maple\s*\|\s*pre[- ]?pack(?:aged)?", "Black Maple 22", "R & D Farms"),
        (r"rewind\s+aloha\s+sugar", "Aloha Sugar", "Rewind"),
        (r"rewind\s+daily\s+grape", "Daily Grape", "Rewind"),
        (r"rewind\s+kanobi\s+sunset", "Kanobi Sunset", "Rewind"),
        (r"rewind\s+killer\s+cupcake", "Killer Cupcake", "Rewind"),
        (r"turtle\s+taffy\s*[-–]\s*(?:2|8)\s*[- ]?pack", "Turtle Taffy", None),
        (r"verist\s+fields\s+verist\s+fields\s*\|\s*cured\s+resin\s*\|\s*sappy\s+pappy\s*\|\s*dream\s+berry", "Dream Berry", "Verist Fields"),
        (r"verist\s+fields\s+verist\s+fields\s*\|\s*pre[- ]?packaged\s*\|\s*double\s+sour\s+grapes?", "Double Sour Grape", "Verist Fields"),
        (r"float\s+float\s*\|\s*pre[- ]?packaged\s*\|\s*gorilla\s+zkittl(?:es|ez)", "Gorilla Zkittlez", "Float Cannabis"),
        (r"float\s+magic\s+marker", "Magic Marker", "Float Cannabis"),
        (r"(?:&\s*)?shine\s+grand\s*daddy\s+purple", "Granddaddy Purple", "&Shine"),
        (r"trailhead\s+trailhead\s*\|\s*pre[- ]?packaged\s*\|\s*gastrona(?:u|un)t", "Gastronaut", "Trailhead Cannabis"),
    )
    for pattern, strain, brand in public_titles:
        if re.fullmatch(pattern, clean, re.I):
            return {"strain": strain, **({"brand": brand} if brand else {})}
    # Canonical strain overrides approved from MNtrees product-card QA.
    # Keep display packaging and retailer prefixes out of cultivar identity.
    dogwalkers = re.fullmatch(
        r"(?i)(?:dogwalkers\s+)?big\s+dog\s+(?:3\s*/\s*4\s+gram\s+)?"
        r"l['’]orange(?:\s+(?:sativa|pre[- ]?rolls?))*", clean)
    if dogwalkers:
        return {"strain": "L'Orange", "brand": "Dogwalkers"}
    if re.fullmatch(r"(?i)3\s*/\s*4\s+gram\s+l['’]orange(?:\s+(?:sativa|pre[- ]?rolls?))*", clean):
        return {"strain": "L'Orange"}
    gummi = re.fullmatch(
        r"(?i)(?:(fl[öo]r)\s+)?gummi[-\s]?bears?\s+live\s+rosin"
        r"(?:\s*[|]\s*\.?5\s*(?:g|gm|grams?)\s*[\"']?)?", clean)
    if gummi:
        result = {"strain": "Gummibears"}
        if gummi.group(1):
            result["brand"] = "FLÖR"
        return result
    discovery = re.fullmatch(
        r"(?i)(?:highnorth\s+)?(turtle\s+taffy|white\s+widow)\s+discovery\s+pack", clean)
    if discovery:
        return {"strain": "Turtle Taffy" if discovery.group(1).casefold().startswith("turtle") else "White Widow"}
    little_stick = re.fullmatch(
        r"(?i)little\s+stick\s+by\s+verist\s+fields\s+"
        r"(double\s+sour\s+grapes?|platinum\s+jesus)", clean)
    if little_stick:
        return {"strain": "Double Sour Grape" if "grape" in little_stick.group(1).casefold()
                else "Platinum Jesus", "brand": "Verist Fields"}
    birch_swedish = re.fullmatch(
        r"(?i)mr\.?\s*birch\s+little\s+stick\s*[-–]?\s*swedish\s+og", clean)
    if birch_swedish:
        return {"strain": "Swedish OG", "brand": "Verist Fields"}
    if re.fullmatch(r"(?i)(?:popcorn\s*[-–]\s*)?space\s+boogie", clean):
        return {"strain": "Space Boogie"}
    if re.fullmatch(r"(?i)purple\s+cereal\s+milk", clean):
        return {"strain": "Purple Milk"}
    if re.fullmatch(r"(?i)pilot\s+light(?:\s+2\.0)?", clean):
        return {"strain": "Pilot Light"}
    if re.fullmatch(r"(?i)hyperion(?:\s+f1)?", clean):
        return {"strain": "Hyperion F1"}
    birch = re.fullmatch(
        r"mr\.?\s*birch\s+(?:big\s+stick|little\s+sticks)\s+"
        r"(torch top|uffda og|uptown tart)(?:\s+pre[- ]?rolls?)?", clean, re.I)
    if birch:
        strain = {"torch top": "Torch Top", "uffda og": "Uffda OG", "uptown tart": "Uptown Tart"}
        # Big Stick / Little Sticks describe package formats, not cultivar names.
        variant = "Big Stick" if re.search(r"big\s+stick", clean, re.I) else "Little Sticks"
        return {"strain": strain[birch.group(1).casefold()], "brand": "Verist Fields",
                "product_variant": variant}
    if re.fullmatch(
        r"r\s+(?:and|&)\s+d\s+pharm\s+black\s+maple\s+22"
        r"(?:[\s-]*\(?\s*(?:1|3\.5|7)\s*g\s*\)?(?:\s+1/[48]\s*oz\.?)?)?",
        clean, re.I,
    ):
        return {"strain": "Black Maple 22", "brand": "R & D Farms"}
    # Specific known brand/strain separations, before the master comparison.
    wild_grape = re.fullmatch(r"(?i)(?:looner\s+)+wild\s+grape(?:\s+(?:flower|concentrate|pre-?roll|\d+(?:\.\d+)?\s*g))*", raw)
    if wild_grape:
        return {"strain": "Wild Grape", "brand": "Looner"}
    elevated = re.fullmatch(r"(?i)(?:elevate|elevated)(?:\s+botanicals)?\s+strawberry\s+lemonade(?:\s+(?:flower|concentrate|pre-?roll|\d+(?:\.\d+)?\s*g))*", raw)
    if elevated:
        return {"strain": "Strawberry Lemonade", "brand": "Elevated Botanicals"}
    granddaddy = re.fullmatch(r"(?i)grand\s*daddy\s+purp(?:le)?(?:\s+(?:flower|concentrate|pre-?roll|\d+(?:\.\d+)?\s*g))*", raw)
    if granddaddy:
        return {"strain": "Granddaddy Purple"}
    # MN Loon / MNL / MnLooN are brand aliases, never a cultivar prefix.
    # Keep a separate product's category and actual package weight unchanged.
    mn_loon = re.fullmatch(r"(?i)(?:mnl|mn\s*loon)\s+(.+)", raw)
    if mn_loon:
        strain = mn_loon.group(1).strip()
        strain = re.sub(r"(?i)\s*(?:1\s*/\s*2\s*gram|0?\.5\s*(?:g|gram)?|half\s*gram)\s*$", "", strain).strip(" .-")
        # Preserve master-approved spelling/capitalization on known MN Loon
        # cultivars. Avoid changing unrelated product names with title-case().
        known = {
            "orange creamsicle": "Orange Creamsicle",
            "watermelon": "Watermelon",
            "nyc diesel": "NYC Diesel",
            "lemon cherry gelato": "Lemon Cherry Gelato",
            "pinke rozay": "Pink Rozay",
            "pink rozay": "Pink Rozay",
        }
        strain = known.get(re.sub(r"\s+", " ", strain).casefold(), strain)
        if strain:
            return {"strain": strain, "brand": "MN Loon"}
    # Explicit Dizgo product names can have pack counts and format suffixes.
    # Those belong to the offer, not the canonical strain or brand.
    dizgo = re.fullmatch(
        r"(?i)(?:dizgo(?:\s+collective)?\s+)+(medusa|tri\s*cross|hyperion(?:\s+f1)?)"
        r"((?:[\s.()-]|\d+\s*[x×]|\d+\s*-?\s*(?:pck|pack|pk|ct)|"
        r"(?:\d+(?:\.\d+)?|\.\d+)\s*(?:g|gm|grams?)|prerolls?|pre-rolls?|joints?|flower|50/50)*)",
        clean,
    )
    if dizgo:
        cultivar = dizgo.group(1).casefold()
        strain = "Hyperion F1" if cultivar.startswith("hyperion") else "Medusa" if cultivar == "medusa" else "TriCross"
        return {"strain": strain, "brand": "Dizgo Collective"}
    # Brand-prefix cleanup for retailer titles (including partially truncated
    # pack-count labels). Do not infer a brand for an unprefixed Medusa item.
    trailhead = re.fullmatch(
        r"(?i)(?:trailhead(?:\s+cannabis)?\s+)+"
        r"(killer\s+cupcake|octane\s+mintz)"
        r"(?:\s*(?:flower|3\.5\s*g|[-–().\s])*)", raw)
    if trailhead:
        strain = "Killer Cupcake" if "killer" in trailhead.group(1).casefold() else "Octane Mintz"
        return {"strain": strain, "brand": "Trailhead Cannabis"}
    medusa_pack = re.fullmatch(
        r"(?i)(dizgo(?:\s+collective)?\s+)?medusa"
        r"(?:\s*\(?\s*\d+\s*[x×](?:\s*(?:\d+(?:\.\d+)?|\.\d+)\s*(?:g|gm|ct)(?:\s+joints?)?)?\s*\)?"
        r"|\s+\d+\s*(?:pk|pack|pck|ct))?\s*", clean)
    if medusa_pack:
        result = {"strain": "Medusa"}
        if medusa_pack.group(1):
            result["brand"] = "Dizgo Collective"
        return result
    # Normalize explicitly branded retailer titles before Strain Master lookup.
    # Product format and pack count are retained on the source offer.
    for pattern, strain, brand in (
        (r"(?:cannabis\s+)?fog\s+dog(?:\s*\(\s*indica\s*\))?(?:\s+(?:flower|3\.5g))?", "Fog Dog", None),
        (r"dizgo(?:\s+collective)?\s+medusa(?:\s+(?:flower|prerolls?|pre-rolls?))?", "Medusa", "Dizgo Collective"),
        (r"emerald\s+(?:fire\s+)?farms\s+pineapple\s+burst(?:\s+\d+(?:\.\d+)?\s*g)?", "Pineapple Burst", "Emerald Farms"),
        (r"frodo\s+squeeze(?:\s+3\s*[x×])?", "Frodo Squeeze", None),
        (r"native\s+cuts\s+cheetah(?:\s+piss)?(?:\s+(?:flower|50/50))?", "Cheetah Piss", "Native Cuts"),
        (r"native\s+cuts\s+mac(?:[-\s]?1)?(?:\s+(?:flower|50/50))?", "MAC-1", "Native Cuts"),
    ):
        if re.fullmatch(pattern, clean, re.I):
            result = {"strain": strain}
            if brand:
                result["brand"] = brand
            return result
    # Owner-confirmed: Purple Prince is a brand, Royal Oasis is its strain.
    if re.search(r"(?i)\bpurple\s+prince\b", raw) and re.search(r"(?i)\broyal\s+oasis\b", raw):
        return {"strain": "Royal Oasis", "brand": "Purple Prince"}
    # Confirmed strain aliases and brand-prefix parsing.
    mr_birch = re.fullmatch(r"(?i)mr\.?\s*birch\s+(?:little\s+sticks?\s*[-–]\s*)?(mimosa\s+ice|double\s+sour\s+grapes?|valley\s+frost)(?:\s+\d+(?:\.\d+)?\s*g)?", raw)
    if mr_birch:
        return {"strain": mr_birch.group(1).title(), "brand": "Mr. Birch"}
    native_cuts = re.fullmatch(r"(?i)native\s+cuts\s+(cheetah\s+piss|mac[- ]?1)", raw)
    if native_cuts:
        return {"strain": "MAC-1" if "mac" in native_cuts.group(1).casefold() else "Cheetah Piss", "brand": "Native Cuts"}
    if re.fullmatch(r"(?i)minny\s+grown\s+bumper\s+og", raw):
        return {"strain": "Bumper OG", "brand": "Minny Grown"}
    if re.fullmatch(r"(?i)mendo\s+breath(?:e|\s+auto)?", raw):
        return {"strain": "Mendo Breath"}
    if re.fullmatch(r"(?i)mimosa\s+ice(?:\s+3\.5(?:\s*g)?)?", raw):
        return {"strain": "Mimosa Ice"}
    if re.fullmatch(r"(?i)night\s*hawk", raw):
        return {"strain": "Night Hawk"}
    if re.fullmatch(r"(?i)mike['’]?s\s+strawberry\s+lemonade", raw):
        return {"strain": "Strawberry Lemonade"}
    rcwm = parse_rcwm_title(raw)
    if rcwm:
        return rcwm
    doctor = re.match(r"(?i)^(?:doctor|doc|dr\\.?)\\s+dabs\\s+(.+)$", raw)
    if doctor:
        strain = re.sub(r"(?i)\\s+3\\.5\\s+whole\\s*sale\\s*$", "", doctor.group(1)).strip()
        strain = re.sub(r"(?i)\\s*\\(3\\.5g\\)\\s*$", "", strain).strip()
        return {"strain": strain, "brand": "Doctor Dabs"}
    dizgo = re.match(r"(?i)^dizgo(?:\\s+collective)?\\s+(.+)$", raw)
    if dizgo:
        return {"strain": dizgo.group(1).strip(), "brand": "Dizgo Collective"}
    # Owner-reviewed product/brand normalization; packaging is not a strain.
    if re.fullmatch(r"(?i)stashbox\s*x\s*loon\s+labs\s+live\s+resin\s+dirty\s+laundry", raw):
        return {"strain": "Dirty Laundry", "brand": "Stashbox x Loon Labs"}
    if re.fullmatch(r"(?i)the\s+soap", raw):
        return {"strain": "Soap"}
    if re.fullmatch(r"(?i)(?:trop|tropical|tropicana)\s+cherry", raw):
        return {"strain": "Tropicana Cherry"}
    if re.fullmatch(r"(?i)valley\s+frost(?:\s+3\\.5(?:\s*g)?)?", raw):
        return {"strain": "Valley Frost"}
    # Bud Doctor is the producer brand, not a strain prefix.
    bud_doctor = re.match(r"(?i)^bud\s+doctor\s+(blueberry\s+diesel|lemon\s+cherry\s+gelato|lemon\s+fresh)(?:\b|$)", raw)
    if bud_doctor:
        canonical = {"blueberry diesel": "Blueberry Diesel", "lemon cherry gelato": "Lemon Cherry Gelato", "lemon fresh": "Lemon Fresh"}
        return {"strain": canonical[bud_doctor.group(1).casefold()], "brand": "Bud Doctor"}
    # Verist is a brand; 5x is packaging for a preroll pack.
    verist = re.fullmatch(r"(?i)verist(?:\s+fields)?\s+(double\s+sour\s+grapes?|gush\s+kush)(?:\s+5x)?", raw)
    if verist:
        strain = "Gush Kush" if verist.group(1).casefold() == "gush kush" else "Double Sour Grape"
        return {"strain": strain, "brand": "Verist Fields"}
    # Owner-confirmed brand/strain and THC-potency normalization.
    if re.search(r"(?i)purple\\s+prince\\s+royal\\s+oasis", raw):
        return {"strain": "Royal Oasis", "brand": "Purple Prince"}
    if re.fullmatch(r"(?i)purple\\s+octane(?:\\s+\\d{1,2}(?:\\.\\d+)?\\s*%\\s*(?:thc)?)?", raw):
        return {"strain": "Purple Octane"}
    # Owner-confirmed: Dabney\'s &Shine 0.75g single preroll is L\'Orange.
    if re.search(r"(?i)&shine\s+single\s+l[\u2019\u0027]orange", raw):
        return {"strain": "L\u0027Orange", "brand": "&Shine"}
    # Explicit Verist brand on Green 2 Go flower cards; THC is potency metadata.
    # Do not rebrand Mr. Birch-branded Uffda OG / Double Sour Grape prerolls.
    if re.search(r"\bverist(?:\s+feelinmn)?\s*[-–]?\s*double sour grapes?\b", raw, re.I):
        return {"strain": "Double Sour Grape", "brand": "Verist Fields"}
    if re.search(r"\bverist(?:\s+feelinmn)?\s*[-–]?\s*uffda og\b", raw, re.I):
        return {"strain": "Uffda OG", "brand": "Verist Fields"}
    if re.search(r"\bapple\s+fritter\s+rcwm\s+3(?:[.,]5)?\b", raw, re.I) and re.search(r"redwood county weed management|\brcwm\b", raw, re.I):
        return {"strain": "Apple Fritter", "brand": "Redwood County Weed Management"}
    if re.search(r"\banimal face\b", raw, re.I):
        if re.search(r"\bbig dog\b", raw, re.I):
            return {"strain": "Animal Face", "brand": "Big Dog"}
        if re.search(r"\brythm\b", raw, re.I):
            return {"strain": "Animal Face", "brand": "RYTHM"}
        if re.search(r"\bdogwalkers?\b", raw, re.I):
            return {"strain": "Animal Face", "brand": "Dogwalkers"}
    if re.fullmatch(r"(?:Popcorn[-\s]+)?(?:Wii?shkobi|Whishkobi) Mashkiki[-\s]*", raw, re.I):
        return {"strain": "Wiishkobi Mashkiki", "brand": "Waabigwan Mashkiki"}
    if re.search(r"\bwaabigwan mashkiki\s*[-|]\s*cheetah piss\b", raw, re.I):
        return {"strain": "Cheetah Piss", "brand": "Waabigwan Mashkiki"}
    if re.search(r"\bzips\s*[-|]\s*biscotti\b", raw, re.I):
        return {"strain": "Biscotti", "brand": "Zips"}
    if re.search(r"\bminny grown\s+zesty parm\b", raw, re.I):
        return {"strain": "Zesty Parm", "brand": "Minny Grown"}
    if re.search(r"\bbud doctor\s+scotch and soda\b", raw, re.I):
        return {"strain": "Scotch and Soda", "brand": "Bud Doctor"}
    if re.search(r"\blifted north\b", raw, re.I) and re.search(r"\bblueberry muffin\b", raw, re.I):
        return {"strain": "Blueberry Muffin", "brand": "Lifted North"}
    if re.search(r"\bbeaver cookies\b", raw, re.I):
        return {"strain": "Beaver Cookies", "brand": "Green Goods"}
    if re.search(r"\banimal scout\b", raw, re.I) and re.search(r"\brythm\b", raw, re.I):
        return {"strain": "Animal Scout", "brand": "RYTHM"}
    if re.fullmatch(r"alien rock candy\s*-?", raw, re.I):
        return {"strain": "Alien Rock Candy", "brand": "Native Cuts"}
    if re.search(r"\bauto\s*pilot\b", raw, re.I) and re.search(r"pre\s*-?\s*roll", raw, re.I):
        return {"strain": "Autopilot", "brand": "Avio"}
    return None


STRUCTURED_BRANDS = {
    "rythm": "RYTHM", "good green": "Good Green", "vireo": "Vireo",
    "boundary waters": "Boundary Waters", "limited salad": "Limited Salad",
    "simple": "Simple", "float": "Float Cannabis", "float cannabis": "Float Cannabis",
    "native care": "Native Care", "nativecare": "Native Care",
    "trailhead": "Trailhead Cannabis", "trailhead cannabis": "Trailhead Cannabis",
    "minny grown": "Minny Grown", "avio": "Avio", "erba": "ERBA",
    "verist": "Verist Fields", "verist fields": "Verist Fields",
    "dizgo": "Dizgo Collective", "dizgo collective": "Dizgo Collective",
    "flor": "FLÖR", "flör": "FLÖR",
}
GREEN_GOODS_TITLE = re.compile(
    r"^(?:hybrid|indica|sativa)\s+flower\s+(.+?)\s+"
    r"(RYTHM|Good Green|Vireo|Boundary Waters|Limited Salad|Simple)\s+"
    r"(?:premium flower|mini buds?|mixed buds?|ground flower|whole flower|flower)$", re.I)
FORMAT_TRAILER = re.compile(
    r"\s+(?:flower|mini buds?|mixed buds?|premium flower|whole flower|ground flower|prerolls?|pre-rolls?)\s*$", re.I)
WEIGHT_TRAILER = re.compile(r"\s+\d+(?:\.\d+)?\s*(?:g|gm|grams?)\s*$", re.I)

def parse_structured_title(title):
    """Extract strain + explicitly stated brand from repeatable menu-title templates.

    This is not a fuzzy strain-guessing method. If the brand or strain segment is
    unrecognized or contains only packaging terms, return None for review.
    """
    raw = str(title or "").strip()
    # Explicit repeated brand in Levitated menu titles, including promotional
    # ribbons. The advertised 0.33g x 3 and 0.5g x 2 are package details,
    # never part of the strain name. Actual source package_g is unchanged.
    item = re.sub(r"^(?:OFFER\s+(?:BUY\s+\d+|CONDITIONS\s+APPLY)\s+)+", "", raw, flags=re.I)
    repeated = re.fullmatch(
        r"(Dizgo\s+Collective\s+Dizgo|Flor\s+Flor)\s+"
        r"(.+?)\s+(?:Infused\s+)?Pre[-\s]?roll\s+"
        r"(?:(?:0?\.\d+|1(?:\.0)?)\s*g)\s+\d+\s*ct",
        item, re.I)
    if repeated:
        brand = "Dizgo Collective" if repeated.group(1).casefold().startswith("dizgo") else "FLÖR"
        strain = re.sub(r"\s+", " ", repeated.group(2)).strip()
        # Hyperion and Hyperion F1 are established aliases for this Dizgo line.
        if brand == "Dizgo Collective" and strain.casefold() == "hyperion":
            strain = "Hyperion F1"
        return {"strain": strain, "brand": brand}
    # Blue Ox Native Care menus may omit the separate brand field even though
    # the brand is explicit at the beginning of the source product title.
    if re.match(r"^Native\s+Care\s+", item, re.I):
        native = re.sub(r"^Native\s+Care\s+", "", item, count=1, flags=re.I).strip()
        if "|" in native:
            segments = [p.strip() for p in native.split("|")]
            if len(segments) >= 2 and re.fullmatch(r"Flower\s+IX", segments[0], re.I):
                native = segments[1]
            else:
                native = ""
        if native and not re.fullmatch(r"(?:Flower|Pre-?roll|Vape|\d+(?:\.\d+)?g)", native, re.I):
            return {"strain": native, "brand": "Native Care"}
    # Unbound and Verist/Mr. Birch are explicitly labeled brand families.
    # Distinct package sizes remain attached to their source offers.
    repeated_family = re.fullmatch(
        r"(Unbound\s+Unbound|Verist\s+Fields\s+Mr\.?\s*Birch)\s+"
        r"(.+?)\s+Pre[-\s]?roll\s+"
        r"(?:0?\.\d+|1(?:\.0)?)\s*g\s+\d+\s*ct", item, re.I)
    if repeated_family:
        brand = ("Unbound" if repeated_family.group(1).casefold().startswith("unbound")
                 else "Verist Fields")
        return {"strain": re.sub(r"\s+", " ", repeated_family.group(2)).strip(),
                "brand": brand}
    # American Made / Highnorth / Kodjo's Verist product families. Retailer
    # titles combine producer + Little Stick packaging + cultivar in one field.
    # Only exact, observed title shapes and named cultivars are accepted.
    verist_pipe = re.fullmatch(
        r"Verist\s+Fields\s*\|\s*(?:(Little\s+Stick)\s*\|\s*)?"
        r"(Double\s+Sour\s+Grape|Mimosa\s+Ice|Valley\s+Frost)\s*\|?",
        item, re.I)
    if verist_pipe:
        names = {"double sour grape": "Double Sour Grape",
                 "mimosa ice": "Mimosa Ice", "valley frost": "Valley Frost"}
        result = {"strain": names[verist_pipe.group(2).casefold()],
                  "brand": "Verist Fields"}
        if verist_pipe.group(1):
            result["product_variant"] = "Little Stick"
        return result
    verist_plain = re.fullmatch(
        r"Verist\s+Fields\s+(Platinum\s+Jesus|Mimosa\s+Ice)"
        r"(?:\s+3\.5\s+Flower)?", item, re.I)
    if verist_plain:
        cultivar = verist_plain.group(1)
        if cultivar.casefold() == "mimosa ice" or not re.search(r"3\.5\s+Flower", item, re.I):
            return {"strain": cultivar.title(), "brand": "Verist Fields"}
    # Greenhouse flower title embeds its type/size/brand around the strain.
    fog_dog = re.fullmatch(
        r"(?:Indica\s+)?FLÖR\s+Fog\s+Dog-\s*3\.5\s*-\s*Flor\s+1/8\s*oz", item, re.I)
    if fog_dog:
        return {"strain": "Fog Dog", "brand": "FLÖR"}
    # Dizgo sale titles do not repeat the brand and use a named 3-pack.
    dizgo_hyperion = re.fullmatch(
        r"(?:ON\s+SALE\s+)?Dizgo\s+Hyperion\s+F1\s*\(3-Pack\)\s+Pre[-\s]?roll",
        item, re.I)
    if dizgo_hyperion:
        return {"strain": "Hyperion F1", "brand": "Dizgo Collective"}
    match = GREEN_GOODS_TITLE.fullmatch(raw)
    if match:
        return {"strain": match.group(1).strip(), "brand": STRUCTURED_BRANDS[match.group(2).casefold()]}
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) >= 3:
        # 'Flower-IX | Native Care | Lit OG | 3.5g' is a common blooMN template.
        brand = STRUCTURED_BRANDS.get(parts[1].casefold())
        if brand and parts[2] and not re.match(r"^\d+(?:\.\d+)?\s*g", parts[2], re.I):
            return {"strain": parts[2], "brand": brand}
        # 'Float Float | Pre-Packaged | Blue Dream | 3.5g' names the brand twice.
        if re.fullmatch(r"float(?:\s+float)?", parts[0], re.I) and len(parts) >= 3:
            return {"strain": parts[2], "brand": "Float Cannabis"}
    if len(parts) >= 2:
        brand = STRUCTURED_BRANDS.get(parts[0].casefold())
        if brand and parts[1]:
            return {"strain": WEIGHT_TRAILER.sub("", FORMAT_TRAILER.sub("", parts[1])).strip(), "brand": brand}
    # 'Float 3.5g Jar Magic Marker' / 'Float 1x1g Pre Rolls Cap Junky'.
    match = re.fullmatch(
        r"Float\s+(?:\d+(?:\.\d+)?g\s+Jar|(?:\d+x)?\d+(?:\.\d+)?g\s+Pre\s*Rolls?)\s+(.+)", raw, re.I)
    if match:
        return {"strain": match.group(1).strip(), "brand": "Float Cannabis"}
    # Strong source title: "ON SALE Avio Mendo Breath Preroll" or
    # "ON SALE Native Cuts Cheetah Piss Flower" explicitly names the brand.
    match = re.fullmatch(
        r"(?:ON SALE\s+)?(Native Cuts|Avio|Minny Grown|ERBA|RYTHM|Good Green|Float Cannabis|Float|Vireo)"
        r"\s+(.+?)\s+(?:Flower|Preroll|Pre[- ]?Roll)", raw, re.I)
    if match:
        brand = STRUCTURED_BRANDS.get(match.group(1).casefold(), match.group(1))
        return {"strain": match.group(2).strip(), "brand": brand}
    match = re.fullmatch(r"(?:ON SALE\s+)?FLOR\s+(.+?)\s+Flower", raw, re.I)
    if match:
        return {"strain": match.group(1).strip(), "brand": "FLÖR"}
    return None

def match_strain(name, database=None):
    original = str(name or "").strip()
    candidate = normalize_name(original)
    if not candidate or INVALID.fullmatch(candidate) or NON_FLOWER.search(candidate):
        return {"strain": original, "match_status": "invalid", "strain_type": ""}
    aliases = ALIASES
    canonical = aliases.get(candidate.casefold(), candidate)
    if canonical == candidate and candidate.casefold().startswith("auto pilot"):
        canonical = "Autopilot"
    if database is None:
        try:
            database = json.loads(DATABASE.read_text())
        except (OSError, ValueError):
            database = {}
    key = canonical.casefold()
    if key in database:
        return {"strain": canonical, "match_status": "alias" if canonical != candidate else "database", "strain_type": database[key]}
    return {"strain": canonical, "match_status": "alias" if canonical != candidate else "unmatched", "strain_type": ""}

# Explicit product labels carry brand evidence even when the scanner leaves brand blank.
# This parser removes only known promotional prefixes. Do not map brands by strain
# alone, retailer name, or fuzzy matching; Lake Leaf and Campfire remain distinct.
_EXPLICIT_BRAND_PROMO = re.compile(
    r"^(?:(?:on\s+sale|sale|best\s+seller|offer\s+conditions\s+apply|offer\s+buy\s+\d+)\s+)+", re.I
)
_EXPLICIT_TITLE_BRANDS = (
    (r"float(?:\s+cannabis)?", "Float Cannabis"),
    (r"fl[oö]r", "FLÖR"),
    (r"campfire(?:\s+cannabis)?", "Campfire Cannabis"),
    (r"native\s+cuts", "Native Cuts"),
    (r"native\s+care", "Native Care"),
    (r"north\s*park(?:\s+cannabis)?", "Northpark"),
    (r"lakeside\s+(?:cana|cannabis)", "Lakeside Cannabis"),
    (r"lake\s+leaf", "Lake Leaf"),
    (r"grass\s*landz", "Grasslandz"),
    (r"high\s+def(?:in|ini)tion", "High Definition"),
    (r"minny\s+grown(?:\s+cannabis)?", "Minny Grown"),
    (r"unbound", "Unbound"),
    (r"verist\s+fields", "Verist Fields"),
    (r"rythm", "RYTHM"),
    (r"good\s+green", "Good Green"),
    (r"avi[oó]", "Avio"),
    (r"dizgo(?:\s+collective)?", "Dizgo Collective"),
    (r"marawanna", "Marawanna"),
    (r"bud\s+doctor", "Bud Doctor"),
    (r"d['’]ope(?:\s+cannabis)?", "D'Ope"),
    (r"mn\s+roots", "MN Roots"),
    (r"looner", "Looner"),
    (r"(?:&shine|shine)", "&Shine"),
    (r"erba", "ERBA"),
    (r"mr\.?\s*birch", "Verist Fields"),
    (r"verist", "Verist Fields"),
    (r"trailhead(?:\s+cannabis)?", "Trailhead Cannabis"),
    (r"emerald\s+fire\s+farms", "Emerald Fire Farms"),
    (r"r\s+(?:and|&)\s+d\s+pharm(?:s)?", "R & D Farms"),
    (r"aurora\s+cannabis(?:\s+llc)?", "Aurora"),
    (r"waagbigwan", "Waabigwan Mashkiki"),
    (r"dope\s+cannabis", "D'Ope"),
    (r"exquisite\s+extractions", "Exquisite Extractions"),
    (r"slaps", "Slaps"),
)
_EXPLICIT_TITLE_BRAND_PATTERNS = tuple(
    (re.compile(r"^" + pattern + r"(?=\s|[|:—–-]|$)", re.I), brand)
    for pattern, brand in _EXPLICIT_TITLE_BRANDS
)


def brand_from_explicit_title(title):
    """Return canonical brand only when it is written as the title prefix.

    Never infer a brand from a cultivar's usual producer or from a store name.
    """
    cleaned = _EXPLICIT_BRAND_PROMO.sub("", str(title or "").strip()).strip()
    for pattern, canonical_brand in _EXPLICIT_TITLE_BRAND_PATTERNS:
        match = pattern.match(cleaned)
        if match and cleaned[match.end():].strip(" |:-—–"):
            return canonical_brand
    # A known brand may be carried in a structured product title as
    # "Flower-IX | Native Care | Lit OG | 3.5g" or
    # "Pre-rolls 0.33 g-IX | Dizgo Collective | Nighthawk".
    fields = [part.strip() for part in cleaned.split("|")]
    if len(fields) >= 3:
        for middle in fields[1:-1]:
            for pattern, canonical_brand in _EXPLICIT_TITLE_BRAND_PATTERNS:
                if pattern.fullmatch(middle):
                    return canonical_brand
    # Mr. Birch / Little Stick is an established Verist Fields subbrand.
    if re.match(r"(?i)^little\s+sticks?\s+by\s+verist\s+fields\b", cleaned):
        return "Verist Fields"
    return ""


def normalize_brand(brand):
    brand = str(brand or "").strip()
    return BRAND_ALIASES.get(brand.casefold(), brand)
