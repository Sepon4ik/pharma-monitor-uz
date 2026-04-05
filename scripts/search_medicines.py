"""
Explore the /search-medicines endpoint discovered from the search flow.
URL pattern: /en/search-medicines?q=prolife
"""

import asyncio
import json
import sys
import re
import hashlib
import httpx
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "https://api.arzonapteka.name"
SECRET = "Nx3WWr"


def make_api_key(endpoint):
    raw = f"{BASE_URL}{endpoint}{SECRET}"
    return hashlib.md5(raw.encode()).hexdigest()


async def explore_search_medicines():
    all_products = {}
    all_api_calls = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="en-US",
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        async def on_response(response):
            url = response.url
            # Skip static
            skip = [".js", ".css", ".png", ".jpg", ".svg", ".woff", ".ico",
                    "google", "yandex", "facebook", "_next/static", "fonts."]
            if any(s in url for s in skip):
                return

            try:
                status = response.status
                method = response.request.method
                ct = response.headers.get("content-type", "")

                if status == 200 and ("json" in ct or "text" in ct or "component" in ct):
                    body = await response.text()
                    entry = {
                        "url": url,
                        "method": method,
                        "status": status,
                    }
                    if response.request.post_data:
                        entry["post_data"] = response.request.post_data[:1000]

                    # Look for medicine/product data in response
                    if "api.arzonapteka" in url:
                        entry["body"] = body[:5000]
                        print(f"\n  *** API: [{method}] {url}")
                        if entry.get("post_data"):
                            print(f"      POST: {entry['post_data'][:300]}")
                        print(f"      Response: {body[:500]}")

                    # Look for search-medicines RSC data
                    if "search-medicines" in url or "_rsc" in url:
                        # Check for product data in RSC stream
                        if any(kw in body.lower() for kw in ["prolife", "omron", "microlife", "тонометр", "good_id", "medicine"]):
                            entry["body"] = body[:10000]
                            print(f"\n  *** RSC with product data: [{method}] {url}")
                            # Extract product info
                            # Look for good_id patterns
                            ids_found = re.findall(r'"good_id"[:\s]*"?(\d+)"?', body)
                            names_found = re.findall(r'"good_name"[:\s]*"([^"]+)"', body)
                            if ids_found:
                                print(f"      good_ids: {ids_found}")
                            if names_found:
                                print(f"      names: {names_found[:5]}")
                            # Also look for IDs in different format
                            ids2 = re.findall(r'"id"[:\s]*(\d{4,6})', body)
                            if ids2:
                                print(f"      numeric ids: {ids2[:20]}")

                    all_api_calls.append(entry)
            except Exception:
                pass

        page.on("response", on_response)

        # Search for different brands
        queries = ["prolife", "omron", "microlife", "тонометр", "небулайзер"]

        for query in queries:
            print(f"\n{'='*60}")
            print(f"Searching: '{query}'")
            print(f"{'='*60}")

            url = f"https://arzonapteka.uz/en/search-medicines?q={query}"
            print(f"  Loading: {url}")
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(5000)

            # Get page content
            try:
                text = await page.inner_text("body")
                lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 3]
                print(f"\n  Page content ({len(lines)} lines):")
                for line in lines[:30]:
                    print(f"    {line[:120]}")

                # Look for product cards
                products_on_page = await page.evaluate("""
                    () => {
                        const results = [];
                        // Look for links with medicine/choose-pharmacy
                        const links = document.querySelectorAll('a');
                        for (const link of links) {
                            const href = link.getAttribute('href') || '';
                            const text = link.textContent.trim();
                            if ((href.includes('medicine') || href.includes('choose-pharmacy') || href.includes('search?m'))
                                && text.length > 5 && text.length < 500) {
                                results.push({
                                    text: text.substring(0, 200),
                                    href: href,
                                });
                            }
                        }

                        // Also look for buttons with "Add to cart"
                        const buttons = document.querySelectorAll('button');
                        for (const btn of buttons) {
                            const text = btn.textContent.trim();
                            if (text.includes('Add to cart') || text.includes('корзин')) {
                                const parent = btn.closest('[class*="card"], [class*="product"], [class*="item"], article, div');
                                if (parent) {
                                    results.push({
                                        text: parent.textContent.trim().substring(0, 300),
                                        href: 'card-element',
                                    });
                                }
                            }
                        }

                        return results.slice(0, 30);
                    }
                """)

                if products_on_page:
                    print(f"\n  Product elements ({len(products_on_page)}):")
                    for prod in products_on_page:
                        print(f"    {prod['text'][:100]} -> {prod['href']}")
                        # Extract medicine IDs
                        ids = re.findall(r'medicine=(\d+)', prod['href'])
                        if ids:
                            for mid in ids:
                                all_products[mid] = prod['text'][:200]
                            print(f"      >>> IDs: {ids}")

            except Exception as e:
                print(f"  Error: {str(e)[:100]}")

            # Also check the page source for embedded data
            try:
                html = await page.content()
                # Look for medicine IDs in script tags or data attributes
                script_ids = re.findall(r'medicine[=:](\d+)', html)
                data_ids = re.findall(r'good_id["\s:]+(\d+)', html)
                if script_ids:
                    print(f"\n  Medicine IDs in HTML: {list(set(script_ids))[:20]}")
                if data_ids:
                    print(f"  good_ids in HTML: {list(set(data_ids))[:20]}")
            except Exception:
                pass

        await browser.close()

    # Save results
    print(f"\n\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"Products found: {len(all_products)}")
    for mid, name in all_products.items():
        print(f"  [{mid}] {name[:100]}")

    with open("recon_output/search_medicines_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "products": all_products,
            "api_calls": [c for c in all_api_calls if c.get("body")],
        }, f, indent=2, ensure_ascii=False)

    # If we found IDs, verify them via API
    if all_products:
        print(f"\n\nVerifying found IDs via API...")
        endpoint = "/api/v4/en/search"
        api_key = make_api_key(endpoint)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
            "Origin": "https://arzonapteka.uz",
            "Api-Key": api_key,
        }
        ids = list(all_products.keys())
        data = {
            "country_code": "1", "platform": "web",
            "region": "-3", "search": ids, "user": "verify"
        }
        resp = httpx.post(f"{BASE_URL}{endpoint}", json=data, headers=headers, timeout=30)
        result = resp.json()
        if result.get("ok"):
            ds = result["result"]["drugstores"]
            print(f"  API returned {len(ds)} pharmacies")
            seen = set()
            for d in ds[:5]:
                for drug in d.get("drugs", []):
                    gid = drug["good_id"]
                    if gid not in seen:
                        seen.add(gid)
                        print(f"  [{gid}] {drug['good_name']} | {drug.get('vendor_name','')} | {drug['price']} UZS")


if __name__ == "__main__":
    asyncio.run(explore_search_medicines())
