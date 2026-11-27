#!/usr/bin/env python3
"""Reconcile licensed storefronts and menu identities into the D1 masters."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from brand_aliases import canonical_brand
from collector import ROOT, fetch, rows
from flowhub_adapter import storefront_data

HUB = "mncannabishub.com"
SITEMAP = f"https://{HUB}/sitemaps/dispensaries.xml"
D1_DATABASE = "457785f2-ab73-4858-b524-ba613a2b5388"
SITE_LICENSE = re.compile(r"[A-Z0-9]+-L\d{2}-\d{6}-\d{2}-AUR", re.I)
FLOWHUB_HOST = re.compile(r"[a-z0-9-]+\.dispensary\.shop")
AGGREGATORS = ("leafly.com", "weedmaps.com", "jointcommerce.com",
               "twincitycannabis.com", HUB, "thcminnesota.com",
               "google.com", "facebook.com", "instagram.com")
RETAILER_FIELDS = "id, source_key, license_id, display_name, aliases, address, menu_url"
CHECKED_SOURCES = {"jsonld", "flowhub_html_card_review_only", "tymber_html_card"}
REVIEW_REASONS = ("scanner_new_entity", "scanner_identity_uncertain", "scanner_retailer_conflict")
STRAIN_CATEGORIES = {"flower", "preroll", "pre roll", "infused preroll", "infused pre roll",
                     "concentrate", "concentrates"}
DETAIL = re.compile(r"(?i)^(?:\d+(?:\.\d+)?\s*(?:g(?:rams?)?|mg|%|pk|ct)|(?:indica|sativa|hybrid)(?:\s+dominant)?|(?:deli|prepackaged|premium)\s+flower)$")
FORMAT = re.compile(r"(?i)\b(?:pre[ -]?rolls?|disposable|cartridge|distillate|"
                    r"rosin|resin|deli|small buds|smalls|shake|popcorn|pack|flower|"
                    r"blends?|infused|live|sale|cart|limited release|sample|grams?)\b")
PLACEHOLDER = re.compile(r"(?i)^(?:unknown|n/?a|none|assorted|variety|house|"
                         r"(?:brand|strain)\s+(?:not\s+)?(?:available|confirmed|specified|listed)|"
                         r"mixed(?:\s+strains?)?|sativa|indica|hybrid|other)$")
PACKAGE_SUFFIX = re.compile(r"(?i)\s+\d+(?:\.\d+)?\s*(?:g(?:rams?)?|mg|%|ct|pk)$")


def key(value):
    plain = unicodedata.normalize("NFKD", str(value or "").casefold())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in plain if not unicodedata.combining(c))).strip()


def street_key(value):
    substitutions = {"avenue": "ave", "street": "st", "road": "rd", "drive": "dr",
                     "boulevard": "blvd", "highway": "hwy", "suite": "ste"}
    return " ".join(substitutions.get(word, word) for word in key(value).split())


def host(value):
    try:
        url = urlsplit(value or "")
        if url.scheme == "https" and not url.username and not url.password:
            return url.hostname or ""
    except ValueError:
        pass
    return ""


def direct_url(value):
    domain = host(value)
    return bool(domain and not any(domain == site or domain.endswith("." + site) for site in AGGREGATORS))


def alias_parts(value):
    return re.split(r"[,;|\n]", value or "")


class D1:
    def __init__(self):
        account = os.environ["CLOUDFLARE_ACCOUNT_ID"]
        self.token = os.environ["CLOUDFLARE_API_TOKEN"]
        self.url = f"https://api.cloudflare.com/client/v4/accounts/{account}/d1/database/{D1_DATABASE}/query"

    def query(self, sql, params=()):
        body = json.dumps(statement(sql, *params)).encode()
        request = Request(self.url, data=body, headers={
            "Authorization": "Bearer " + self.token, "Content-Type": "application/json",
        })
        with urlopen(request, timeout=45) as response:
            payload = json.load(response)
        results = payload.get("result") or []
        if not payload.get("success") or len(results) != 1 or not results[0].get("success"):
            raise RuntimeError("Unsuccessful D1 entity reconciliation")
        return results[0]["results"]


def statement(sql, *params):
    return {"sql": sql, "params": list(params)}


def commit(db, commands):
    with ThreadPoolExecutor(max_workers=5) as pool:
        for _ in pool.map(lambda item: db.query(**item), commands):
            pass


def review(entity, identity, reason, evidence):
    return statement(
        """INSERT INTO review_queue (entity_type, entity_key, reason, payload_json)
           SELECT ?, ?, ?, ? WHERE NOT EXISTS
           (SELECT 1 FROM review_queue WHERE entity_type = ? AND entity_key = ? AND reason = ?)""",
        entity, identity, reason, json.dumps(evidence), entity, identity, reason,
    )


class MenuLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = set()
        self.unverified = set()

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        url = urlsplit(dict(attrs).get("href") or "")
        if FLOWHUB_HOST.fullmatch(host(url.geturl())) and re.fullmatch(r"/rec/(?:menu|all-products(?:/[^/]+)*)/?", url.path):
            self.links.add(url._replace(query="", fragment="").geturl())
        elif direct_url(url.geturl()) and re.fullmatch(r"/(?:shop|menu|order|embedded-menu)(?:/[^/]+)*/?", url.path):
            self.unverified.add(url._replace(query="", fragment="").geturl())


def hub_pages(run_number, count=36):
    req = Request(SITEMAP, headers={"User-Agent": "MNtrees-menu-research/1.0"})
    with urlopen(req, timeout=15) as response:
        root = ElementTree.fromstring(response.read(1_000_000))
    links = list(dict.fromkeys(node.text for node in root.findall(".//{*}loc")
                               if node.text and host(node.text) == HUB
                               and re.fullmatch(r"/dispensaries/[a-z0-9-]+", urlsplit(node.text).path)))
    if not links:
        raise RuntimeError("No retailer pages found in Hub sitemap")
    start = ((run_number - 1) * count) % len(links)
    return (links + links)[start:start + count]


def storefront(lead, menu):
    result = fetch(menu, timeout=10)
    if not result.get("ok") or host(result["url"]) != host(menu):
        return None
    root, _ = storefront_data(result["html"])
    contact = root.get("contactInfo") or {}
    licenses = {str(row.get("license_number", "")).upper() for row in root.get("licenses") or []
                if row.get("license_type") == "REC" and SITE_LICENSE.fullmatch(str(row.get("license_number", "")))}
    if len(licenses) != 1 or contact.get("state") != "MN":
        return None
    name, address, city, zip_code = (str(contact.get(field) or "").strip()
                                      for field in ("name", "address", "city", "zip"))
    if not name or not address or not city or not re.fullmatch(r"\d{5}(?:-\d{4})?", zip_code):
        return None
    website = contact.get("website")
    return {"name": name, "license": licenses.pop(),
            "address": f"{address}, {city}, MN {zip_code}", "menu_url": result["url"],
            "website_url": website if direct_url(website) else None, "discovery_url": lead}


def discover_retailers(current, pages, *, delay=1):
    by_license = defaultdict(list)
    by_address = defaultdict(list)
    known_urls = set()
    for row in current:
        by_license[key(row["license_id"])].append(row)
        if row["address"]:
            by_address[street_key(row["address"])].append(row)
        if row["menu_url"] and FLOWHUB_HOST.fullmatch(host(row["menu_url"])):
            known_urls.add(host(row["menu_url"]))
    commands = []
    events = []
    checked_menus = set(known_urls)
    for index, page in enumerate(pages):
        if index:
            time.sleep(delay)
        result = fetch(page, timeout=10)
        if not result.get("ok") or host(result["url"]) != HUB:
            continue
        links = MenuLinks()
        links.feed(result["html"])
        for menu in sorted(links.unverified):
            if host(menu) not in known_urls:
                events.append(("retailer", urlsplit(page).path.rsplit("/", 1)[-1],
                               "scanner_identity_uncertain", {"menu_url": menu, "discovery_url": page,
                                                               "identity": menu, "change": "verify location license"}))
        for menu in sorted(links.links):
            if host(menu) in checked_menus:
                continue
            checked_menus.add(host(menu))
            record = storefront(page, menu)
            if not record:
                events.append(("retailer", urlsplit(page).path.rsplit("/", 1)[-1],
                               "scanner_identity_uncertain", {"menu_url": menu, "discovery_url": page,
                                                               "identity": menu, "change": "verify location license"}))
                continue
            license_id = record["license"]
            matches = by_license[key(license_id)]
            address_matches = by_address[street_key(record["address"])]
            if len(matches) > 1 or (not matches and address_matches) or (matches and matches[0]["menu_url"]):
                events.append(("retailer", record["name"], "scanner_retailer_conflict", record))
                continue
            if matches:
                commands.append(statement(
                    """UPDATE retailers SET menu_url = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE id = ? AND trim(coalesce(menu_url, '')) = ''""",
                    record["menu_url"], matches[0]["id"],
                ))
                matches[0]["menu_url"] = record["menu_url"]
                events.append(("retailer", record["name"], "scanner_new_entity", {**record, "change": "menu added"}))
                continue
            commands.append(statement(
                """INSERT INTO retailers (source_key, display_name, license_id, address, menu_url, website_url, raw_json)
                   SELECT ?, ?, ?, ?, ?, ?, ?
                   WHERE NOT EXISTS (SELECT 1 FROM retailers WHERE upper(license_id) = ?)
                   ON CONFLICT(source_key) DO NOTHING""",
                "scanner:" + license_id, record["name"], license_id, record["address"],
                record["menu_url"], record["website_url"], json.dumps({"source": "scanner", **record}), license_id,
            ))
            by_license[key(license_id)].append({"menu_url": record["menu_url"]})
            by_address[street_key(record["address"])].append(record)
            events.append(("retailer", record["name"], "scanner_new_entity", record))
    return commands, events


def target_rows(current, legacy):
    targets = {row["license"]: row for row in legacy}
    used_urls = {row["verified_direct_menu_url"].rstrip("/") for row in legacy}
    for row in current:
        license_id = row["license_id"] or row["source_key"]
        url = row["menu_url"] or ""
        if not row["display_name"] or not direct_url(url):
            continue
        existing = targets.get(license_id)
        if existing:
            existing_url = existing["verified_direct_menu_url"]
            if host(existing_url) == host(url) and urlsplit(url).path in ("", "/"):
                continue
            if existing_url.rstrip("/") == url.rstrip("/"):
                continue
        if url.rstrip("/") in used_urls:
            continue
        if existing:
            used_urls.discard(existing["verified_direct_menu_url"].rstrip("/"))
        targets[license_id] = {"license": license_id, "retailer": row["display_name"],
                               "verified_direct_menu_url": url}
        used_urls.add(url.rstrip("/"))
    return list(targets.values())


class Names:
    def __init__(self, rows, redirects):
        self.exact = defaultdict(set)
        self.compact = defaultdict(set)
        for row in rows:
            self.add(row["canonical_name"], row["canonical_name"])
            for alias in alias_parts(row["aliases"]):
                self.add(alias, row["canonical_name"])
        for row in redirects:
            self.add(row["observed_name"], row["canonical_name"])

    def add(self, label, canonical):
        token = key(label)
        if token and canonical:
            self.exact[token].add(canonical)
            self.compact[token.replace(" ", "")].add(canonical)

    def check(self, label):
        token = key(label)
        matches = self.exact.get(token, set())
        if len(matches) == 1:
            return "current"
        if matches or self.compact.get(token.replace(" ", "")):
            return "ambiguous"
        return "new"


def strain_name(title, brand):
    fields = re.split(r"\s*\|\s*|\s+[-–—]\s+", title.strip())
    distinct = []
    for field in fields:
        field = PACKAGE_SUFFIX.sub("", field.strip()).strip(" -–—,")
        if not field or DETAIL.fullmatch(field) or key(field) == key(brand):
            continue
        # A separately labeled brand is safe to remove. A shared substring is not.
        if key(brand) and key(field).startswith(key(brand) + " "):
            words = field.split()
            for end in range(1, len(words)):
                if key(" ".join(words[:end])) == key(brand):
                    field = " ".join(words[end:])
                    break
        distinct.append(field)
    if len(distinct) != 1:
        return ""
    name = distinct[0]
    if (FORMAT.search(name) or PLACEHOLDER.fullmatch(name)
            or re.search(r"\d\s*(?:%|g\b|mg\b|ct\b)|[$@!]|\b(?:THC|CBD)\b", name, re.I)):
        return ""
    return name


def acceptable(label):
    return (isinstance(label, str) and 2 <= len(label) <= 80 and bool(re.search("[a-z]", label, re.I))
            and not PLACEHOLDER.fullmatch(label) and not any(char in label for char in "<>\r\n\t"))


def discover_products(offers, indexes):
    commands = []
    events = []
    seen = set()
    for offer in offers:
        if offer.get("source_method") not in CHECKED_SOURCES or not direct_url(offer.get("url")):
            continue
        category = key(offer.get("category"))
        observed_brand = offer.get("observed_brand")
        if not acceptable(observed_brand) or category not in STRAIN_CATEGORIES | {"", "vape", "vapes"}:
            continue
        brand = canonical_brand(observed_brand)
        title = offer.get("observed_product_name")
        strain = strain_name(title, observed_brand) if isinstance(title, str) and category in STRAIN_CATEGORIES else ""
        evidence = {field: offer.get(field) for field in
                    ("url", "store_id", "retailer", "product_name", "observed_brand",
                     "observed_product_name", "category", "checked_at")}
        for entity, label in (("brand", brand), ("strain", strain)):
            if not acceptable(label) or (entity, key(label)) in seen:
                continue
            index = indexes[entity]
            match = index.check(label)
            seen.add((entity, key(label)))
            if match == "current":
                continue
            if match == "ambiguous":
                events.append((entity, label, "scanner_identity_uncertain", evidence))
                continue
            table, status_column = {"brand": ("brands", "research_status"),
                                    "strain": ("strains", "review_status")}[entity]
            commands.append(statement(
                f"""INSERT INTO {table} (canonical_name, {status_column}, raw_json)
                    VALUES (?, 'needs_review', ?) ON CONFLICT(canonical_name) DO NOTHING""",
                label, json.dumps({"source": "scanner", "name": label, **evidence}),
            ))
            index.add(label, label)
            events.append((entity, label, "scanner_new_entity", evidence))
    return commands, events


def save(db, commands, events, *, dry_run):
    def identity(name, evidence):
        return evidence.get("license") or evidence.get("identity") or key(name)

    existing = {(row["entity_type"], row["entity_key"], row["reason"])
                for row in db.query("""SELECT entity_type, entity_key, reason FROM review_queue
                                      WHERE reason IN (?, ?, ?)""", REVIEW_REASONS)}
    new_events = []
    for kind, name, reason, evidence in events:
        event_key = (kind, identity(name, evidence), reason)
        if event_key not in existing:
            new_events.append((kind, name, reason, evidence))
            existing.add(event_key)
    if not dry_run:
        # Write review evidence first so a retry can still discover any missing master rows.
        commit(db, [review(kind, identity(name, evidence), reason, {"name": name, **evidence})
                    for kind, name, reason, evidence in new_events])
        commit(db, commands)
    return [{"entity": kind, "name": name, "reason": reason, **evidence}
            for kind, name, reason, evidence in new_events]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("retailers", "products"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--targets", type=Path)
    options = parser.parse_args()
    db = D1()
    if options.phase == "retailers":
        current = db.query(f"SELECT {RETAILER_FIELDS} FROM retailers ORDER BY id")
        try:
            pages = hub_pages(int(os.getenv("GITHUB_RUN_NUMBER", "1")))
        except (OSError, ValueError, RuntimeError, ElementTree.ParseError) as error:
            print(f"::warning::Hub retailer discovery unavailable ({type(error).__name__})")
            pages = []
        commands, events = discover_retailers(current, pages)
        result = save(db, commands, events, dry_run=options.dry_run)
        if options.targets and not options.dry_run:
            current = db.query(f"SELECT {RETAILER_FIELDS} FROM retailers ORDER BY id")
            targets = target_rows(current, rows("menu_targets.csv"))
            options.targets.write_text(json.dumps(targets), encoding="utf-8")
            print(f"Scheduled scan targets: {len(targets)}")
    else:
        redirects = db.query("""SELECT lower(entity_type) AS entity_type, observed_name, canonical_name
                                FROM entity_aliases WHERE lower(action) IN ('normalize', 'canonical')""")
        indexes = {entity: Names(db.query(f"SELECT canonical_name, aliases FROM {table}"),
                                  [row for row in redirects if row["entity_type"] == entity])
                   for entity, table in (("brand", "brands"), ("strain", "strains"))}
        offers = json.loads((ROOT / "data" / "candidate_products.json").read_text(encoding="utf-8"))
        commands, events = discover_products(offers, indexes)
        result = save(db, commands, events, dry_run=options.dry_run)
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "dry_run": options.dry_run,
              "phase": options.phase, "events": result}
    options.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{options.phase}: {len(result)} discovery events")
    if summary := os.getenv("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(f"### Entity discovery • {options.phase}\n\n")
            for reason in REVIEW_REASONS:
                selected = [row for row in result if row["reason"] == reason]
                if selected:
                    names = ", ".join(row["name"].replace("<", "&lt;").replace(">", "&gt;")
                                      for row in selected[:30])
                    handle.write(f"- {reason.replace('scanner_', '').replace('_', ' ')} ({len(selected)}) — {names}\n")
            if not result:
                handle.write("No new entities this run.\n")


if __name__ == "__main__":
    main()
