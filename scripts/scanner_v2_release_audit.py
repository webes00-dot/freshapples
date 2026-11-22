"""Audit the configured retailer menus before the Scanner V2 cutover."""
import argparse
import asyncio
import csv
import json
import re
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlunsplit

from scanner_v2_capture import capture_rendered
from scanner_v2_master import load_snapshot
from scanner_v2_pilot import read_menu, write_holds
from scanner_v2_reconcile import reconcile
from scanner_v2_source_plan import discover_plan, source_class
from scanner_v2_validate import validate


PAGE_LIMIT = 30
BATCH_COUNT = 10
STORE_TIMEOUT_SECONDS = 240
STORE_TIMEOUT_STATUS = "Store capture timed out"
BATCH_ARTIFACT = re.compile(r"v2-menu-batch-(\d+)-attempt-(\d+)")
CATEGORY_PATH = re.compile(
    r"/(?:rec|menu)/(?:flower|pre[-_]?rolls?|vapes?|vaporizers?|carts?|concentrates?)(?:-\d+)?/?$",
    re.I,
)


def menu_key(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip("/") or "/", p.query, ""))


def menu_links(current, hrefs):
    current_parts = urlsplit(current)
    links = set()
    for href in hrefs:
        target = urlsplit(href)
        if target.scheme != "https" or target.netloc != current_parts.netloc:
            continue
        category = parse_qs(target.query).get("dtche[category]", [""])[0]
        if CATEGORY_PATH.search(target.path) or category in {
            "flower", "pre-rolls", "prerolls", "vaporizers", "concentrates",
        } or (
            target.path.rstrip("/") == current_parts.path.rstrip("/")
            and parse_qs(target.query).get("page", [""])[0].isdigit()
        ):
            links.add(menu_key(href))
    return sorted(links)


def targets_from_master(retailers):
    candidates = {}
    for retailer, plan in zip(retailers, discover_plan(retailers), strict=True):
        sources = [(item["url"], False) for item in plan["first_party_candidates"]]
        sources.extend((item["url"], True) for item in plan["secondary_candidates"]
                       if item["origin"] == "retailer_master_fallback")
        deduped = {}
        for url, fallback in sources:
            if urlsplit(url).scheme == "https":
                deduped.setdefault(menu_key(url), (url, fallback))
        candidates[retailer["id"]] = list(deduped.values())
    counts = Counter(menu_key(url) for sources in candidates.values() for url, _ in sources)
    targets, skipped = [], []
    for retailer in retailers:
        sources = candidates[retailer["id"]]
        eligible = [(url, fallback) for url, fallback in sources if counts[menu_key(url)] == 1]
        if eligible:
            targets.append({**retailer, "menu_url": eligible[0][0], "audit_sources": eligible})
            continue
        url = retailer.get("menu_url") or ""
        parts = urlsplit(url)
        if not url:
            reason = "No approved menu URL"
        elif parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            reason = "Unsupported menu URL"
        elif source_class(url) in {"secondary", "directory_or_social", "missing"}:
            reason = "Secondary menu source"
        elif sources:
            reason = "Menu URL shared by multiple locations"
        else:
            reason = "No eligible store-specific menu URL"
        skipped.append((retailer, reason))
    return targets, skipped


def apply_master_sources(directory, master):
    if master is None:
        return directory
    indexed = {row["id"]: row for row in master["retailers"]}
    for retailer in directory:
        entry = indexed.pop(retailer["id"], None)
        if entry is None:
            continue
        for key in ("website_url", "menu_platform", "platform_location_id", "fallback_menu_url"):
            if entry.get(key):
                retailer[key] = entry[key]
        if source_class(entry.get("menu_url")) not in ("missing", "secondary", "directory_or_social"):
            retailer["menu_url"] = entry["menu_url"]
    fields = ("id", "name", "menu_url", "website_url", "menu_platform",
              "platform_location_id", "fallback_menu_url")
    directory.extend({key: row[key] for key in fields if row.get(key)}
                     for row in indexed.values())
    return directory


def audit_plan(path):
    directory = json.loads(path.read_text(encoding="utf-8"))
    targets, skipped = targets_from_master(directory)
    by_host = defaultdict(list)
    for retailer in sorted(targets, key=lambda row: row["id"]):
        by_host[urlsplit(retailer["menu_url"]).hostname].append(retailer)
    batches = [[] for _ in range(BATCH_COUNT)]
    for _, stores in sorted(by_host.items(), key=lambda item: (-len(item[1]), item[0])):
        min(batches, key=len).extend(stores)
    return directory, batches, skipped


def write_json(path, data):
    pending = path.with_suffix(".tmp")
    pending.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
    pending.replace(path)


async def capture_store(browser, retailer):
    from playwright.async_api import Error as BrowserError

    root = retailer["menu_url"]
    visited, product_keys = set(), set()
    statuses, products = [], []
    attempted = []
    seen_controls = False
    source_has_timeout = False
    sources = retailer["audit_sources"]
    source_timeout = (STORE_TIMEOUT_SECONDS - 30) / len(sources)
    page = await browser.new_page()
    try:
        for source, fallback in sources:
            attempted.append(source)
            pending = deque([menu_key(source)])
            source_pages = 0
            try:
                async with asyncio.timeout(source_timeout):
                    while pending and source_pages < PAGE_LIMIT:
                        url = pending.popleft()
                        if url in visited:
                            continue
                        visited.add(url)
                        source_pages += 1
                        status, cards = await read_menu(page, url)
                        statuses.append(status)
                        for card in cards:
                            key = (card["product_url"], card["card_text"], card["source_product_id"])
                            if key not in product_keys:
                                product_keys.add(key)
                                products.append({**card, "secondary_source": fallback})
                        if status in {"Age gate", "Access limited"} or status.endswith(("HTTP 401", "HTTP 403", "HTTP 429")):
                            break
                        try:
                            for frame in page.frames:
                                hrefs = await frame.locator("a[href]").evaluate_all(
                                    "(nodes) => nodes.map(node => node.href)")
                                pending.extend(link for link in menu_links(frame.url, hrefs) if link not in visited)
                                if await frame.get_by_role("button", name=re.compile(
                                        r"^(?:next(?: page)?|load more|show more products)$", re.I)).count():
                                    seen_controls = True
                        except BrowserError:
                            statuses.append("Page links unavailable")
            except TimeoutError:
                source_has_timeout = True
                statuses.append("Menu source timed out")
            if pending and source_pages >= PAGE_LIMIT:
                statuses.append("Page limit reached")
            if products:
                if fallback:
                    statuses.append("Cards captured from fallback menu")
                break
        if seen_controls:
            statuses.append("Button pagination requires adapter")
    finally:
        await page.close()
    if source_has_timeout and not products:
        statuses.append(STORE_TIMEOUT_STATUS)
    return {
        "id": retailer["id"], "retailer": retailer["name"], "menu_url": root,
        "attempted_menu_urls": attempted, "menu_platform": retailer.get("menu_platform", ""),
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "statuses": statuses, "products": products, "pages": len(visited),
    }


async def scan_targets(retailers, checkpoint=None):
    from playwright.async_api import async_playwright

    gate = asyncio.Semaphore(8)
    hosts = defaultdict(lambda: asyncio.Semaphore(2))
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)

        async def scan(retailer):
            host = urlsplit(retailer["menu_url"]).hostname
            async with hosts[host], gate:
                try:
                    result = await asyncio.wait_for(capture_store(browser, retailer), STORE_TIMEOUT_SECONDS)
                except TimeoutError:
                    result = {
                        "id": retailer["id"], "retailer": retailer["name"],
                        "menu_url": retailer["menu_url"], "pages": 0, "products": [],
                        "statuses": [STORE_TIMEOUT_STATUS],
                    }
                if checkpoint:
                    checkpoint(result)
                return result

        try:
            return await asyncio.gather(*(scan(r) for r in retailers))
        finally:
            await browser.close()


def combine_batches(directory, batches, skipped, artifacts):
    expected = {retailer["id"]: (number, retailer["menu_url"])
                for number, batch in enumerate(batches, 1) for retailer in batch}
    captures = {}
    for folder in artifacts.iterdir() if artifacts.is_dir() else ():
        match = BATCH_ARTIFACT.fullmatch(folder.name)
        if not match or not folder.is_dir():
            continue
        number, attempt = map(int, match.groups())
        for path in folder.glob("retailer-*.json"):
            result = json.loads(path.read_text(encoding="utf-8"))
            retailer_id = result["id"]
            if expected.get(retailer_id) != (number, result["menu_url"]):
                raise ValueError(f"Unexpected capture for retailer {retailer_id} in batch {number}")
            rank = (STORE_TIMEOUT_STATUS not in result["statuses"], attempt)
            if retailer_id not in captures or rank > captures[retailer_id][0]:
                captures[retailer_id] = rank, result

    by_batch = []
    for number, batch in enumerate(batches, 1):
        finished = sum(retailer["id"] in captures and captures[retailer["id"]][0][0] for retailer in batch)
        by_batch.append({"batch": number, "targets": len(batch), "finished": finished})
    return {
        "directory_count": len(directory),
        "skipped": skipped,
        "results": [captures[key][1] for key in expected if key in captures],
        "missing": [row for row in directory if row["id"] in expected and row["id"] not in captures],
        "batches": by_batch,
    }


def write_coverage(path, batch, accepted=None):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Retailer", "Retailer ID", "Menu URL", "Pages checked", "Raw cards", "Validated offers",
                         "Statuses", "Menu platform", "Attempted menu URLs"])
        for result in batch["results"]:
            writer.writerow([result["retailer"], result["id"], result["menu_url"], result["pages"],
                             len(result["products"]), accepted[result["id"]] if accepted is not None else "",
                             " | ".join(dict.fromkeys(result["statuses"])), result.get("menu_platform", ""),
                             " | ".join(result.get("attempted_menu_urls", []))])
        for retailer, reason in batch["skipped"]:
            writer.writerow([retailer["name"], retailer["id"], retailer.get("menu_url"), 0, 0, "", reason,
                             retailer.get("menu_platform", ""), ""])
        for retailer in batch.get("missing", []):
            writer.writerow([retailer["name"], retailer["id"], retailer["menu_url"], 0, 0, "",
                             "Batch did not return a result", retailer.get("menu_platform", ""), ""])


def write_capture_report(output, batch):
    summary = {
        "registry_locations": batch["directory_count"],
        "menu_targets": sum(row["targets"] for row in batch["batches"]),
        "finished_targets": sum(row["finished"] for row in batch["batches"]),
        "locations_with_cards": sum(bool(result["products"]) for result in batch["results"]),
        "locations_captured_after_age_prompt": sum(
            "Cards captured after age prompt" in result["statuses"] for result in batch["results"]),
        "locations_captured_from_fallback": sum(
            "Cards captured from fallback menu" in result["statuses"] for result in batch["results"]),
        "raw_cards": sum(len(result["products"]) for result in batch["results"]),
        "skipped": dict(Counter(reason for _, reason in batch["skipped"])),
        "limitations": dict(Counter(status for result in batch["results"] for status in set(result["statuses"])
                                    if not status.startswith("Cards captured"))),
        "missing_results": len(batch["missing"]),
        "batches": batch["batches"],
    }
    write_json(output / "public-captures.json", batch)
    write_json(output / "capture-summary.json", summary)
    write_coverage(output / "retailer-coverage.csv", batch)
    print(json.dumps(summary, indent=2))
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--public-directory", type=Path)
    p.add_argument("--captures", type=Path)
    p.add_argument("--master-snapshot", type=Path)
    p.add_argument("--batch", type=int, choices=range(1, BATCH_COUNT + 1))
    p.add_argument("--merge-batches", type=Path)
    p.add_argument("--prepare-directory", action="store_true")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.prepare_directory:
        if not args.public_directory or not args.master_snapshot or args.batch or args.merge_batches or args.captures:
            p.error("--prepare-directory requires --public-directory and --master-snapshot")
        directory = json.loads(args.public_directory.read_text(encoding="utf-8"))
        write_json(args.output / "retailers.json", apply_master_sources(directory, load_snapshot(args.master_snapshot)))
        return
    if args.public_directory and not args.captures and not args.master_snapshot:
        if args.batch and args.merge_batches:
            p.error("--batch and --merge-batches are mutually exclusive")
        if args.batch or args.merge_batches:
            directory, batches, skipped = audit_plan(args.public_directory)
            if args.merge_batches:
                batch = combine_batches(directory, batches, skipped, args.merge_batches)
                summary = write_capture_report(args.output, batch)
                if summary["finished_targets"] != summary["menu_targets"]:
                    raise SystemExit("Some retailer captures did not finish; see the coverage report")
                return
            stores = batches[args.batch - 1]
            indexes = {row["id"]: index for index, row in enumerate(stores, 1)}
            print(f"Batch {args.batch}/{BATCH_COUNT}: {len(stores)} retailer menus", flush=True)

            def checkpoint(result):
                write_json(args.output / f"retailer-{indexes[result['id']]:03}.json", result)
                print(f"{result['retailer']}: {len(result['products'])} cards; {', '.join(result['statuses'])}",
                      flush=True)

            results = asyncio.run(scan_targets(stores, checkpoint)) if stores else []
            if any(STORE_TIMEOUT_STATUS in result["statuses"] for result in results):
                raise SystemExit("A retailer capture timed out; other results were saved")
            return
        directory = json.loads(args.public_directory.read_text(encoding="utf-8"))
        targets, skipped = targets_from_master(directory)
        results = asyncio.run(scan_targets(targets))
        print(f"Checked {len(targets)} public menu URLs; {len(skipped)} locations skipped")
        (args.output / "public-captures.json").write_text(
            json.dumps({"directory_count": len(directory), "skipped": skipped,
                        "results": results}, ensure_ascii=False) + "\n", encoding="utf-8")
        return
    if not args.captures or not args.master_snapshot or args.public_directory or args.batch or args.merge_batches:
        p.error("use --public-directory alone or --captures with --master-snapshot")
    batch = json.loads(args.captures.read_text(encoding="utf-8"))
    master = load_snapshot(args.master_snapshot)
    results, skipped = batch["results"], batch["skipped"]
    captured, capture_holds = capture_rendered({"results": results})
    rows = reconcile(captured, master["strain_master"], master["brands"], approved_brands=master["brands"])
    validated = validate(rows)

    write_holds(args.output / "holds.csv", results, captured, capture_holds, rows, validated)
    accepted = Counter(row["retailer_id"] for row in validated["accepted"])
    write_coverage(args.output / "retailer-coverage.csv", batch, accepted)
    summary = {
        "registry_locations": batch["directory_count"],
        "menu_targets": len(results),
        "locations_with_cards": sum(bool(result["products"]) for result in results),
        "skipped": dict(Counter(reason for _, reason in skipped)),
        "limitations": dict(Counter(status for result in results for status in set(result["statuses"])
                                    if not status.startswith("Cards captured"))),
        "observations": len(captured), "capture_holds": len(capture_holds),
        "accepted": len(validated["accepted"]), "validation_holds": len(validated["holds"]),
        "deduplicated": len(validated["duplicates_suppressed"]),
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (args.output / "accepted.json").write_text(json.dumps(validated["accepted"], ensure_ascii=False) + "\n",
                                                encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if not validated["accepted"]:
        raise SystemExit("No retailer offers passed validation")


if __name__ == "__main__":
    main()
