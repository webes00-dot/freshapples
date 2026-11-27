#!/usr/bin/env python3
"""Reconcile licensed storefronts and menu identities into the D1 masters."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
from difflib import get_close_matches
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
from publish_offers import request_json, workflow_token

HUB = "mncannabishub.com"
SITEMAP = f"https://{HUB}/sitemaps/dispensaries.xml"
ENTITY_ENDPOINT = "https://mntrees.co/api/internal/scanner-entities"
SITE_LICENSE = re.compile(r"[A-Z0-9]+-L\d{2}-\d{6}-\d{2}-AUR", re.I)
FLOWHUB_HOST = re.compile(r"[a-z0-9-]+\.dispensary\.shop")
AGGREGATORS = ("leafly.com", "weedmaps.com", "jointcommerce.com",
               "twincitycannabis.com", HUB, "thcminnesota.com",
               "google.com", "facebook.com", "instagram.com")
CHECKED_SOURCES = {"jsonld", "flowhub_html_card_review_only", "tymber_html_card"}
REVIEW_REASONS = ("scanner_new_entity", "scanner_identity_uncertain", "scanner_retailer_conflict",
                  "scanner_single_source", "scanner_reclassified")
STRAIN_CATEGORIES = {"flower", "preroll", "pre roll", "infused preroll", "infused pre roll",
                     "concentrate", "concentrates"}
DETAIL = re.compile(r"(?i)^(?:\d+(?:\.\d+)?\s*(?:g(?:rams?)?|mg|%|pk|ct)|(?:indica|sativa|hybrid)(?:\s+dominant)?|(?:deli|prepackaged|premium)\s+flower)$")
FORMAT = re.compile(r"(?i)\b(?:pre[ -]?rolls?|disposable|cartridge|distillate|"
                    r"rosin|resin|deli|small buds|smalls|shake|popcorn|pack|flower|"
                    r"blends?|infused|live|sale|cart|limited release|sample|grams?|pre[ -]?packaged|"
                    r"(?:little|big) sticks?|mixed buds|dogwalkers?|box|single|hybrid|sativa|indica)\b")
PLACEHOLDER = re.compile(r"(?i)^(?:unknown|n/?a|none|assorted|variety|house|"
                         r"(?:brand|strain)\s+(?:not\s+)?(?:available|confirmed|specified|listed)|"
                         r"mixed(?:\s+strains?)?|sativa|indica|hybrid|other)$")
PACKAGE_SUFFIX = re.compile(r"(?i)\s+\d+(?:\.\d+)?\s*(?:g(?:rams?)?|mg|%|ct|pk)$")
TITLE_RULES = {name: re.compile(pattern, re.I) for name, pattern in json.loads(
    (ROOT.parent / "src" / "menu-title-rules.json").read_text(encoding="utf-8")
).items()}


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
    if isinstance(value, list):
        return value
    return re.split(r"[,;|\n]", value or "")


class D1:
    def __init__(self):
        self.token = workflow_token()

    def query(self, operation, params=()):
        return self.batch([statement(operation, *params)])[0]

    def batch(self, commands):
        request = Request(ENTITY_ENDPOINT, data=json.dumps(commands).encode(), headers={
            "Authorization": "Bearer " + self.token, "Content-Type": "application/json",
            "User-Agent": "MNtrees-Scanner/1.0",
        })
        return request_json(request, attempts=8)


def statement(operation, *params):
    return {"operation": operation, "params": list(params)}


def commit(db, commands):
    for start in range(0, len(commands), 20):
        db.batch(commands[start:start + 20])


def review(entity, identity, reason, evidence):
    return statement("add_review", entity, identity, reason, json.dumps(evidence),
                     entity, identity, reason)


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
                    "add_retailer_menu",
                    record["menu_url"], matches[0]["id"],
                ))
                matches[0]["menu_url"] = record["menu_url"]
                events.append(("retailer", record["name"], "scanner_new_entity", {**record, "change": "menu added"}))
                continue
            commands.append(statement(
                "add_retailer",
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
            canonical_key = key(canonical)
            self.exact[token].add(canonical_key)
            self.compact[token.replace(" ", "")].add(canonical_key)

    def check(self, label):
        token = key(label)
        matches = self.exact.get(token, set())
        if len(matches) == 1:
            return "current"
        compact = token.replace(" ", "")
        if (matches or self.compact.get(compact)
                or (len(compact) >= 7 and get_close_matches(compact, self.compact, n=1, cutoff=0.91))):
            return "ambiguous"
        return "new"


def strain_name(title, brand, category=""):
    fields = re.split(r"\s*\|\s*|\s+[-–—]\s+", TITLE_RULES["promotion"].sub("", title.strip()))
    distinct = []
    for field in fields:
        field = PACKAGE_SUFFIX.sub("", field.strip()).strip(" -–—,")
        field = TITLE_RULES["packSuffix"].sub("", TITLE_RULES["potency"].sub("", field)).strip()
        if not field or DETAIL.fullmatch(field) or TITLE_RULES["packaging"].fullmatch(field) or key(field) == key(brand):
            continue
        # A separately labeled brand is safe to remove. A shared substring is not.
        if key(brand) and key(field).startswith(key(brand) + " "):
            words = field.split()
            for end in range(1, len(words)):
                if key(" ".join(words[:end])) == key(brand):
                    field = " ".join(words[end:])
                    break
        if "roll" in category:
            field = TITLE_RULES["stickLine"].sub("", field)
        distinct.append(field)
    if len(distinct) != 1:
        return ""
    name = distinct[0]
    if (FORMAT.search(name) or PLACEHOLDER.fullmatch(name)
            or re.search(r"\d\s*(?:%|g\b|mg\b|ct\b|p(?:a)?ck\b)|\d\s*[./]\s*\d|[$@!#]|\b(?:THC|CBD)\b", name, re.I)):
        return ""
    return name


def acceptable(label):
    return (isinstance(label, str) and 2 <= len(label) <= 80 and bool(re.search("[a-z]", label, re.I))
            and not PLACEHOLDER.fullmatch(label) and not any(char in label for char in "<>\r\n\t"))


def discover_products(offers, indexes):
    commands = []
    events = []
    evidence_by_name = defaultdict(dict)
    for offer in offers:
        if offer.get("source_method") not in CHECKED_SOURCES or not direct_url(offer.get("url")):
            continue
        category = key(offer.get("category"))
        observed_brand = offer.get("observed_brand")
        if category not in STRAIN_CATEGORIES | {"", "vape", "vapes"}:
            continue
        brand = canonical_brand(observed_brand) if acceptable(observed_brand) else ""
        title = offer.get("observed_product_name")
        explicit_strain = offer.get("observed_strain")
        strain = ""
        if isinstance(explicit_strain, str) and explicit_strain:
            strain = strain_name(explicit_strain, observed_brand, category)
        elif brand and isinstance(title, str) and category in STRAIN_CATEGORIES:
            strain = strain_name(title, observed_brand, category)
        evidence = {field: offer.get(field) for field in
                    ("url", "store_id", "retailer", "product_name", "observed_brand",
                     "observed_product_name", "observed_strain", "category", "checked_at")}
        for entity, label in (("brand", brand), ("strain", strain)):
            if not acceptable(label) or not offer.get("store_id"):
                continue
            evidence_by_name[entity, key(label)].setdefault(offer["store_id"], (label, evidence))
    for (entity, _), locations in sorted(evidence_by_name.items()):
        label, evidence = next(iter(locations.values()))
        index = indexes[entity]
        match = index.check(label)
        if match == "current":
            continue
        supporting_urls = list(dict.fromkeys(item["url"] for _, item in locations.values()))
        evidence = {**evidence, "retailer_count": len(locations), "supporting_urls": supporting_urls[:3]}
        if entity == "brand":
            shortened = re.sub(r"(?:\s+(?:cannabis|co|company|llc|supply|inc|collective))+$", "", key(label))
            if (shortened != key(label) and index.check(shortened) != "new"
                    or re.search(r"\s+(?:x|by)\s+|[/+]", label, re.I)):
                match = "ambiguous"
        if match == "ambiguous":
            events.append((entity, label, "scanner_identity_uncertain", evidence))
            continue
        if min(len(locations), len(supporting_urls)) < 2:
            events.append((entity, label, "scanner_single_source", evidence))
            continue
        commands.append(statement(
            "add_" + entity,
            label, json.dumps({"source": "scanner", "name": label, **evidence}),
        ))
        index.add(label, label)
        events.append((entity, label, "scanner_new_entity", evidence))
    return commands, events


def save(db, commands, events, *, dry_run):
    def identity(name, evidence):
        return evidence.get("license") or evidence.get("identity") or key(name)

    existing = {(row["entity_type"], row["entity_key"], row["reason"])
                for row in db.query("reviews")}
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
        current = db.query("retailers")
        try:
            pages = hub_pages(int(os.getenv("GITHUB_RUN_NUMBER", "1")))
        except (OSError, ValueError, RuntimeError, ElementTree.ParseError) as error:
            print(f"::warning::Hub retailer discovery unavailable ({type(error).__name__})")
            pages = []
        commands, events = discover_retailers(current, pages)
        result = save(db, commands, events, dry_run=options.dry_run)
        if options.targets and not options.dry_run:
            current = db.query("retailers")
            targets = target_rows(current, rows("menu_targets.csv"))
            options.targets.write_text(json.dumps(targets), encoding="utf-8")
            print(f"Scheduled scan targets: {len(targets)}")
    else:
        redirects = db.query("aliases")
        # The storefront still displays names from its verified baseline. They
        # count as existing even when there is no corresponding D1 master row.
        baseline = json.loads((ROOT.parent / "data" / "site-data.json").read_text(encoding="utf-8"))
        published = {
            "brand": [{"canonical_name": brand.get("name"), "aliases": brand.get("aliases")}
                      for brand in baseline["brands"]],
            "strain": [{"canonical_name": name, "aliases": None}
                       for name in {*baseline.get("strain_types", {}), *baseline.get("strain_profile_references", {})}
                                    if name],
        }
        indexes = {entity: Names(db.query(table) + published[entity],
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
