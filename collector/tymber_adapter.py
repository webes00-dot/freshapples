"""Conservative HTML product-card extraction for MN THC Co / Tymber-style menus.

Only pairs price with a single distinct product link in the nearest card ancestor.
No price inference from scripts, unrelated links, or parent grids.
"""
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
import re

PRICE_RE = re.compile(r'\$\s*([0-9]{1,4}(?:\.[0-9]{1,2})?)')
GRAM_RE = re.compile(r'(?<![\d.])(\d+(?:\.\d+)?)\s*g(?:rams?)?\b', re.I)
SPACE = re.compile(r'\s+')
SALE_RE = re.compile(r'Sale\s*Price\s*\$\s*(\d+(?:\.\d{1,2})?)', re.I)

class Node:
    __slots__ = ("tag", "attrs", "parent", "children", "bits")
    def __init__(self, tag, attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children, self.bits = [], []
    def text(self):
        return SPACE.sub(" ", " ".join(self.bits)).strip()

class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]
        self.anchors = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in ("area","base","br","col","embed","hr","img","input","link","meta","param","source","track","wbr"):
            self.stack.append(node)
        if tag == "a" and "/products/" in node.attrs.get("href", ""):
            self.anchors.append(node)
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return
    def handle_data(self, data):
        # Exclude scripts and styles from price calculations.
        if any(n.tag in ("script","style","noscript") for n in self.stack):
            return
        if data.strip():
            for node in self.stack:
                node.bits.append(data.strip())

def product_href(node, base_url):
    href = node.attrs.get("href", "")
    full = urljoin(base_url, href)
    parsed = urlsplit(full)
    origin = urlsplit(base_url)
    if parsed.scheme != "https" or parsed.hostname != origin.hostname or "/products/" not in parsed.path:
        return None
    return full.split("?")[0].split("#")[0]

def name_size_brand(title):
    title = SPACE.sub(" ", title).strip()
    grams = GRAM_RE.search(title)
    weight = float(grams.group(1)) if grams else None
    # Require an explicit weight and hyphen-delimited product title to avoid guessing.
    if not weight or weight <= 0 or weight > 112:
        return None
    pieces = [p.strip() for p in re.split(r'\s*-\s*', title) if p.strip()]
    if len(pieces) < 2:
        return None
    strain = re.split(r'\s*-\s*', title[:grams.start()])[0].strip(" -")
    if not strain:
        return None
    brand = pieces[-1] if len(pieces) >= 3 else ""
    if brand and (GRAM_RE.search(brand) or brand.isnumeric()):
        brand = ""
    return {"product_name":title,"strain":strain,"brand":brand,
            "category":"Flower", "package_g":weight}

def extract_cards(html, base_url):
    tree = Tree()
    tree.feed(html)
    records = {}
    for anchor in tree.anchors:
        url = product_href(anchor, base_url)
        if not url:
            continue
        title = anchor.text()
        fields = name_size_brand(title)
        if not fields:
            continue
        candidate = anchor.parent
        for _ in range(7):
            if candidate is None or candidate.tag == "root":
                break
            # A card must contain one distinct product link; repeated links to same
            # item are fine, but a grid containing other products is not.
            links = set()
            stack = [candidate]
            while stack:
                n = stack.pop()
                if n.tag == "a":
                    u = product_href(n, base_url)
                    if u:
                        links.add(u)
                stack.extend(n.children)
                if len(links) > 1:
                    break
            if links != {url}:
                break
            text = candidate.text()
            prices = PRICE_RE.findall(text)
            if prices and len(prices) <= 6:
                sale = SALE_RE.search(text)
                price = float(sale.group(1)) if sale else float(prices[-1])
                if 0 < price < 10000:
                    records[url] = {**fields,"price":price,"url":url,
                                    "price_selection":"sale" if sale else "card"}
                    break
            candidate = candidate.parent
    return list(records.values())
