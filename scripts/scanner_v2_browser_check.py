"""Exercise shared menu capture with browser-rendered fixtures."""
import asyncio

from playwright.async_api import async_playwright

from scanner_v2_pilot import read_menu
from scanner_v2_capture import capture_rendered
from scanner_v2_release_audit import capture_store


URL = "https://menu.example/"
PRODUCT = "<article><h2>Example Flower</h2>$25.00 priced listing</article>"
PROMPT = "<p>Are you 21 or older?</p>"
REVEAL = """onclick="this.parentElement.remove(); document.querySelector('#menu').hidden=false" """
HIDDEN_MENU = f'<div id="menu" hidden>{PRODUCT}</div>'

CASES = [
    (f"<footer>You must be 21 or older.</footer>{PRODUCT}", "Cards captured"),
    (f'<div role="dialog">{PROMPT}<button {REVEAL}>I am 21+</button></div>{HIDDEN_MENU}',
     "Cards captured after age prompt"),
    (f'<div role="dialog">{PROMPT}<button {REVEAL}>Yes</button><button>No</button></div>{HIDDEN_MENU}',
     "Cards captured after age prompt"),
    (f'<form><input type="date"><div>{PROMPT}<button {REVEAL}>I am 21+</button></div></form>{HIDDEN_MENU}',
     "Age gate"),
    (f"<div>{PROMPT}<button {REVEAL}>Continue</button></div>{HIDDEN_MENU}", "Age gate"),
    (f"<div><p>Verify that you are human.</p>{PROMPT}<button {REVEAL}>I am 21+</button></div>{HIDDEN_MENU}",
     "Access limited"),
]


async def check(browser, html, expected):
    page = await browser.new_page()
    try:
        await page.route(URL, lambda route: route.fulfill(content_type="text/html", body=f"<body>{html}</body>"))
        status, cards = await read_menu(page, URL)
        if status != expected or bool(cards) != expected.startswith("Cards captured"):
            raise AssertionError(f"Expected {expected!r}, received {status!r} with {len(cards)} cards")
    finally:
        await page.close()


async def check_fallback(browser):
    fallback = "https://thcminnesota.com/dispensary/example"
    markup = """
    <script type="application/ld+json">
      {"@type":"ItemList","itemListElement":[{"item":{"@type":"Product","name":"Example Flower",
        "category":"Flower","url":"/products/example"}}]}
    </script>
    <table><thead><tr><th>Product</th><th>Brand</th><th>Price</th><th>Category</th>
      <th>Type</th><th>THC</th><th>Size</th></tr></thead><tbody>
      <tr><td>Example Flower</td><td>Example Brand</td><td>$25.00*</td><td>Flower</td>
        <td>Hybrid</td><td>20%</td><td>3.5g</td></tr>
    </tbody></table>
    """
    context = await browser.new_context()
    try:
        await context.route(URL, lambda route: route.fulfill(status=403))
        await context.route(fallback, lambda route: route.fulfill(content_type="text/html", body=markup))
        result = await capture_store(context, {
            "id": "example", "name": "Example Store", "menu_url": URL,
            "audit_sources": [(URL, False), (fallback, True)],
        })
        evidence, holds = capture_rendered({"results": [result]})
        assert result["attempted_menu_urls"] == [URL, fallback]
        assert result["statuses"] == ["HTTP 403", "Cards captured", "Cards captured from fallback menu"]
        assert not holds and len(evidence) == 1
        assert evidence[0]["source_kind"] == "secondary_research" and evidence[0]["price"] == 25
    finally:
        await context.close()


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            await asyncio.gather(check_fallback(browser), *(check(browser, html, expected) for html, expected in CASES))
        finally:
            await browser.close()
    print(f"{len(CASES) + 1} menu capture browser checks passed")


if __name__ == "__main__":
    asyncio.run(main())
