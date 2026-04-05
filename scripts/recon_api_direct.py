"""
Direct API exploration for api.arzonapteka.name
Intercept the exact request body sent to the API, then call it directly.
"""

import asyncio
import json
import os
from playwright.async_api import async_playwright

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "recon_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

captured_requests = []


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="en-US",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        )

        page = await context.new_page()

        async def capture_api(response):
            url = response.url
            if "api.arzonapteka" in url:
                try:
                    req = response.request
                    entry = {
                        "url": url,
                        "method": req.method,
                        "status": response.status,
                        "request_headers": dict(req.headers),
                        "response_headers": dict(response.headers),
                    }

                    # Capture request body
                    if req.post_data:
                        entry["request_body"] = req.post_data
                        try:
                            entry["request_json"] = json.loads(req.post_data)
                        except (json.JSONDecodeError, TypeError):
                            pass

                    # Capture response body
                    try:
                        body = await response.text()
                        entry["response_body_length"] = len(body)
                        try:
                            data = json.loads(body)
                            entry["response_json"] = data
                        except (json.JSONDecodeError, TypeError):
                            entry["response_text"] = body[:5000]
                    except Exception as e:
                        entry["response_error"] = str(e)

                    captured_requests.append(entry)

                    print(f"\n{'='*80}")
                    print(f"[{req.method}] {url}")
                    print(f"Status: {response.status}")
                    if entry.get("request_json"):
                        print(f"Request body: {json.dumps(entry['request_json'], indent=2, ensure_ascii=False)}")
                    if entry.get("response_json"):
                        resp_str = json.dumps(entry["response_json"], indent=2, ensure_ascii=False)
                        print(f"Response ({len(resp_str)} chars): {resp_str[:3000]}")
                    print(f"{'='*80}")

                except Exception as e:
                    print(f"Error capturing {url}: {e}")

        page.on("response", capture_api)

        # Step 1: Search page with query "omron" — all regions
        print("[1] Searching 'omron' (all regions)...")
        await page.goto("https://arzonapteka.uz/en/search?query=omron&region=-3",
                        wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        # Step 2: Search for "тонометр" (tonometer in Russian)
        print("\n[2] Searching 'тонометр'...")
        await page.goto("https://arzonapteka.uz/ru/search?query=%D1%82%D0%BE%D0%BD%D0%BE%D0%BC%D0%B5%D1%82%D1%80&region=-3",
                        wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        # Step 3: Search by medicine ID (we know this pattern works)
        print("\n[3] Loading medicine ID 10854...")
        await page.goto("https://arzonapteka.uz/en/search?medicine=10854&region=-3",
                        wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        # Step 4: Try choose-pharmacy page (seen in URL redirect)
        print("\n[4] Loading choose-pharmacy page...")
        await page.goto("https://arzonapteka.uz/en/choose-pharmacy?m=10854&r=-3",
                        wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        # Step 5: Try the search input with autocomplete
        print("\n[5] Testing autocomplete on homepage...")
        await page.goto("https://arzonapteka.uz/en", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(2000)

        # Try to find and type in search
        try:
            search_input = page.locator('input').first
            await search_input.click()
            await page.wait_for_timeout(500)

            # Type slowly to trigger autocomplete
            for char in "omron":
                await search_input.type(char, delay=200)
                await page.wait_for_timeout(500)

            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"  Autocomplete test failed: {e}")

        # Step 6: Try pharmacy page
        print("\n[6] Loading pharmacy 115035...")
        await page.goto("https://arzonapteka.uz/en/pharmacy/uzbekistan/115035",
                        wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        await browser.close()

    # Save results
    output_file = os.path.join(OUTPUT_DIR, "api_requests.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(captured_requests, f, indent=2, ensure_ascii=False)

    print(f"\n\n{'='*80}")
    print(f"CAPTURED {len(captured_requests)} API REQUESTS")
    print(f"{'='*80}")
    print(f"Saved to: {output_file}")

    # Print summary
    for i, req in enumerate(captured_requests):
        print(f"\n--- Request {i+1} ---")
        print(f"URL: {req['url']}")
        print(f"Method: {req['method']}")
        if req.get("request_json"):
            print(f"Request: {json.dumps(req['request_json'], ensure_ascii=False)[:300]}")
        if req.get("response_json"):
            resp = req["response_json"]
            if isinstance(resp, dict):
                print(f"Response keys: {list(resp.keys())}")
            elif isinstance(resp, list):
                print(f"Response: array of {len(resp)} items")


if __name__ == "__main__":
    asyncio.run(run())
