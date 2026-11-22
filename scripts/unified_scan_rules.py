"""Shared, source-evidence-first product identity contract for every MNtrees scanner.

A transport adapter extracts public JSON-LD, HTML, rendered cards or documented
structured API objects. This module makes ONE decision about brand, strain,
total package grams, product type and the review gate. It never asserts stock.
"""
import re
from unicodedata import numeric
from pathlib import Path
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parents[1]
WEIGHT = re.compile(r"(?<![\w.])(?:(?P<oz>1\s*/\s*(?:8|4|2|1))\s*oz|(?P<grams>(?:\d+(?:\.\d+)?|\.\d+))\s*(?:g|gm|grams?))\b", re.I)
FRACTION_VALUE = (r"(?:(?P<numerator>\d+)[ \t]*[/⁄][ \t]*(?P<denominator>\d+)"
                  r"|(?P<symbol>[¼½¾⅐-⅞]))")
FRACTIONAL_GRAMS = re.compile(rf"(?<![\w./⁄]){FRACTION_VALUE}[ \t]*(?:grams?|gm|g)\b", re.I)
PACK = re.compile(r"\b(\d{1,2})\s*(?:-?\s*pack|pk|ct|count)\b", re.I)
PER_STICK = re.compile(r"(?<![\w.])\.?\d+(?:\.\d+)?\s*g\s*(?:pre[- ]?roll|joint)", re.I)
THC = re.compile(r"\b\d+(?:\.\d+)?\s*%\s*(?:THC|CBD)\b", re.I)
MERCH = re.compile(r"^(?:(?:on sale|sale|offer conditions apply|offer buy \d+)\s+)+", re.I)
FORMAT = re.compile(r"\b(?:vapes?|vaporizers?|carts?|cartridges?|disposables?|all[- ]in[- ]one|510(?:\s*thread(?:ed)?)?)\b",re.I)
CONCENTRATE = re.compile(r"\b(?:concentrates?|extracts?|wax|shatter|badder|budder|crumble|hash|diamonds|rosin|resin)\b",re.I)
PREROLL = re.compile(r"\b(?:pre[- ]?rolls?|joints?|blunts?)\b", re.I)
FLOWER = re.compile(r"\b(?:flower|buds?|eighth|quarter|ounce)\b", re.I)
CATEGORY_URL = re.compile(r"\b(?:flower|vapes?|vaporizers?|pre[- ]?rolls?|concentrates?)\b",re.I)
SEPARATORS = re.compile(r"\s*[|·•]\s*")
DECORATION = re.compile(r"\b(?:sativa|indica|hybrid|live resin|live rosin|cured resin|pre[- ]?packaged|premium|small buds|pre[- ]?rolls?|flower|vapes?|vaporizers?|510|cartridges?|disposables?)\b",re.I)
BAD_STRAIN = re.compile(r"^(?:\d+(?:\.\d+)?\s*%\s*(?:THC|CBD)|\d+(?:\.\d+)?\s*(?:g|grams?)|\d+\s*/\s*\d+\s*oz|sale|on sale|flower|vape|preroll|hybrid|indica|sativa)$",re.I)
OZ = {"1/8":3.5,"1/4":7.0,"1/2":14.0,"1/1":28.0}

def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()

def key(value):
    return re.sub(r"[^a-z0-9]+", "", clean(value).casefold())

def names_from_master(master):
    names = master.get("canonical_strains", []) if isinstance(master,dict) else master
    aliases = master.get("approved_aliases", {}) if isinstance(master,dict) else {}
    out = {key(x):x for x in names if clean(x)}
    for alias,target in aliases.items():
        canonical=out.get(key(target))
        if canonical:out[key(alias)]=canonical
    return out

def names_from_brands(brands):
    out={}
    for brand in brands:
        name=clean(brand.get("name"))
        if name:out[key(name)]=name
        for alias in brand.get("aliases",[]) or []:
            if isinstance(alias,str) and name:out[key(alias)]=name
    return out

def bounded_prefix(text, term):
    # Punctuation variants such as Feelin' MN and Feelin MN are equivalent.
    # Token boundaries prevent "Float" from stripping "Floatation".
    tokens=re.findall(r"[a-z0-9]+",clean(term).lower())
    if not tokens:return None
    pattern=r"^\W*"+r"\W*".join(re.escape(t) for t in tokens)+r"(?=$|\W)\W*"
    m=re.match(pattern,text,re.I)
    return text[m.end():].strip() if m else None

def infer_category(text, url="", explicit="", context_url=""):
    """One type resolver: explicit store type, title, menu context, then fallback.

    Resin/rosin alone does not prove a dabbable concentrate. A menu category
    URL can resolve that ambiguity without overriding explicit product form.
    """
    tag=clean(explicit)
    if tag:
        if FORMAT.search(tag):return "Vape"
        if PREROLL.search(tag):return "Preroll"
        if FLOWER.search(tag):return "Flower"
        if CONCENTRATE.search(tag):return "Concentrates"
    title=clean(text)
    if FORMAT.search(title):return "Vape"
    if PREROLL.search(title):return "Preroll"
    if FLOWER.search(title):return "Flower"
    if re.search(r"\b(?:concentrates?|wax|shatter|badder|budder|crumble|diamonds)\b",title,re.I):
        return "Concentrates"
    context=unquote(urlsplit(context_url).path+"?"+urlsplit(context_url).query).lower()
    if context:
        if FORMAT.search(context):return "Vape"
        if PREROLL.search(context):return "Preroll"
        if FLOWER.search(context):return "Flower"
        if CONCENTRATE.search(context):return "Concentrates"
    if CONCENTRATE.search(title):return "Concentrates"
    path=unquote(urlsplit(url).path+"?"+urlsplit(url).query).lower()
    if FORMAT.search(path):return "Vape"
    if PREROLL.search(path):return "Preroll"
    if FLOWER.search(path):return "Flower"
    if CONCENTRATE.search(path):return "Concentrates"
    return ""

def normalize_fractional_grams(value):
    def replace(match):
        if match["symbol"]:
            weight = numeric(match["symbol"])
        else:
            denominator = int(match["denominator"])
            if not denominator:
                return " "
            weight = int(match["numerator"]) / denominator
        return f"{weight:.6f}".rstrip("0").rstrip(".") + "g"

    return FRACTIONAL_GRAMS.sub(replace, str(value or ""))


def extract_weight(title, body="", explicit=None):
    title = normalize_fractional_grams(title)
    body = normalize_fractional_grams(body)
    # The individual product title outranks the larger card, where multiple
    # prices/weights may be unrelated option selectors.
    source=clean(title)
    matches=list(WEIGHT.finditer(source))
    if not matches and explicit is not None:
        source=normalize_fractional_grams(clean(explicit))
        matches=list(WEIGHT.finditer(source))
    if not matches:
        source=clean(body)
        matches=list(WEIGHT.finditer(source))
    vals=[]
    for m in matches:
        grams=OZ.get(re.sub(r"\s+","",m.group("oz"))) if m.group("oz") else float(m.group("grams"))
        if grams is not None and 0 < grams <= 28: vals.append(round(grams,3))
    if not vals:
        return None,None,"missing_weight"
    if len(set(vals))>1:
        return None,None,"conflicting_weights"
    grams=vals[0]
    pack=PACK.search(title) or PACK.search(body)
    count=int(pack.group(1)) if pack else None
    if count and count>1 and PER_STICK.search(title):
        grams=round(grams*count,3)
    if grams>28:return None,count,"invalid_total_weight"
    return grams,count,"title_or_card"

def clean_candidate_fragment(value):
    return clean(DECORATION.sub(" ", WEIGHT.sub(" ", THC.sub(" ", normalize_fractional_grams(value)))).strip(" -|·•,:()"))

def clean_candidate(title, brand):
    value=unquote(clean(title))
    value=MERCH.sub("",value).strip()
    value=THC.sub(" ",value)
    value=WEIGHT.sub(" ",normalize_fractional_grams(value))
    value=PACK.sub(" ",value)
    if brand:
        rest=bounded_prefix(value,brand)
        if rest is not None:value=rest
    # Brand + cultivar can be repeated in pipe-delimited menu taxonomy.
    parts=[clean(s) for s in SEPARATORS.split(value) if clean(s)]
    if len(parts)>1:
        # A trailing segment can be a pack size or potency rather than a strain.
        parts=[p for p in parts if key(p)!=key(brand)]
        substantive=[p for p in parts if not BAD_STRAIN.fullmatch(
            clean_candidate_fragment(p))]
        value=max(substantive,key=lambda p:len(clean_candidate_fragment(p))) if substantive else ""
    # Do not remove a cultivar word at the beginning (e.g. Flower Power).
    value=re.sub(r"\s+(?:flower|pre[- ]?rolls?|vape|cartridge|disposable)$","",value,flags=re.I)
    value=re.sub(r"\s+(?:live rosin|live resin|cured resin)$","",value,flags=re.I)
    value=re.sub(r"\b(?:\d+\s*x\s*)\b"," ",value,flags=re.I)
    return clean(value.strip(" -|·•,:()"))

def normalize_observation(observation, master=None, brands=None):
    """Return reviewed identity fields and evidence, never guesses as approvals.

    Raw product_name, URL, price, store identity and source fields are untouched.
    Missing or conflicting fields mean needs_review; no speculative cultivar merge.
    """
    row=dict(observation)
    raw=clean(row.get("raw_scanned_product_name") or row.get("product_name") or row.get("name"))
    url=clean(row.get("url") or row.get("product_url"))
    title=clean(row.get("title") or raw)
    declared_brand=clean(row.get("brand") or row.get("brand_candidate"))
    master_map=names_from_master(master or [])
    brand_map=names_from_brands(brands or [])
    reasons=[]
    # Only source-declared product category is explicit. Adapter heuristics
    # (category_candidate) are diagnostic, not a second identity authority.
    context_url=clean(row.get("source_menu_url") or row.get("category_context_url"))
    category=infer_category(title+" "+clean(row.get("product_variant")),
                            url,row.get("category"),context_url)
    if not category:reasons.append("missing_type")
    package_g,pack_count,weight_status=extract_weight(title,row.get("card_text",""),row.get("weight_text"))
    # Explicit source total grams may be used if no title weight was present.
    if package_g is None and weight_status=="missing_weight" and row.get("package_g"):
        try:
            value=float(row["package_g"])
            if 0<value<=28:package_g=round(value,3);weight_status="explicit_source_weight"
        except (TypeError,ValueError):pass
    # A direct product URL may explicitly say 1g, 0.5g, or 1/8oz.
    # Category/store landing pages cannot supply a product package weight.
    product_path=unquote(urlsplit(url).path).lower()
    is_product_url=bool(re.search(r"/(?:product|products|pdp)/",product_path))
    if package_g is None and weight_status=="missing_weight" and is_product_url:
        url_weight,url_pack,url_status=extract_weight(product_path.replace("-"," "))
        if url_weight is not None:
            package_g,weight_status=url_weight,"direct_product_url"
            if url_pack:pack_count=url_pack
    if package_g is None:reasons.append(weight_status)
    brand=""
    if declared_brand:
        # Brand fields on real menus sometimes include the strain and weight.
        # Accept only a master-approved brand prefix when removing such text.
        brand=brand_map.get(key(declared_brand),"")
        if not brand:
            for known in sorted(set(brand_map.values()),key=len,reverse=True):
                if bounded_prefix(declared_brand,known) is not None:
                    brand=known
                    break
        if not brand:
            cleaned_brand=WEIGHT.sub(" ",THC.sub(" ",normalize_fractional_grams(declared_brand)))
            if BAD_STRAIN.fullmatch(clean(cleaned_brand)):
                reasons.append("invalid_brand_field")
            else:
                # Preserve a new explicit producer name for master review,
                # rather than promoting an unverified alias.
                brand=clean(cleaned_brand)
                reasons.append("brand_not_in_master")
    if not brand:
        # Only a known brand at the beginning of title counts as a brand,
        # not a strain name that happens to contain a brand token.
        for name in sorted(set(brand_map.values()),key=len,reverse=True):
            if bounded_prefix(MERCH.sub("",title),name) is not None:
                brand=name
                break
    if not brand and is_product_url:
        # Product slugs can identify an approved brand, but a retailer domain
        # or a menu category page cannot imply who manufactured the item.
        slug=unquote(urlsplit(url).path).lower().replace("-"," ")
        matches=[name for name in set(brand_map.values())
                 if len(name)>=4 and re.search(
                   r"(?<![a-z0-9])"+re.escape(name.lower())+r"(?![a-z0-9])",slug)]
        if len(matches)==1:brand=matches[0]
    if not brand:reasons.append("missing_brand")
    candidate=clean_candidate(title,brand)
    canonical=master_map.get(key(candidate))
    if not canonical:
        # URL slug is an additional evidence source but must confirm a
        # recognized cultivar; never use a retailer/category URL as a cultivar.
        path=unquote(urlsplit(url).path).lower().replace("-"," ")
        options=sorted(set(master_map.values()),key=len,reverse=True)
        matches=[name for name in options if len(name)>=4 and re.search(
            r"(?<![a-z0-9])"+re.escape(name.lower())+r"(?![a-z0-9])",path)]
        # A single exact cultivar in a genuine product URL is strong evidence
        # when the captured card has only generic/packaging text.
        if len(matches)==1 and (key(matches[0]) in key(title) or
                 not candidate or BAD_STRAIN.fullmatch(candidate) or
                 (is_product_url and not master_map.get(key(candidate)))):
            canonical=matches[0]
    # An explicitly structured strain is evidence only when the same
    # canonical identity is corroborated in the title or product URL.
    if not canonical and row.get("strain"):
        structured=master_map.get(key(row["strain"]))
        if structured and (
            key(structured) in key(title) or
            re.search(r"(?<![a-z0-9])"+re.escape(structured.casefold())+r"(?![a-z0-9])",
                      unquote(urlsplit(url).path).lower().replace("-"," "))):
            canonical=structured
    if not canonical:
        if not candidate or BAD_STRAIN.fullmatch(candidate):
            reasons.append("missing_strain")
        else:
            reasons.append("strain_not_in_master")
    row["brand"]=brand
    row["strain"]=canonical or candidate
    row["category"]=category
    row["package_g"]=package_g
    if pack_count:row["pack_count"]=pack_count
    row["weight_status"]=weight_status
    row["identity_status"]="needs_review" if reasons else "ready"
    row["identity_reasons"]=list(dict.fromkeys(reasons))
    row["identity_evidence"]={"original_title":raw,"source_url":url,
                              "parsed_candidate":candidate,
                              "canonical_strain_match":bool(canonical)}
    row["stock_status"]=row.get("stock_status") or "not_verified"
    return row
