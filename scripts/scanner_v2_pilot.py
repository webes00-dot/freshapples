#!/usr/bin/env python3
"""Capture and review public menu evidence from the three pilot retailers."""
import argparse
import asyncio
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

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
    r"verify (?:your )?age|are you (?:over |at least )?21|enter your date of birth",
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
  return Array.from(document.querySelectorAll(selector), element => ({
    text: text(element),
    href: element.closest('a[href]')?.href || element.querySelector('a[href]')?.href,
    title: text(element.querySelector('[data-testid*="product-name"],[class*="product-name"],[class*="productName"],h2,h3,h4')),
    brand: text(element.querySelector('[data-testid*="brand"],[class*="product-brand"],[class*="productBrand"]')),
    productId: element.getAttribute('data-product-id') || '',
  })).filter(card => card.text.length >= 12 && card.text.length <= 750 && card.text.includes('$'));
}"""


def rendered_products(cards, menu_url):
    products = []
    for card in cards:
        prices = [float(price.replace(",", "")) for price in PRICE.findall(card["text"])]
        if prices:
            products.append({
                "card_text": card["text"], "price_candidates": prices,
                "product_url": card.get("href"), "source_menu_url": menu_url,
                "raw_product_title": card.get("title"),
                "brand_candidate": card.get("brand"),
                "source_product_id": card.get("productId"),
            })
    return products


async def read_menu(page, url):
    from playwright.async_api import Error as BrowserError

    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        if response and response.status >= 400:
            return f"HTTP {response.status}", []
        for attempt in range(6):
            rendered = []
            for frame in page.frames:
                try:
                    body = await frame.locator("body").inner_text(timeout=2_000)
                    if AGE_GATE.search(body[:2500]):
                        return "Age gate", []
                    if ACCESS_LIMITED.search(body[:1200]):
                        return "Access limited", []
                    rendered.extend(await frame.evaluate(READ_CARDS))
                except BrowserError:
                    if frame == page.main_frame and attempt == 5:
                        return "Page unavailable", []
            products = rendered_products(rendered, url)
            if products:
                return "Cards captured", products
            if attempt < 5:
                await asyncio.sleep(1)
    except BrowserError:
        return "Page unavailable", []
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
            if status in {"Age gate", "Access limited", "HTTP 401", "HTTP 403", "HTTP 429"}:
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


def summarize(results, master):
    captured, capture_holds = capture_rendered({"results": results})
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
        validated = validate(reconcile(captured, master["strain_master"], brands, approved_brands=brands))
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
    elif not master:
        lines.extend(["", "Master workbook snapshot unavailable. Identity validation was skipped."])
    return "\n".join(lines) + "\n", bool(captured)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master-snapshot", type=Path)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    master = load_snapshot(args.master_snapshot) if args.master_snapshot else None
    if master and not PILOT_MENUS.keys() <= {row["name"] for row in master["retailers"]}:
        raise SystemExit("One or more pilot retailers are missing from the master snapshot")
    results = asyncio.run(capture_pilot(master))
    summary, has_observations = summarize(results, master)
    with args.summary.open("a", encoding="utf-8") as output:
        output.write(summary)
    print(summary)
    if not has_observations:
        raise SystemExit("No live V2 observations captured")


if __name__ == "__main__":
    main()
