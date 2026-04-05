"""
Find Prolife and other brand products.
The screenshot shows they exist - we need to find their medicine IDs.
Strategy: use Playwright to navigate to actual search results and capture API calls.
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


async def find_via_browser():
    """Use browser to search and capture the medicine IDs from the results."""
    found_ids = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="en-US",
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        # Capture API calls
        async def on_response(response):
            if "api.arzonapteka" in response.url and response.status == 200:
                try:
                    req = response.request
                    if req.post_data:
                        body = json.loads(req.post_data)
                        search_ids = body.get("search", [])
                        if search_ids:
                            print(f"  API search IDs: {search_ids}")
                            # Get response to map IDs to names
                            resp_body = await response.text()
                            data = json.loads(resp_body)
                            if data.get("ok"):
                                for ds in data["result"].get("drugstores", [])[:3]:
                                    for drug in ds.get("drugs", []):
                                        gid = drug["good_id"]
                                        if gid not in found_ids:
                                            found_ids[gid] = {
                                                "good_id": gid,
                                                "good_name": drug["good_name"],
                                                "vendor_name": drug.get("vendor_name", ""),
                                                "price": drug.get("price", ""),
                                            }
                except Exception:
                    pass

        page.on("response", on_response)

        # The screenshot shows the page at arzonapteka.uz with Prolife products
        # The URL likely has search params. Let's try the search flow properly.

        # Strategy: go to homepage, find search, use keyboard to type
        print("[1] Loading homepage...")
        await page.goto("https://arzonapteka.uz/en", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        # The search input is the second one (visible on desktop)
        # Use keyboard shortcut or click on the search area
        print("[2] Trying to use search...")

        # Try clicking the search bar area at the top of the page
        # From screenshot it's in the header, let's try clicking at specific coordinates
        await page.click('header', timeout=5000)
        await page.wait_for_timeout(500)

        # Find and interact with search using evaluate
        search_result = await page.evaluate("""
            async () => {
                // Find all search inputs
                const inputs = document.querySelectorAll('input[type="search"]');
                for (const input of inputs) {
                    if (input.offsetParent !== null || input.offsetHeight > 0) {
                        // This one is visible or has dimensions
                        input.focus();

                        // Use React's native value setter
                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value'
                        ).set;
                        nativeInputValueSetter.call(input, 'prolife');

                        // Dispatch React-compatible events
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));

                        // Wait a bit for autocomplete
                        await new Promise(r => setTimeout(r, 2000));

                        // Check for dropdown/suggestions
                        const suggestions = [];
                        const links = document.querySelectorAll('a');
                        for (const link of links) {
                            const href = link.getAttribute('href') || '';
                            const text = link.textContent.trim();
                            if (href.includes('medicine') || href.includes('choose-pharmacy')) {
                                suggestions.push({ text: text.substring(0, 100), href });
                            }
                        }

                        // Try submitting
                        const form = input.closest('form');
                        if (form) {
                            form.dispatchEvent(new Event('submit', { bubbles: true }));
                        } else {
                            input.dispatchEvent(new KeyboardEvent('keydown', {
                                key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true
                            }));
                        }

                        return {
                            inputFound: true,
                            placeholder: input.placeholder,
                            value: input.value,
                            suggestions: suggestions,
                        };
                    }
                }
                return { inputFound: false };
            }
        """)
        print(f"  Search result: {json.dumps(search_result, ensure_ascii=False)[:500]}")

        await page.wait_for_timeout(5000)
        print(f"  URL after search: {page.url}")

        # If URL changed, check for medicine params
        url = page.url
        m_ids = re.findall(r'[?&]m(?:edicine)?=([^&]+)', url)
        if m_ids:
            print(f"  Medicine IDs from URL: {m_ids}")

        # Try to get the page content
        try:
            text = await page.inner_text("body")
            # Look for product names
            for line in text.split("\n"):
                line = line.strip()
                if line and any(kw in line.lower() for kw in ["prolife", "omron", "microlife", "тонометр", "небулайзер", "термометр"]):
                    print(f"  >> {line[:120]}")
        except Exception:
            pass

        # Try direct URL approach - the screenshot shows it working
        # Maybe the search sends comma-separated IDs in the URL
        print("\n[3] Trying direct search URLs...")

        search_urls = [
            "https://arzonapteka.uz/en/search?query=prolife",
            "https://arzonapteka.uz/en/search?query=prolife&region=-3",
            "https://arzonapteka.uz/ru/search?query=prolife",
            "https://arzonapteka.uz/ru/search?query=prolife&region=-3",
        ]

        for surl in search_urls:
            print(f"\n  Navigating to: {surl}")
            await page.goto(surl, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(5000)
            print(f"  Final URL: {page.url}")

            # Extract medicine IDs from final URL
            final_url = page.url
            m_param = re.search(r'[?&]m=([^&]+)', final_url)
            if m_param:
                ids_str = m_param.group(1)
                print(f"  >>> Medicine IDs: {ids_str}")

            # Get page text
            try:
                text = await page.inner_text("body")
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                product_lines = [l for l in lines if any(kw in l.lower() for kw in
                    ["prolife", "omron", "microlife", "тонометр", "небулайзер", "термометр", "uzs", "сум"])]
                if product_lines:
                    print(f"  Product lines ({len(product_lines)}):")
                    for pl in product_lines[:20]:
                        print(f"    {pl[:120]}")
            except Exception:
                pass

        await browser.close()

    return found_ids


async def main():
    print("Finding Prolife products on ArzonApteka...")
    found = await find_via_browser()

    print(f"\n\n{'='*60}")
    print(f"Found {len(found)} products via API interception:")
    for gid, info in found.items():
        print(f"  [{gid}] {info['good_name']} | {info['vendor_name']} | {info['price']} UZS")

    with open("recon_output/prolife_products.json", "w", encoding="utf-8") as f:
        json.dump(found, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    asyncio.run(main())
