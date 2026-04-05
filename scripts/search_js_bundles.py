"""
Search JS bundles for API endpoints, search logic, and medicine ID mapping.
Also try the Telegram bot API and alternate search approaches.
"""

import asyncio
import json
import sys
import re
import httpx
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')


async def search_js_bundles():
    """Download and search JS bundles for API endpoints and search logic."""
    print("=" * 80)
    print("PHASE 1: Searching JS bundles")
    print("=" * 80)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Collect JS URLs
        js_urls = []

        async def on_response(response):
            url = response.url
            if "_next" in url and url.endswith(".js") and response.status == 200:
                js_urls.append(url)

        page.on("response", on_response)

        await page.goto("https://arzonapteka.uz/ru", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        # Also load a search page to get its JS
        await page.goto("https://arzonapteka.uz/ru/search?medicine=10854&region=-3",
                        wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        await browser.close()

    print(f"Found {len(js_urls)} JS bundles")

    # Download and search each bundle
    keywords = [
        "api.arzonapteka", "arzonapteka.name",
        "autocomplete", "suggest", "search",
        "medicine_id", "good_id", "medicineId",
        "/api/v", "api_key", "apiKey", "api-key",
        "34319a8fb16208800380e63955a4a49c",
    ]

    client = httpx.Client(timeout=30)
    interesting_chunks = []

    for url in js_urls:
        try:
            resp = client.get(url)
            content = resp.text

            for kw in keywords:
                if kw.lower() in content.lower():
                    # Find context around the keyword
                    idx = content.lower().index(kw.lower())
                    context = content[max(0, idx-100):idx+200]
                    interesting_chunks.append({
                        "url": url.split("/")[-1],
                        "keyword": kw,
                        "context": context,
                    })

        except Exception as e:
            pass

    print(f"\nFound {len(interesting_chunks)} keyword matches:")
    seen = set()
    for chunk in interesting_chunks:
        key = f"{chunk['url']}:{chunk['keyword']}"
        if key not in seen:
            seen.add(key)
            print(f"\n  [{chunk['url']}] keyword='{chunk['keyword']}'")
            print(f"  Context: ...{chunk['context'][:300]}...")

    # Save for analysis
    with open("recon_output/js_bundle_matches.json", "w", encoding="utf-8") as f:
        json.dump(interesting_chunks, f, indent=2, ensure_ascii=False)


def try_alternate_search():
    """Try alternate approaches to find medicine IDs."""
    print("\n\n" + "=" * 80)
    print("PHASE 2: Alternate search approaches")
    print("=" * 80)

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://arzonapteka.uz",
        "Referer": "https://arzonapteka.uz/",
        "api-key": "34319a8fb16208800380e63955a4a49c",
    }

    # Try different field names for text search
    print("\nTrying different request formats...")
    attempts = [
        {"country_code": "1", "platform": "web", "region": "-3",
         "search": ["тонометр"], "user": "test", "query": "тонометр"},
        {"country_code": "1", "platform": "web", "region": "-3",
         "search": ["тонометр"], "user": "test", "type": "text"},
        {"country_code": "1", "platform": "web", "region": "-3",
         "search_text": "тонометр", "user": "test"},
        {"country_code": "1", "platform": "web", "region": "1726",
         "search": ["тонометр"], "user": "test"},
        {"country_code": "1", "platform": "web", "region": "1726",
         "search": [], "user": "test", "query": "тонометр"},
        # Try numeric region (Tashkent)
        {"country_code": "1", "platform": "web", "region": "1726",
         "search": ["10854"], "user": "test"},
    ]

    for i, body in enumerate(attempts):
        print(f"\n  Attempt {i+1}: {json.dumps(body, ensure_ascii=False)[:200]}")
        try:
            resp = httpx.post(
                "https://api.arzonapteka.name/api/v4/ru/search",
                json=body, headers=headers, timeout=10
            )
            result = resp.json()
            ok = result.get("ok")
            if ok:
                ds = result["result"].get("drugstores", [])
                print(f"    OK! {len(ds)} drugstores")
                if ds:
                    for drug in ds[0].get("drugs", [])[:3]:
                        print(f"      - {drug['good_name']}")
            else:
                print(f"    Error: {result.get('error')}")
        except Exception as e:
            print(f"    Failed: {e}")

    # Try the regions endpoint with different params
    print("\n\nTrying regions endpoint...")
    region_attempts = [
        {"country_code": "1"},
        {"country_code": "1", "platform": "web"},
        {},
    ]

    for body in region_attempts:
        print(f"\n  Body: {body}")
        try:
            resp = httpx.post(
                "https://api.arzonapteka.name/api/v4/ru/regions",
                json=body, headers=headers, timeout=10
            )
            result = resp.json()
            print(f"    {json.dumps(result, ensure_ascii=False)[:500]}")
        except Exception as e:
            print(f"    Failed: {e}")


async def main():
    await search_js_bundles()
    try_alternate_search()


if __name__ == "__main__":
    asyncio.run(main())
