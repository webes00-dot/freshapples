#!/usr/bin/env python3
"""Capture and review public menu evidence from the three pilot retailers."""
import argparse
import asyncio
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from scanner_v2_capture import capture_rendered
from scanner_v2_master import load_snapshot
from scanner_v2_reconcile import reconcile
from scanner_v2_validate import validate


PILOT_MENUS = {
    "Dinky Dope": ("https://shop.dinkydope.com/dinkytown",),
    "Green Leaf Depot": ("https://greenleafdepot.dispensary.shop",),
    "Off The Path Cannabis — Morton": (
        "https://offthepathcannabis.com/shop/",
        "https://offthepathcannabis.com/shop/?dtche%5Bcategory%5D=vaporizers",
    ),
}
PRICE = re.compile(r"\$\s*(\d{1,5}(?:,\d{3})*(?:\.\d{2})?)")
AGE_GATE = re.compile(
    r"(?:verify|confirm) (?:your )?age|age verification|are you (?:over |at least )?21"
    r"|enter your date of birth|you must be (?:at least )?21|\b21\s*(?:\+|or older|years of age)",
    re.IGNORECASE,
)
ACCESS_LIMITED = re.compile(
    r"access denied|verify (?:that )?you are human|checking your browser",
    re.IGNORECASE,
)

READ_CARDS = r"""() => {
  const selector = [
    'article', '[class*="product-card"]', '[class*="productCard"]',
    '[class*="ProductCard"]', '[class*="product-item"]', '[class*="ProductItem"]',
    '[class*="menu-item"]', '[class*="MenuItem"]', '[data-product-id]',
    '[data-testid*="product"]', '[data-testid*="menu-item"]',
  ].join(',');
  const text = node => (node?.innerText || '').trim().replace(/\s+/g, ' ');
  const cardText = node => (node?.innerText || '').trim().replace(/[^\S\r\n]+/g, ' ');
  const cards = new Set(document.querySelectorAll(selector));
  for (const link of document.querySelectorAll('a[href]')) {
    if (link.origin === location.origin && /\/(?:product|products|pdp)\/[^/]+\/?$/i.test(link.pathname)
        && /\$\s*\d/.test(link.innerText)) cards.add(link.closest(selector) || link);
  }
  return Array.from(cards)
    .filter(element => element.getClientRects().length && element.checkVisibility({checkVisibilityCSS: true}))
    .map(element => ({
    text: cardText(element),
    href: element.closest('a[href]')?.href || element.querySelector('a[href]')?.href,
    title: text(element.querySelector('[data-testid*="product-name"],[class*="product-name"],[class*="productName"],h2,h3,h4')),
    brand: text(element.querySelector('[data-testid*="brand"],[class*="product-brand"],[class*="productBrand"]')),
    productId: element.getAttribute('data-product-id') || '',
  })).filter(card => card.text.length >= 12 && card.text.length <= 750 && card.text.includes('$'));
}"""

AGE_VERIFICATION_WIDGET = r"""() => {
  const prompt = /(?:verify|confirm) (?:your )?age|age verification|are you (?:over |at least )?21|date of birth|birth date/i;
  const fields = 'input[type="date"], input[autocomplete^="bday"], input[type="file"], input[name*="birth" i]';
  const visible = node => node.getClientRects().length && node.checkVisibility({checkVisibilityCSS: true});
  return [...document.querySelectorAll('form, dialog, [role="dialog"], [aria-modal="true"]')].some(widget => {
    if (!visible(widget) || !prompt.test(widget.innerText || '')) return false;
    return widget.matches('dialog, [role="dialog"], [aria-modal="true"]') ||
      [...widget.querySelectorAll(fields)].some(visible);
  });
}"""

READ_THC_MINNESOTA = r"""() => {
  const headers = ['product', 'brand', 'price', 'category', 'type', 'thc', 'size'];
  const clean = text => String(text || '').replace(/\s+/g, ' ').trim();
  const key = (name, category) => JSON.stringify([clean(name).toLowerCase(), clean(category).toLowerCase()]);
  const links = new Map();
  for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
    let data;
    try { data = JSON.parse(script.textContent); } catch { continue; }
    if (data?.['@type'] !== 'ItemList' || !Array.isArray(data.itemListElement)) continue;
    for (const entry of data.itemListElement) {
      const item = entry?.item;
      if (item?.['@type'] !== 'Product' || !item.url || !item.name || !item.category) continue;
      let url;
      try { url = new URL(item.url, location.href); } catch { continue; }
      if (url.origin !== location.origin || !/^\/products\/[^/]+\/?$/.test(url.pathname)) continue;
      const id = key(item.name, item.category);
      if (!links.has(id)) links.set(id, new Set());
      links.get(id).add(url.href);
    }
  }
  return [...document.querySelectorAll('table')].filter(table =>
    table.checkVisibility({checkVisibilityCSS: true}) &&
    [...table.querySelectorAll('thead th')].map(th => clean(th.innerText).toLowerCase()).join('|') === headers.join('|')
  ).flatMap(table => [...table.querySelectorAll('tbody tr')].flatMap(row => {
    if (!row.checkVisibility({checkVisibilityCSS: true}) || row.cells.length !== headers.length) return [];
    const [title, brand, priceText, category] = [...row.cells].map(cell => clean(cell.innerText));
    if (!title || !/^\$\s*[\d,]+(?:\.\d{2})?\*?$/.test(priceText)) return [];
    const candidates = links.get(key(title, category));
    const href = candidates?.size === 1 ? [...candidates][0] : null;
    return [{text: row.innerText.trim(), title, brand, href, priceText, category}];
  }));
}"""

AGE_CONFIRM_CONTROL = r"""() => {
  const prompt = /(?:verify|confirm) (?:your )?age|age verification|are you (?:over |at least )?21|you must be (?:at least )?21|\b21\s*(?:\+|years? (?:of age|old)|or older|and older)/i;
  const restricted = /date of birth|birth date|upload (?:an? |your )?(?:id|identification)|government[- ]issued|verify (?:your )?identity|sign in|log in|captcha|verify (?:that )?you are human/i;
  const explicitYes = /^(?:yes[,.!\s]+)?(?:i(?: am|['’]m) (?:at least |over )?21(?:\s*(?:\+|or older|years old))?|21\s*\+)[.!]?$/i;
  const shortYes = /^(?:yes(?:[,.!\s]+i am)?|enter(?: (?:site|website|store))?|continue|confirm(?: age)?)[.!]?$/i;
  const negative = /^(?:no\b|exit\b|leave\b|(?:i am |i['’]m )?(?:under|not) 21\b)/i;
  const selector = 'button, a[href], [role="button"], input[type="button"], input[type="submit"]';
  const fields = 'input:not([type="hidden"],[type="button"],[type="submit"]), select, textarea';
  const requiresVerification = node => restricted.test(node.innerText || '') || node.querySelector(fields);
  const visible = node => node.getClientRects().length && node.checkVisibility({checkVisibilityCSS: true});
  const label = node => (node.getAttribute('aria-label') || node.innerText || node.value || '')
    .replace(/\s+/g, ' ').trim();
  const matching = [];
  for (const control of document.querySelectorAll(selector)) {
    if (!visible(control) || control.matches(':disabled,[aria-disabled="true"]')) continue;
    const name = label(control);
    if (!explicitYes.test(name) && !shortYes.test(name)) continue;
    const widget = control.closest('form, dialog, [role="dialog"], [aria-modal="true"]');
    if (widget && requiresVerification(widget)) continue;
    for (let container = control.parentElement; container && container !== document.body;
         container = container.parentElement) {
      const text = container.innerText || '';
      if (text.length > 1500 || requiresVerification(container)) break;
      if (!prompt.test(text.replace(control.innerText || name, ''))) continue;
      const hasNegative = Array.from(container.querySelectorAll(selector))
        .some(other => other !== control && visible(other) && negative.test(label(other)));
      if (explicitYes.test(name) || hasNegative) {
        matching.push(control);
        break;
      }
    }
  }
  return matching.length === 1 ? matching[0] : null;
}"""


def rendered_products(cards, menu_url):
    products = []
    for card in cards:
        prices = [float(price.replace(",", "")) for price in PRICE.findall(card.get("priceText") or card["text"])]
        if prices:
            products.append({
                "card_text": card["text"], "price_candidates": prices,
                "product_url": card.get("href"), "source_menu_url": menu_url,
                "raw_product_title": card.get("title"),
                "brand_candidate": card.get("brand"),
                "source_product_id": card.get("productId"),
                "category_candidate": card.get("category"),
            })
    return products


async def read_menu(page, url):
    from playwright.async_api import Error as BrowserError

    embedded_errors = set()
    age_prompt_seen = False
    age_prompt_clicked = False

    def record_embedded_error(response):
        host = urlsplit(response.url).hostname or ""
        if (host == "dutchie.com" or host.endswith(".dutchie.com")) and response.status >= 400:
            embedded_errors.add(response.status)

    page.on("response", record_embedded_error)
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        if response and response.status >= 400:
            return f"HTTP {response.status}", []
        for attempt in range(6):
            rendered = []
            age_frames = []
            access_limited = False
            for frame in page.frames:
                try:
                    body = await frame.locator("body").inner_text(timeout=2_000)
                    if AGE_GATE.search(body):
                        age_frames.append(frame)
                    if ACCESS_LIMITED.search(body[:1200]):
                        if frame == page.main_frame:
                            return "Access limited", []
                        access_limited = True
                        continue
                    frame_url = urlsplit(frame.url)
                    if (frame_url.hostname in {"thcminnesota.com", "www.thcminnesota.com"}
                            and frame_url.path.startswith("/dispensary/")):
                        rendered.extend(await frame.evaluate(READ_THC_MINNESOTA))
                    else:
                        rendered.extend(await frame.evaluate(READ_CARDS))
                except BrowserError:
                    if frame == page.main_frame and attempt == 5:
                        return "Page unavailable", []
            products = rendered_products(rendered, url)
            if products:
                return ("Cards captured after age prompt" if age_prompt_clicked else "Cards captured"), products
            for code in (401, 403, 429):
                if code in embedded_errors:
                    return f"Embedded menu HTTP {code}", []
            if access_limited:
                return "Access limited", []
            if not age_prompt_clicked:
                for frame in age_frames:
                    try:
                        age_prompt_seen |= await frame.evaluate(AGE_VERIFICATION_WIDGET)
                        handle = await frame.evaluate_handle(AGE_CONFIRM_CONTROL)
                        try:
                            control = handle.as_element()
                            if control is not None:
                                age_prompt_seen = True
                                if attempt < 5:
                                    await control.click(timeout=2_000)
                                    age_prompt_clicked = True
                                break
                        finally:
                            await handle.dispose()
                    except BrowserError:
                        continue
            if attempt < 5:
                await asyncio.sleep(1)
    except BrowserError:
        return "Page unavailable", []
    finally:
        page.remove_listener("response", record_embedded_error)
    if embedded_errors:
        return f"Embedded menu HTTP {min(embedded_errors)}", []
    if age_prompt_seen:
        return "Age gate", []
    return "No product cards", []


async def capture_retailer(browser, name, urls, retailer_id):
    page = await browser.new_page()
    products, statuses, seen = [], [], set()
    scanned_at = datetime.now(timezone.utc).isoformat()
    try:
        for url in urls:
            status, cards = await read_menu(page, url)
            statuses.append(status)
            for card in cards:
                identity = (card["product_url"], card["card_text"], card["source_product_id"])
                if identity not in seen:
                    seen.add(identity)
                    products.append(card)
            if status in {"Age gate", "Access limited"} or status.endswith(("HTTP 401", "HTTP 403", "HTTP 429")):
                break
    finally:
        await page.close()
    return {
        "id": retailer_id, "retailer": name, "menu_url": urls[0], "scanned_at": scanned_at,
        "statuses": statuses, "products": products,
    }


async def capture_pilot(master):
    from playwright.async_api import async_playwright

    ids = {row["name"]: row["id"] for row in master["retailers"]} if master else {}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            return await asyncio.gather(*(
                capture_retailer(browser, name, urls, ids.get(name, f"pilot-{index}"))
                for index, (name, urls) in enumerate(PILOT_MENUS.items(), 1)
            ))
        finally:
            await browser.close()


def review_summary(results, capture_holds, rows, validated):
    retailers = {result["id"]: result["retailer"] for result in results}
    rows_by_id = {row["observation_id"]: row for row in rows}
    accepted = Counter(row["retailer_id"] for row in validated["accepted"])
    held = Counter()
    reasons = defaultdict(Counter)
    for item in capture_holds:
        reasons[item["retailer_id"]][("Capture", item["reason"])] += 1
    for item in validated["holds"]:
        for observation_id in item.get("observation_ids", [item.get("observation_id")]):
            row = rows_by_id[observation_id]
            retailer_id = row["retailer_id"]
            held[retailer_id] += 1
            for reason in row["identity_reasons"] or item["reasons"]:
                reasons[retailer_id][("Validation", reason)] += 1
    lines = [
        "", "| Retailer | Validated offers | Held observations |",
        "| --- | ---: | ---: |",
    ]
    for retailer_id, name in retailers.items():
        lines.append(f"| {name} | {accepted[retailer_id]} | {held[retailer_id]} |")
    lines.extend([
        "", "An observation may have more than one hold reason.", "",
        "| Retailer | Stage | Hold reason | Count |",
        "| --- | --- | --- | ---: |",
    ])
    for retailer_id, name in retailers.items():
        for (stage, reason), count in reasons[retailer_id].most_common():
            lines.append(f"| {name} | {stage} | {reason.replace('_', ' ')} | {count} |")
    return lines


def write_holds(path, results, captured, capture_holds, rows, validated):
    retailers = {result["id"]: result for result in results}
    evidence = {item["observation_id"]: item for item in captured}
    normalized = {row["observation_id"]: row for row in rows}

    def cell(value):
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value

    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Stage", "Retailer", "Retailer ID", "Observation ID", "Observed at",
                         "Raw product title", "Reported brand", "Canonical brand",
                         "Canonical strain", "Category", "Package weight g", "Pack count",
                         "Source price", "Product URL", "Menu URL", "Identity hold reasons",
                         "Validation hold reasons", "Raw card"])

        def write(values):
            writer.writerow([cell(value) for value in values])

        for hold in capture_holds:
            retailer_id = hold["retailer_id"]
            result = retailers[retailer_id]
            card = result["products"][hold["card_index"]] if "card_index" in hold else hold
            write(["Capture", result["retailer"], retailer_id, hold.get("observation_id"), result["scanned_at"],
                   card.get("raw_product_title"), card.get("brand_candidate"),
                   "", "", "", "", "", "", hold.get("source_url"), result["menu_url"],
                   "", hold["reason"], hold.get("raw_card")])
        for hold in validated["holds"]:
            for observation_id in hold.get("observation_ids", [hold.get("observation_id")]):
                row, item = normalized[observation_id], evidence[observation_id]
                retailer_id = row["retailer_id"]
                write(["Validation", retailers[retailer_id]["retailer"], retailer_id,
                       observation_id, row["observed_at"], row["raw_title"],
                       item.get("source_brand_text"), row["brand"], row["strain"],
                       row["category"], row["package_g"], row["pack_count"], row["price"],
                       row["product_url"], row["source_url"],
                       " | ".join(row["identity_reasons"]), " | ".join(hold["reasons"]),
                       (item.get("source_metadata") or {}).get("card_text")])


def summarize(results, master, holds_csv=None):
    captured, capture_holds = capture_rendered({"results": results})
    rows, validated = [], {"holds": []}
    lines = [
        "## Scanner V2 live pilot", "",
        "| Retailer | Menu result | Raw cards |",
        "| --- | --- | ---: |",
    ]
    for result in results:
        name, statuses, cards = result["retailer"], result["statuses"], result["products"]
        lines.append(f"| {name} | {', '.join(statuses)} | {len(cards)} |")
    lines.extend([
        "", f"V2 observations: {len(captured)}. Capture holds: {len(capture_holds)}.",
    ])
    if master and captured:
        brands = master["brands"]
        rows = reconcile(captured, master["strain_master"], brands, approved_brands=brands)
        validated = validate(rows)
        categories = Counter(row["category"] for row in validated["accepted"])
        lines.extend([
            "", f"Validated offers: {len(validated['accepted'])}. "
            f"Validation holds: {len(validated['holds'])}. "
            f"Duplicates: {len(validated['duplicates_suppressed'])}.",
            "",
            "Accepted by format: " + (", ".join(
                f"{name} {count}" for name, count in sorted(categories.items())
            ) or "none") + ".",
        ])
        lines.extend(review_summary(results, capture_holds, rows, validated))
    elif not master:
        lines.extend(["", "Master workbook snapshot unavailable. Identity validation was skipped."])
    if holds_csv:
        write_holds(holds_csv, results, captured, capture_holds, rows, validated)
    return "\n".join(lines) + "\n", bool(captured)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master-snapshot", type=Path)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--holds-csv", type=Path)
    args = parser.parse_args()
    master = load_snapshot(args.master_snapshot) if args.master_snapshot else None
    if master and not PILOT_MENUS.keys() <= {row["name"] for row in master["retailers"]}:
        raise SystemExit("One or more pilot retailers are missing from the master snapshot")
    results = asyncio.run(capture_pilot(master))
    summary, has_observations = summarize(results, master, args.holds_csv)
    with args.summary.open("a", encoding="utf-8") as output:
        output.write(summary)
    print(summary)
    if not has_observations:
        raise SystemExit("No live V2 observations captured")


if __name__ == "__main__":
    main()
