"""
Recon tabletka.uz, uzum.uz, doridarmon.uz for medical device data.
"""

import asyncio
import json
import sys
import re
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')

RESULTS = {}


async def explore_site(browser, site_name, urls, search_terms):
    """Explore a site: load pages, capture API calls, extract product data."""
    print(f"\n{'='*80}")
    print(f"EXPLORING: {site_name}")
    print(f"{'='*80}")

    site_results = {"api_calls": [], "products": [], "errors": []}

    context = await browser.new_context(
        locale="ru-RU",
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        ignore_https_errors=True,
    )
    page = await context.new_page()

    async def on_response(response):
        url = response.url
        skip = [".js", ".css", ".png", ".jpg", ".svg", ".woff", ".ico",
                "google", "yandex", "facebook", "_next/static", "fonts."]
        if any(s in url for s in skip):
            return
        try:
            if response.status == 200:
                ct = response.headers.get("content-type", "")
                if "json" in ct:
                    body = await response.text()
                    entry = {
                        "url": url,
                        "method": response.request.method,
                        "body_preview": body[:2000],
                        "length": len(body),
                    }
                    if response.request.post_data:
                        entry["post_data"] = response.request.post_data[:500]
                    site_results["api_calls"].append(entry)
                    print(f"  API: [{response.request.method}] {url[:100]} ({len(body)} chars)")
        except Exception:
            pass

    page.on("response", on_response)

    # Try loading each URL
    for url in urls:
        print(f"\n  Loading: {url}")
        try:
            resp = await page.goto(url, wait_until="networkidle", timeout=30000)
            print(f"  Status: {resp.status if resp else 'no response'}")
            await page.wait_for_timeout(3000)

            # Get page text
            text = await page.inner_text("body")
            lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 3]

            # Look for product-like content
            product_lines = []
            for line in lines:
                lower = line.lower()
                if any(kw in lower for kw in ["тонометр", "omron", "microlife", "prolife",
                    "небулайзер", "термометр", "b.well", "beurer", "uzs", "сум", "цена"]):
                    product_lines.append(line[:150])

            if product_lines:
                print(f"  Product lines ({len(product_lines)}):")
                for pl in product_lines[:15]:
                    print(f"    {pl}")
            else:
                # Show general content
                print(f"  Content ({len(lines)} lines):")
                for line in lines[:20]:
                    print(f"    {line[:100]}")

            site_results["products"].extend(product_lines)

        except Exception as e:
            err = str(e)[:200]
            print(f"  Error: {err}")
            site_results["errors"].append({"url": url, "error": err})

    # Try search
    for term in search_terms:
        print(f"\n  Searching: '{term}'")
        try:
            # Try common search URL patterns
            search_urls = [
                f"{urls[0].rstrip('/')}/search?q={term}",
                f"{urls[0].rstrip('/')}/search?query={term}",
                f"{urls[0].rstrip('/')}/ru/search?query={term}",
            ]
            for surl in search_urls:
                try:
                    resp = await page.goto(surl, wait_until="networkidle", timeout=20000)
                    if resp and resp.status == 200:
                        await page.wait_for_timeout(3000)
                        text = await page.inner_text("body")
                        lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 5]
                        product_count = sum(1 for l in lines if any(
                            kw in l.lower() for kw in ["тонометр", "omron", "prolife", "uzs", "сум"]))
                        if product_count > 0 or len(lines) > 10:
                            print(f"    URL works: {surl}")
                            print(f"    Lines: {len(lines)}, product-like: {product_count}")
                            for line in lines[:10]:
                                print(f"      {line[:120]}")
                            break
                except Exception:
                    continue
        except Exception as e:
            print(f"    Error: {str(e)[:100]}")

    await context.close()
    RESULTS[site_name] = site_results


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # === UZUM.UZ ===
        await explore_site(browser, "Uzum.uz", [
            "https://uzum.uz/ru",
            "https://uzum.uz/ru/category/tonometry-i-stetoskopy-8575",
            "https://uzum.uz/ru/category/nebulajzery-i-ingalyatory-8576",
            "https://uzum.uz/ru/category/termometry-8577",
        ], ["тонометр omron", "prolife тонометр"])

        # === TABLETKA.UZ ===
        await explore_site(browser, "Tabletka.uz", [
            "https://tabletka.uz",
            "https://www.tabletka.uz",
            "https://tabletka.uz/ru",
        ], ["тонометр"])

        # === DORIDARMON.UZ ===
        await explore_site(browser, "Doridarmon.uz", [
            "https://doridarmon.uz",
            "https://www.doridarmon.uz",
            "http://doridarmon.uz",
        ], ["тонометр"])

        # === BONUS: MYDORI.UZ ===
        await explore_site(browser, "MyDori.uz", [
            "https://mydori.uz",
            "https://mydori.uz/ru",
        ], ["тонометр"])

        await browser.close()

    # Summary
    print(f"\n\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    for site, data in RESULTS.items():
        print(f"\n{site}:")
        print(f"  API calls captured: {len(data['api_calls'])}")
        print(f"  Product lines found: {len(data['products'])}")
        print(f"  Errors: {len(data['errors'])}")
        if data['api_calls']:
            print(f"  Key APIs:")
            for api in data['api_calls'][:5]:
                print(f"    [{api['method']}] {api['url'][:100]}")

    with open("recon_output/other_sites_recon.json", "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, indent=2, ensure_ascii=False, default=str)


if __name__ == "__main__":
    asyncio.run(main())
