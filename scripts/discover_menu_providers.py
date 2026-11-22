#!/usr/bin/env python3
"""Discover retailer menu platforms and public catalog endpoints.

Uses the existing retailer targets. Does not guess dispensary IDs or bypass
age gates. Results are evidence for reusable provider-specific extractors.
Usage: python scripts/discover_menu_providers.py [retailer substring]
"""
import asyncio
import datetime
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

TARGETS = Path("data/retailer_menu_scan_targets.json")
OUTPUT = Path("data/menu_provider_discovery.json")
PATTERNS = {
    "dutchie": re.compile(r"dutchie\.com|dutchie[-_]embed|dutchie[-_]menu", re.I),
    "jane": re.compile(r"iheartjane\.com|jane\.com|jane[-_]embed|jane[-_]menu", re.I),
    "dispensary_shop": re.compile(r"dispensary\.shop", re.I),
    "tymber": re.compile(r"tymber\.io|tymber[-_]menu", re.I),
    "leafly": re.compile(r"leafly\.com", re.I),
    "weedmaps": re.compile(r"weedmaps\.com", re.I),
    "blaze": re.compile(r"blaze\.me|blaze[-_]menu", re.I),
    "meadow": re.compile(r"getmeadow\.com|meadow[-_]menu", re.I),
}
MENU_HINT = re.compile(r"menu|shop|product|catalog|dispensary|graphql|iframe|embed", re.I)
MAX_EVIDENCE = 35

def identify(evidence):
    joined = "\n".join(evidence)
    return [name for name, pattern in PATTERNS.items() if pattern.search(joined)]

async def inspect(browser, target, semaphore):
    async with semaphore:
        stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        result = {"id": target["id"], "retailer": target["name"],
                  "url": target["url"], "scanned_at": stamp,
                  "providers": [], "evidence_urls": [], "status": "error"}
        context = await browser.new_context(
            viewport={"width": 1365, "height": 850}, locale="en-US")
        page = await context.new_page()
        evidence = set([target["url"]])
        def on_request(request):
            url = request.url
            if MENU_HINT.search(url) or any(p.search(url) for p in PATTERNS.values()):
                evidence.add(url.split("?")[0][:300])
        context.on("request", on_request)
        try:
            response = await page.goto(target["url"], wait_until="domcontentloaded",
                                       timeout=25000)
            result["http_status"] = response.status if response else None
            await page.wait_for_timeout(3500)
            evidence.add(page.url)
            for frame in page.frames:
                if frame.url and frame.url != "about:blank":
                    evidence.add(frame.url.split("?")[0][:300])
            # Includes scripts and anchors not yet requested by the browser.
            extra = await page.evaluate("""() => Array.from(
                document.querySelectorAll('a[href], iframe[src], script[src], [data-src]'))
                .map(el => el.href || el.src || el.getAttribute('data-src'))
                .filter(Boolean).slice(0, 500)""")
            for url in extra:
                if MENU_HINT.search(url) or any(p.search(url) for p in PATTERNS.values()):
                    evidence.add(url.split("?")[0][:300])
            # Inspect page markup for providers that load through inline scripts.
            html = await page.content()
            result["providers"] = identify(list(evidence) + [html[:300000]])
            result["evidence_urls"] = sorted(
                x for x in evidence if MENU_HINT.search(x)
                or any(p.search(x) for p in PATTERNS.values())
            )[:MAX_EVIDENCE]
            result["status"] = "provider_identified" if result["providers"] else "unknown"
            result["final_url"] = page.url
        except Exception as exc:
            result["error"] = str(exc)[:240]
            result["providers"] = identify(list(evidence))
            result["evidence_urls"] = sorted(evidence)[:MAX_EVIDENCE]
        finally:
            await context.close()
        return result

async def main():
    targets = json.loads(TARGETS.read_text())
    if len(sys.argv) > 1:
        needle = " ".join(sys.argv[1:]).casefold()
        targets = [t for t in targets if needle in t["name"].casefold()]
    from playwright.async_api import async_playwright
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        sem = asyncio.Semaphore(4)
        results = await asyncio.gather(
            *(inspect(browser, target, sem) for target in targets))
        await browser.close()
    previous = {}
    if OUTPUT.exists():
        try:
            previous = {r["id"]: r for r in json.loads(OUTPUT.read_text())["results"]}
        except (ValueError, KeyError, TypeError):
            pass
    for result in results:
        old = previous.get(result["id"])
        if old and old.get("providers") and not result["providers"]:
            result["last_successful_providers"] = old["providers"]
            result["last_successful_evidence_urls"] = old.get("evidence_urls", [])
        previous[result["id"]] = result
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "total": len(previous), "results": list(previous.values())
    }, indent=2) + "\n")
    counts = {}
    for item in results:
        for provider in item["providers"]:
            counts[provider] = counts.get(provider, 0) + 1
    print(json.dumps({"scanned": len(results), "providers": counts,
                      "unknown": sum(not x["providers"] for x in results),
                      "errors": sum(x["status"] == "error" for x in results)}))

if __name__ == "__main__":
    asyncio.run(main())
