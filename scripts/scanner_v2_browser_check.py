"""Exercise shared menu capture with browser-rendered fixtures."""
import asyncio

from playwright.async_api import async_playwright

from scanner_v2_pilot import read_menu


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


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            await asyncio.gather(*(check(browser, html, expected) for html, expected in CASES))
        finally:
            await browser.close()
    print(f"{len(CASES)} menu capture browser checks passed")


if __name__ == "__main__":
    asyncio.run(main())
