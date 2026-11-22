"""Conservative public Flowhub storefront HTML extraction, review-only.

Only captures anchor text actually adjacent to direct /pdp/ links and exactly
one clearly displayed final price (or a marked ON SALE price pair).
Never claims stock and never qualifies for automatic publication.
"""
from html.parser import HTMLParser
import hashlib
import math
import re
from urllib.parse import urljoin, urlsplit

PRICE=re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)")
WEIGHT=re.compile(r"/\s*(\d+(?:\.\d+)?)\s*g\b", re.I)
PRODUCT_PATH=re.compile(r"/(?:rec|med)/(?:view/pdp/p|[^/]+/pdp/[^/]+)/v/[^/?#]+",re.I)
LABEL=re.compile(r"\b(Flower|Preroll|Pre-Roll|Vapes/Carts|Vapes|Concentrates|Edibles)\b(?=\s*(?:Indica(?:-dom)?|Sativa(?:-dom)?|Hybrid|50/50|THC\s*:|CBD\s*:|$))",re.I)
CATEGORY={"flower":"Flower","preroll":"Preroll","pre-roll":"Preroll","infused-preroll":"Infused Preroll","vapes":"Vape","vapes-carts":"Vape","vapes/carts":"Vape"}

# Exact visible leading manufacturer names; longest first to avoid partial collisions.
KNOWN_BRANDS=(
    "Campfire Cannabis", "Float Cannabis Company", "Float Cannabis Co.",
    "Float Canna Co", "Dizgo Collective", "D'ope! Cannabis",
    "Redwood County Weed Management", "Good Green", "Dogwalkers",
    "Wright Way Farms", "Northern Cultivators", "Matchbox Farms",
    "Tasty Gems", "Minny Grown", "Mischief Cannabis", "Mischief",
    "Unbound", "RYTHM", "Rythm", "FLÖR", "Flor", "Northpark",
    "Dizgo", "Oma", "Avio", "Phantom", "Purple Prince",
    "Green Cross Corp", "Black Bear", "MN First", "Redwood",
    "&Shine", "Epitome Labs", "Campfire", "Lake Leaf",
)
def split_brand_and_strain(title):
    raw=str(title or "").strip()
    for maker in sorted(KNOWN_BRANDS,key=len,reverse=True):
        if raw.casefold().startswith(maker.casefold()) and (len(raw)==len(maker) or raw[len(maker)] in " |:-"):
            name=raw[len(maker):].lstrip(" |:-")
            # Remove separately advertised package/form descriptions from strain.
            name=re.split(r"\s+-\s+(?:\d+(?:\.\d+)?\s*g\b|\.?\d+g\b|1/\d+\s*oz\b|vape\s*cart\b|pre.?roll\b)",name,1,flags=re.I)[0].strip()
            return maker,name or raw
    return "",raw

VOID_TAGS={"area","base","br","col","embed","hr","img","input","link","meta","param","source","track","wbr"}

class Cards(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth=0
        self.active=None
        self.cards=[]
        self.skip_text_depth=0
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if self.active:
            if tag not in VOID_TAGS:
                self.depth+=1
            if tag in ("style","script","svg"):
                self.skip_text_depth+=1
            return
        href=attrs.get("href","")
        if tag=="a" and PRODUCT_PATH.search(href):
            self.active={"href":href,"segments":[]}
            self.depth=1
    def handle_startendtag(self,tag,attrs):
        pass
    def handle_data(self,data):
        if self.active and not self.skip_text_depth:
            self.active["segments"].append(data)
    def handle_endtag(self,tag):
        if not self.active:
            return
        if tag in ("style","script","svg") and self.skip_text_depth:
            self.skip_text_depth-=1
        if tag not in VOID_TAGS:
            self.depth-=1
        if self.depth==0:
            self.cards.append(self.active)
            self.active=None

def extract_cards(html,base_url):
    parser=Cards()
    parser.feed(html)
    offers=[]
    seen=set()
    host=urlsplit(base_url).hostname
    for card in parser.cards:
        url=urljoin(base_url,card["href"])
        parts=urlsplit(url)
        if parts.scheme!="https" or parts.hostname!=host:
            continue
        pieces=parts.path.lower().split("/")
        if "pdp" not in pieces:
            continue
        text=re.sub(r"\s+"," "," ".join(card["segments"])).strip()
        labels=list(LABEL.finditer(text))
        if labels:
            match=labels[-1]
            kind=match.group(1).casefold()
            category=CATEGORY.get(kind) or {"concentrates":"Concentrate","edibles":"Edible"}.get(kind)
            title=text[:match.start()].strip()
        else:
            kind=pieces[pieces.index("pdp")-1].replace("_","-") if pieces[pieces.index("pdp")-1]!="view" else ""
            category=CATEGORY.get(kind)
            title=text
        if not category:
            continue
        prices=[float(p) for p in PRICE.findall(text)]
        if not prices or len(prices)>2:
            continue
        if len(prices)==2:
            if not re.search(r"\bon\s*sale\b|\bsale\b",text,re.I):
                continue
            amount=prices[-1]
        else:
            amount=prices[0]
        if not math.isfinite(amount) or not 0<amount<10000:
            continue
        # Preserve the card title, not an inferred strain or brand.
        title=re.split(r"\bTHC\s*:",title,1,flags=re.I)[0]
        title=re.sub(r"^(?:ON SALE\s*)","",title,flags=re.I)
        title=title.replace(" Add to Bag","").strip()
        if len(title)<8 or len(title)>260:
            continue
        weight=WEIGHT.search(text)
        key=(parts.path,amount)
        if key in seen:
            continue
        seen.add(key)
        maker,strain=split_brand_and_strain(title)
        offers.append({
            "url":url,"product_name":title,"strain":strain,"brand":maker,
            "category":category,"package_g":float(weight.group(1)) if weight else None,
            "price":amount,"source_method":"flowhub_html_card_review_only",
            "stock_status":"not_verified","weight_status":"advertised_card" if weight else "unverified"
        })
    return offers
