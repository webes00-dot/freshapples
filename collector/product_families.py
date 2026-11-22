"""User-reviewed product family vocabulary for comparisons.

A family groups related labels for search/price comparisons; it NEVER authorizes
collapsing distinct offers, strains, formats, retailers, weights, or SKUs.
"""
import re
import unicodedata

def normalize_name(value):
    x=unicodedata.normalize("NFKC",str(value or "")).casefold().strip()
    x=x.replace("&"," and ")
    return " ".join(re.findall(r"[a-z0-9]+",x))

def product_family(strain):
    name=normalize_name(strain)
    if name in ("bourbon berry zulu","zulu terp"):
        return ("Bourbon Berry Zulu","approved_exact_alias")
    if name.startswith("bumper og") or name in ("bumper o g",):
        return ("Bumper OG","variant_family")
    if name.startswith("banana push pop"):
        return ("Banana Push Pop","variant_family")
    return (str(strain or "").strip(),"unmapped")

# Owner-approved duplicate-review groupings from MNtrees management workbook.
# Group for comparison only; preserve source names, delivery devices, extraction
# types, package weights, retailer locations, and individual advertised prices.
REVIEWED_GROUPS = (
    ("D'ope! Cannabis", "Concentrate", "Aurora Blend", ("aurora blend",)),
    ("D'ope! Cannabis", "Concentrate", "Bourbon Berry x Whiskey Zulu", ("berry zulu", "bourbon berry x whiskey zulu")),
    ("Oma", "Vape", "Jack Herer", ("jack herer",)),
    ("D'ope! Cannabis", "Vape", "Lemon Medusa", ("lemon medusa",)),
    ("Tasty Gems", "Vape", "Sunstone Apricot Orange", ("sunset apricot orange", "sunstone apricot orange")),
    ("Float Cannabis", "Vape", "Limesickle", ("limesickle",)),
    ("Unbound", "Vape", "Skywalker OG", ("skywalker og", "skywalker")),
    ("MN First", "Vape", "Watermelon Rolex", ("watermelon rolex",)),
    ("Mischief", "Flower", "Froot by the Foot", ("froot by the foot",)),
    ("RYTHM", "Flower", "Durban Z", ("durban z",)),
)

def reviewed_product_family(name, brand, category):
    raw=normalize_name(name)
    maker=normalize_name(brand)
    kind=normalize_name(category)
    for source_brand, source_category, family, variants in REVIEWED_GROUPS:
        if normalize_name(source_brand) not in maker:
            continue
        wanted=normalize_name(source_category)
        if wanted not in kind and not (wanted=="vape" and kind in ("vapes","vapes carts")):
            continue
        if any(re.search(r"(?<![a-z0-9])"+re.escape(variant)+r"(?![a-z0-9])",raw) for variant in variants):
            return (family, "owner_approved_comparison_family")
    return None

def canonical_brand_family(brand):
    text=normalize_name(brand)
    if text.startswith("lake leaf") or text.startswith("campfire"):
        return ("Campfire / Lake Leaf","related_brand_family")
    if text.startswith("emerald farms") or text.startswith("emerald fire farms"):
        return ("Emerald Farms","approved_brand_alias")
    return (str(brand or "").strip(),"unmapped")

def annotate(row):
    row=dict(row)
    # Retailer text can include merchandising, packaging and brand prefixes.
    # Explicitly identifiable strain names take priority over these decorations.
    source_text = str(row.get("product_name") or "") + " | " + str(row.get("strain") or "")
    if re.search(r"(?<![a-z0-9])zesty[\s-]+parm(?![a-z0-9])", source_text, re.I):
        row["strain"] = "Zesty Parm"
        row["product_family"] = "Zesty Parm"
        row["product_family_decision"] = "confirmed_named_strain"
        brand_group, brand_decision = canonical_brand_family(row.get("brand"))
        row["brand_family"] = brand_group
        row["brand_family_decision"] = brand_decision
        return row
    reviewed=reviewed_product_family(row.get("strain") or row.get("product_name"),row.get("brand"),row.get("category"))
    group,decision=reviewed if reviewed else product_family(row.get("strain"))
    row["product_family"]=group
    row["product_family_decision"]=decision
    brand_group,brand_decision=canonical_brand_family(row.get("brand"))
    row["brand_family"]=brand_group
    row["brand_family_decision"]=brand_decision
    return row
