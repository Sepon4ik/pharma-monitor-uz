"""
API Reconnaissance Script for arzonapteka.uz

Intercepts all network requests while browsing the site to discover
API endpoints, data structures, and URL patterns for the scraper.
"""

import asyncio
import json
import os
from datetime import datetime
from playwright.async_api import async_playwright

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "recon_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Collect all intercepted API calls
api_calls = []


async def handle_response(response):
    """Capture API/fetch responses with JSON data."""
    url = response.url
    content_type = response.headers.get("content-type", "")

    # Skip static assets
    skip_patterns = [
        ".js", ".css", ".png", ".jpg", ".svg", ".woff", ".ico",
        "google", "analytics", "gtag", "facebook", "yandex",
        "_next/static", "fonts.googleapis"
    ]
    if any(p in url for p in skip_patterns):
        return

    try:
        status = response.status
        entry = {
            "url": url,
            "status": status,
            "content_type": content_type,
            "method": response.request.method,
            "timestamp": datetime.now().isoformat(),
        }

        # Try to capture JSON responses
        if "json" in content_type or "text" in content_type:
            try:
                body = await response.text()
                if len(body) < 500_000:  # Skip huge responses
                    entry["body_preview"] = body[:5000]
                    entry["body_length"] = len(body)
                    # Try parsing as JSON
                    try:
                        data = json.loads(body)
                        entry["is_json"] = True
                        entry["json_keys"] = list(data.keys()) if isinstance(data, dict) else f"array[{len(data)}]"
                    except (json.JSONDecodeError, TypeError):
                        entry["is_json"] = False
            except Exception:
                entry["body_preview"] = "<could not read>"

        api_calls.append(entry)

        # Print interesting calls in real-time
        if entry.get("is_json") or "api" in url.lower() or "search" in url.lower():
            print(f"\n{'='*80}")
            print(f"[{entry['method']}] {url}")
            print(f"Status: {status} | Content-Type: {content_type}")
            if entry.get("json_keys"):
                print(f"JSON keys: {entry['json_keys']}")
            if entry.get("body_preview"):
                preview = entry["body_preview"][:500]
                print(f"Preview: {preview}")
            print(f"{'='*80}")

    except Exception as e:
        print(f"Error processing {url}: {e}")


async def handle_request(route):
    """Log outgoing requests."""
    request = route.request
    url = request.url

    # Log POST requests (likely API calls)
    if request.method == "POST":
        print(f"\n>>> POST REQUEST: {url}")
        if request.post_data:
            print(f"    Body: {request.post_data[:500]}")

    await route.continue_()


async def run_recon():
    print("=" * 80)
    print("ArzonApteka API Reconnaissance")
    print("=" * 80)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="en-US",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        )

        page = await context.new_page()

        # Intercept all responses
        page.on("response", handle_response)

        # Intercept all requests (to log POST bodies)
        await page.route("**/*", handle_request)

        # --- Step 1: Visit homepage ---
        print("\n\n[STEP 1] Loading homepage...")
        await page.goto("https://arzonapteka.uz/en", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)
        print(f"  Page title: {await page.title()}")

        # --- Step 2: Search for OMRON ---
        print("\n\n[STEP 2] Searching for 'omron'...")

        # Try finding search input
        search_selectors = [
            'input[type="search"]',
            'input[placeholder*="search" i]',
            'input[placeholder*="поиск" i]',
            'input[placeholder*="qidirish" i]',
            'input[name="query"]',
            'input[name="search"]',
            '#search',
            '.search-input',
            'input[type="text"]',
        ]

        search_found = False
        for selector in search_selectors:
            try:
                el = page.locator(selector).first
                if await el.is_visible(timeout=2000):
                    print(f"  Found search input: {selector}")
                    await el.click()
                    await el.fill("omron")
                    await page.wait_for_timeout(1000)

                    # Try pressing Enter
                    await el.press("Enter")
                    await page.wait_for_timeout(5000)
                    search_found = True
                    break
            except Exception:
                continue

        if not search_found:
            print("  Search input not found, trying direct URL...")
            await page.goto("https://arzonapteka.uz/en/search?query=omron", wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(5000)

        # Capture page content after search
        page_content = await page.content()
        with open(os.path.join(OUTPUT_DIR, "search_omron_page.html"), "w", encoding="utf-8") as f:
            f.write(page_content)
        print(f"  Saved page HTML ({len(page_content)} chars)")

        # Extract __NEXT_DATA__ if present
        try:
            next_data = await page.evaluate("() => window.__NEXT_DATA__")
            if next_data:
                with open(os.path.join(OUTPUT_DIR, "next_data_search.json"), "w", encoding="utf-8") as f:
                    json.dump(next_data, f, indent=2, ensure_ascii=False)
                print("  Saved __NEXT_DATA__")
        except Exception as e:
            print(f"  No __NEXT_DATA__: {e}")

        # Extract any window state
        try:
            for var_name in ["__INITIAL_STATE__", "__APP_DATA__", "__PRELOADED_STATE__"]:
                data = await page.evaluate(f"() => window.{var_name}")
                if data:
                    with open(os.path.join(OUTPUT_DIR, f"{var_name}.json"), "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    print(f"  Found {var_name}!")
        except Exception:
            pass

        # Try to find product listings in the DOM
        print("\n  Looking for product elements in DOM...")
        product_selectors = [
            '[class*="product"]', '[class*="card"]', '[class*="item"]',
            '[class*="medicine"]', '[class*="drug"]', '[class*="result"]',
            '[data-testid*="product"]', 'article', '.list-item',
        ]

        for selector in product_selectors:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    print(f"  {selector}: {count} elements found")
                    # Get text from first few
                    for i in range(min(3, count)):
                        text = await page.locator(selector).nth(i).inner_text()
                        if text.strip() and len(text.strip()) > 10:
                            print(f"    [{i}]: {text.strip()[:200]}")
            except Exception:
                continue

        # Take a screenshot
        await page.screenshot(path=os.path.join(OUTPUT_DIR, "search_omron.png"), full_page=True)
        print("  Screenshot saved")

        # --- Step 3: Try a specific medicine page ---
        print("\n\n[STEP 3] Loading specific medicine page (ID 10854)...")
        await page.goto("https://arzonapteka.uz/en/search?medicine=10854&region=-3",
                        wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        # Capture this page too
        page_content2 = await page.content()
        with open(os.path.join(OUTPUT_DIR, "medicine_10854_page.html"), "w", encoding="utf-8") as f:
            f.write(page_content2)

        await page.screenshot(path=os.path.join(OUTPUT_DIR, "medicine_10854.png"), full_page=True)

        # Extract product data from DOM
        print("  Looking for product/pharmacy data...")
        try:
            all_text = await page.inner_text("body")
            with open(os.path.join(OUTPUT_DIR, "medicine_10854_text.txt"), "w", encoding="utf-8") as f:
                f.write(all_text)
            print(f"  Page text saved ({len(all_text)} chars)")
            # Show preview
            lines = [l.strip() for l in all_text.split("\n") if l.strip()]
            print(f"  Content preview (first 30 lines):")
            for line in lines[:30]:
                print(f"    {line[:120]}")
        except Exception as e:
            print(f"  Error: {e}")

        # --- Step 4: Try to find pharmacy list for this medicine ---
        print("\n\n[STEP 4] Looking for pharmacy listings...")
        pharmacy_selectors = [
            '[class*="pharmacy"]', '[class*="apteka"]', '[class*="offer"]',
            '[class*="price"]', '[class*="store"]', '[class*="shop"]',
            'table tr', '.list-group-item',
        ]

        for selector in pharmacy_selectors:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    print(f"  {selector}: {count} elements")
                    for i in range(min(5, count)):
                        text = await page.locator(selector).nth(i).inner_text()
                        if text.strip() and len(text.strip()) > 5:
                            print(f"    [{i}]: {text.strip()[:200]}")
            except Exception:
                continue

        # --- Step 5: Try pharmacy page ---
        print("\n\n[STEP 5] Loading pharmacy page...")
        await page.goto("https://arzonapteka.uz/en/pharmacy/tashkent?view=list",
                        wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        pharmacy_text = await page.inner_text("body")
        with open(os.path.join(OUTPUT_DIR, "pharmacy_tashkent_text.txt"), "w", encoding="utf-8") as f:
            f.write(pharmacy_text)
        print(f"  Pharmacy page text saved ({len(pharmacy_text)} chars)")

        await page.screenshot(path=os.path.join(OUTPUT_DIR, "pharmacy_tashkent.png"), full_page=True)

        await browser.close()

    # --- Save all captured API calls ---
    output_file = os.path.join(OUTPUT_DIR, "api_calls.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(api_calls, f, indent=2, ensure_ascii=False)

    print(f"\n\n{'='*80}")
    print(f"RECON COMPLETE")
    print(f"{'='*80}")
    print(f"Total API calls captured: {len(api_calls)}")
    print(f"JSON responses: {sum(1 for c in api_calls if c.get('is_json'))}")
    print(f"Results saved to: {OUTPUT_DIR}")
    print(f"\nFiles:")
    for f in os.listdir(OUTPUT_DIR):
        size = os.path.getsize(os.path.join(OUTPUT_DIR, f))
        print(f"  {f} ({size:,} bytes)")

    # Summary of unique API endpoints
    print(f"\nUnique URLs captured:")
    seen = set()
    for call in api_calls:
        # Strip query params for grouping
        base_url = call["url"].split("?")[0]
        if base_url not in seen:
            seen.add(base_url)
            print(f"  [{call['method']}] {call['url'][:120]}")


if __name__ == "__main__":
    asyncio.run(run_recon())
