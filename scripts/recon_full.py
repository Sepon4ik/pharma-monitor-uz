"""
Full API recon: capture exact headers/cookies that make the API work,
find the autocomplete/text search mechanism.
"""

import asyncio
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

from playwright.async_api import async_playwright

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "recon_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

all_api_calls = []


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="ru-RU",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        )

        page = await context.new_page()

        async def on_response(response):
            url = response.url
            # Skip static assets and analytics
            skip = [".js", ".css", ".png", ".jpg", ".svg", ".woff", ".ico",
                    "google-analytics", "analytics", "gtag", "facebook",
                    "yandex.com", "mc.yandex", "_next/static", "fonts."]
            if any(s in url for s in skip):
                return

            try:
                req = response.request
                entry = {
                    "url": url,
                    "method": req.method,
                    "status": response.status,
                }

                # Only deeply inspect non-redirect successful responses
                if response.status == 200:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct or "text" in ct:
                        entry["request_headers"] = dict(req.headers)
                        if req.post_data:
                            entry["request_body"] = req.post_data
                        try:
                            body = await response.text()
                            if len(body) < 1_000_000:
                                entry["response_body"] = body[:10000]
                                entry["response_length"] = len(body)
                        except Exception:
                            pass

                all_api_calls.append(entry)

                # Print API calls
                if "api.arzonapteka" in url or ("arzonapteka" in url and req.method == "POST"):
                    print(f"\n{'='*80}")
                    print(f"[{req.method}] {url} -> {response.status}")
                    if req.post_data:
                        print(f"REQ BODY: {req.post_data[:500]}")
                    print(f"REQ HEADERS: {json.dumps(dict(req.headers), indent=2)[:800]}")
                    if entry.get("response_body"):
                        print(f"RESP ({entry.get('response_length', 0)} chars): {entry['response_body'][:1000]}")
                    print(f"{'='*80}")

                # Also catch RSC/Next.js data calls
                if "_rsc" in url or "/_next/data" in url or "RSC" in (req.headers.get("rsc", "") + req.headers.get("next-router-state-tree", "")):
                    print(f"\n>>> RSC CALL: [{req.method}] {url} -> {response.status}")
                    if entry.get("response_body"):
                        print(f"    Body: {entry['response_body'][:500]}")

            except Exception as e:
                pass

        page.on("response", on_response)

        # === STEP 1: Go to homepage, let it set cookies ===
        print("[1] Loading homepage (ru)...")
        await page.goto("https://arzonapteka.uz/ru", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        # Get cookies
        cookies = await context.cookies()
        print(f"\nCookies set ({len(cookies)}):")
        for c in cookies:
            print(f"  {c['name']} = {c['value'][:50]}...")

        # === STEP 2: Use search with autocomplete ===
        print("\n\n[2] Typing 'omron' in search box...")

        # Find the visible search input
        search = page.locator('input[type="search"]').first
        try:
            await search.wait_for(state="visible", timeout=10000)
            await search.click()
            await page.wait_for_timeout(500)

            # Type character by character to trigger autocomplete
            for char in "omron":
                await search.press(char)
                await page.wait_for_timeout(800)

            # Wait for autocomplete dropdown
            await page.wait_for_timeout(3000)

            # Check for autocomplete dropdown
            print("\n  Looking for autocomplete results...")
            suggestions = page.locator('[class*="suggest"], [class*="autocomplete"], [class*="dropdown"], [role="listbox"], [class*="search-result"], [class*="option"], ul li a')
            count = await suggestions.count()
            print(f"  Found {count} suggestion elements")

            for i in range(min(10, count)):
                try:
                    text = await suggestions.nth(i).inner_text()
                    if text.strip():
                        print(f"    [{i}]: {text.strip()[:100]}")
                except Exception:
                    pass

            # Now press Enter to search
            print("\n  Pressing Enter...")
            await search.press("Enter")
            await page.wait_for_timeout(8000)

            # Check URL after search
            print(f"  Current URL: {page.url}")

            # Get page text
            body_text = await page.inner_text("body")
            with open(os.path.join(OUTPUT_DIR, "search_omron_ru_text.txt"), "w", encoding="utf-8") as f:
                f.write(body_text)
            print(f"  Page text saved ({len(body_text)} chars)")

            # Show relevant lines
            lines = [l.strip() for l in body_text.split("\n") if l.strip() and len(l.strip()) > 3]
            print(f"  Content ({len(lines)} lines):")
            for line in lines[:40]:
                print(f"    {line[:120]}")

        except Exception as e:
            print(f"  Search failed: {str(e)[:200]}")

        # === STEP 3: Try direct medicine page ===
        print("\n\n[3] Loading medicine page (ID 10854, region -3)...")
        await page.goto("https://arzonapteka.uz/ru/search?medicine=10854&region=-3",
                        wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        # Get the pharmacy list from the page
        body_text2 = await page.inner_text("body")
        with open(os.path.join(OUTPUT_DIR, "medicine_10854_ru_text.txt"), "w", encoding="utf-8") as f:
            f.write(body_text2)

        lines = [l.strip() for l in body_text2.split("\n") if l.strip() and len(l.strip()) > 3]
        print(f"  Content ({len(lines)} lines):")
        for line in lines[:30]:
            print(f"    {line[:120]}")

        # === STEP 4: Try to search "тонометр" ===
        print("\n\n[4] Navigating to search for 'тонометр'...")
        await page.goto("https://arzonapteka.uz/ru", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(2000)

        search2 = page.locator('input[type="search"]').first
        try:
            await search2.wait_for(state="visible", timeout=10000)
            await search2.click()
            await page.wait_for_timeout(500)

            await search2.fill("тонометр")
            await page.wait_for_timeout(3000)

            # Check suggestions
            print("  Looking for suggestions...")
            # Try more general selectors
            all_links = page.locator('a[href*="search"], a[href*="medicine"]')
            count = await all_links.count()
            print(f"  Links with search/medicine: {count}")
            for i in range(min(20, count)):
                try:
                    href = await all_links.nth(i).get_attribute("href")
                    text = await all_links.nth(i).inner_text()
                    if text.strip():
                        print(f"    [{i}]: {text.strip()[:80]} -> {href}")
                except Exception:
                    pass

            # Press Enter
            await search2.press("Enter")
            await page.wait_for_timeout(8000)
            print(f"  URL after search: {page.url}")

            body_text3 = await page.inner_text("body")
            lines = [l.strip() for l in body_text3.split("\n") if l.strip() and len(l.strip()) > 3]
            print(f"  Results ({len(lines)} lines):")
            for line in lines[:20]:
                print(f"    {line[:120]}")

        except Exception as e:
            print(f"  Search failed: {str(e)[:200]}")

        await browser.close()

    # Save all API calls
    with open(os.path.join(OUTPUT_DIR, "all_api_calls.json"), "w", encoding="utf-8") as f:
        json.dump(all_api_calls, f, indent=2, ensure_ascii=False)

    print(f"\n\n{'='*80}")
    print(f"TOTAL: {len(all_api_calls)} calls captured")
    print(f"{'='*80}")

    # Filter and show API calls
    api_only = [c for c in all_api_calls if "api.arzonapteka" in c["url"]]
    print(f"\nAPI calls to api.arzonapteka.name: {len(api_only)}")
    for c in api_only:
        print(f"  [{c['method']}] {c['url']}")
        if c.get("request_body"):
            print(f"    Body: {c['request_body'][:200]}")

    # Show RSC calls
    rsc_calls = [c for c in all_api_calls if "_rsc" in c.get("url", "") or "text/x-component" in c.get("response_body", "")]
    print(f"\nRSC calls: {len(rsc_calls)}")
    for c in rsc_calls:
        print(f"  [{c['method']}] {c['url'][:100]}")


if __name__ == "__main__":
    asyncio.run(run())
