"""
Find medicine IDs for OMRON, Prolife, Microlife products.
The text->ID mapping happens on the frontend. We need to:
1. Use Playwright to type in search and capture the autocomplete suggestions
2. OR parse the sitemap for all IDs and check them against the API
"""

import asyncio
import json
import sys
import httpx
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "https://api.arzonapteka.name/api/v4"
API_KEY = "34319a8fb16208800380e63955a4a49c"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "https://arzonapteka.uz",
    "Referer": "https://arzonapteka.uz/",
    "api-key": API_KEY,
}


async def find_ids_via_playwright():
    """Use Playwright to capture medicine IDs from the search autocomplete."""
    found_products = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="ru-RU",
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        # Capture API calls to find how search maps text to IDs
        async def on_response(response):
            url = response.url
            if "api.arzonapteka" in url and response.status == 200:
                try:
                    req = response.request
                    if req.post_data:
                        body = json.loads(req.post_data)
                        if body.get("search"):
                            print(f"  API search called with: {body['search']}")
                except Exception:
                    pass

        page.on("response", on_response)

        search_terms = [
            "omron", "OMRON",
            "microlife", "Microlife",
            "prolife", "Prolife",
            "тонометр", "небулайзер", "термометр",
            "тонометр omron",
        ]

        for term in search_terms:
            print(f"\n{'='*60}")
            print(f"Searching: '{term}'")
            print(f"{'='*60}")

            await page.goto("https://arzonapteka.uz/ru", wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(2000)

            # Click on search area to make input visible
            try:
                # Try clicking the search container/button first
                search_btn = page.locator('button:has-text("Найти"), [class*="search"], label:has-text("поиск")')
                if await search_btn.count() > 0:
                    await search_btn.first.click()
                    await page.wait_for_timeout(1000)
            except Exception:
                pass

            # Now try the input
            search_input = page.locator('input[type="search"], input[placeholder*="Найти"], input[placeholder*="поиск" i], input[placeholder*="Find" i]')
            try:
                # Try to make it visible
                await page.evaluate("""
                    const inputs = document.querySelectorAll('input[type="search"]');
                    inputs.forEach(input => {
                        input.style.display = 'block';
                        input.style.visibility = 'visible';
                        input.style.opacity = '1';
                        const parent = input.closest('[style]');
                        if (parent) {
                            parent.style.display = 'block';
                            parent.style.visibility = 'visible';
                        }
                    });
                """)
                await page.wait_for_timeout(500)

                visible = await search_input.first.is_visible()
                print(f"  Search input visible: {visible}")

                if not visible:
                    # Force focus
                    await search_input.first.evaluate("el => el.focus()")
                    await page.wait_for_timeout(500)

                await search_input.first.fill(term)
                await page.wait_for_timeout(2000)

                # Look for suggestions/results
                suggestions = await page.evaluate("""
                    () => {
                        const results = [];
                        // Look for any links that appeared
                        const links = document.querySelectorAll('a[href*="medicine"], a[href*="search?m"], a[href*="choose-pharmacy"]');
                        links.forEach(link => {
                            results.push({
                                text: link.textContent.trim(),
                                href: link.getAttribute('href'),
                            });
                        });
                        // Also look for list items
                        const items = document.querySelectorAll('[class*="suggest"] *, [class*="dropdown"] li, [class*="search-result"] *, [role="option"]');
                        items.forEach(item => {
                            if (item.textContent.trim().length > 3) {
                                results.push({
                                    text: item.textContent.trim().substring(0, 200),
                                    href: item.getAttribute('href') || '',
                                });
                            }
                        });
                        return results;
                    }
                """)

                if suggestions:
                    print(f"  Found {len(suggestions)} suggestions:")
                    for s in suggestions[:20]:
                        print(f"    {s['text'][:80]} -> {s['href']}")
                        # Extract medicine ID from href
                        if s['href'] and 'medicine=' in s['href']:
                            import re
                            m = re.search(r'medicine=(\d+)', s['href'])
                            if m:
                                found_products[m.group(1)] = s['text']
                else:
                    print("  No suggestions found in DOM")

                # Also try pressing Enter and seeing where it goes
                await search_input.first.press("Enter")
                await page.wait_for_timeout(5000)
                print(f"  URL after Enter: {page.url}")

                # Check if URL has medicine parameter
                if "medicine=" in page.url or "choose-pharmacy" in page.url:
                    import re
                    m = re.search(r'[?&]m(?:edicine)?=(\d+)', page.url)
                    if m:
                        print(f"  Found medicine ID in URL: {m.group(1)}")

                # Get page content to see results
                try:
                    text = await page.inner_text("body")
                    lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 5]
                    # Filter for product-like lines
                    for line in lines:
                        lower = line.lower()
                        if any(brand in lower for brand in ["omron", "microlife", "prolife", "тонометр", "небулайзер"]):
                            print(f"  >> {line[:120]}")
                except Exception:
                    pass

            except Exception as e:
                print(f"  Error: {str(e)[:200]}")

        await browser.close()

    return found_products


async def main():
    print("PHASE 1: Finding medicine IDs via Playwright autocomplete")
    print("="*80)
    products = await find_ids_via_playwright()

    if products:
        print(f"\n\nFOUND PRODUCTS:")
        for mid, name in products.items():
            print(f"  ID {mid}: {name}")

        # Save
        with open("recon_output/found_medicine_ids.json", "w", encoding="utf-8") as f:
            json.dump(products, f, indent=2, ensure_ascii=False)
    else:
        print("\nNo products found via autocomplete. The search might work differently.")
        print("Will need to scan sitemap IDs or find another approach.")


if __name__ == "__main__":
    asyncio.run(main())
