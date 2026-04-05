"""
Find the search/autocomplete mechanism by intercepting ALL network calls
while performing a search via JavaScript evaluation.
"""

import asyncio
import json
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="ru-RU",
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        all_calls = []

        async def on_response(response):
            url = response.url
            skip = [".js", ".css", ".png", ".jpg", ".svg", ".woff", ".ico",
                    "google", "analytics", "yandex", "facebook", "_next/static", "fonts."]
            if any(s in url for s in skip):
                return
            try:
                entry = {"url": url, "method": response.request.method, "status": response.status}
                if response.status == 200:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct or "text" in ct:
                        body = await response.text()
                        entry["body"] = body[:3000]
                        if response.request.post_data:
                            entry["post_data"] = response.request.post_data[:500]
                all_calls.append(entry)
                if "api" in url.lower() or "search" in url.lower() or "suggest" in url.lower():
                    print(f"  [{response.request.method}] {url} -> {response.status}")
                    if entry.get("post_data"):
                        print(f"    POST: {entry['post_data'][:200]}")
                    if entry.get("body") and len(entry['body']) < 500:
                        print(f"    BODY: {entry['body'][:300]}")
            except Exception:
                pass

        page.on("response", on_response)

        # Load homepage
        print("[1] Loading homepage...")
        await page.goto("https://arzonapteka.uz/ru", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        # Find ALL inputs on the page
        print("\n[2] Analyzing page inputs...")
        inputs = await page.evaluate("""
            () => {
                const inputs = document.querySelectorAll('input');
                return Array.from(inputs).map((el, i) => ({
                    index: i,
                    type: el.type,
                    placeholder: el.placeholder,
                    name: el.name,
                    className: el.className,
                    visible: el.offsetParent !== null,
                    rect: el.getBoundingClientRect(),
                }));
            }
        """)
        print(f"  Found {len(inputs)} inputs:")
        for inp in inputs:
            print(f"    [{inp['index']}] type={inp['type']}, placeholder='{inp['placeholder']}', "
                  f"visible={inp['visible']}, class={inp['className'][:60]}")

        # Try to interact with search by simulating user actions
        print("\n[3] Trying to trigger search via JS...")

        # Method 1: Find and focus the search input, trigger React events
        search_result = await page.evaluate("""
            async () => {
                const results = [];

                // Find search inputs
                const inputs = document.querySelectorAll('input[type="search"], input[placeholder*="Найти"], input[placeholder*="цен"]');
                results.push(`Found ${inputs.length} search inputs`);

                for (const input of inputs) {
                    // Make visible
                    input.style.display = 'block';
                    input.style.visibility = 'visible';
                    input.style.opacity = '1';
                    input.style.position = 'fixed';
                    input.style.top = '100px';
                    input.style.left = '100px';
                    input.style.zIndex = '99999';
                    input.style.width = '300px';
                    input.style.height = '40px';

                    // Traverse up and make parents visible
                    let parent = input.parentElement;
                    for (let i = 0; i < 10 && parent; i++) {
                        parent.style.display = 'block';
                        parent.style.visibility = 'visible';
                        parent.style.opacity = '1';
                        parent = parent.parentElement;
                    }

                    results.push(`Made input visible: ${input.placeholder}`);
                }

                return results;
            }
        """)
        print(f"  {search_result}")

        await page.wait_for_timeout(1000)

        # Now try to type
        search_input = page.locator('input[type="search"]').first
        try:
            visible = await search_input.is_visible()
            print(f"  Search input visible now: {visible}")

            if visible:
                print("  Typing 'тонометр'...")
                await search_input.click()
                await page.wait_for_timeout(500)

                # Type with React-compatible events
                await page.evaluate("""
                    (text) => {
                        const input = document.querySelector('input[type="search"]');
                        if (!input) return;

                        // Set value via native setter to trigger React
                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value'
                        ).set;
                        nativeInputValueSetter.call(input, text);

                        // Dispatch events
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                """, "тонометр")

                await page.wait_for_timeout(3000)

                # Check for any new elements that appeared
                suggestions = await page.evaluate("""
                    () => {
                        const results = [];
                        // Check for any new visible elements
                        const allElements = document.querySelectorAll('*');
                        for (const el of allElements) {
                            const text = el.textContent || '';
                            if (text.length > 5 && text.length < 200) {
                                const rect = el.getBoundingClientRect();
                                if (rect.width > 0 && rect.height > 0 && rect.top > 0) {
                                    const lower = text.toLowerCase();
                                    if (lower.includes('тонометр') || lower.includes('omron') ||
                                        lower.includes('microlife') || lower.includes('давлен')) {
                                        const tag = el.tagName.toLowerCase();
                                        if (tag === 'a' || tag === 'li' || tag === 'div' || tag === 'span' || tag === 'p') {
                                            results.push({
                                                tag: tag,
                                                text: text.substring(0, 200),
                                                href: el.getAttribute('href') || '',
                                                class: el.className.substring(0, 50),
                                            });
                                        }
                                    }
                                }
                            }
                        }
                        return results.slice(0, 30);
                    }
                """)
                print(f"  Matching elements: {len(suggestions)}")
                for s in suggestions:
                    print(f"    <{s['tag']}> {s['text'][:100]} -> {s['href']}")
            else:
                print("  Still not visible, trying keyboard navigation...")
                # Press Tab to focus search
                await page.keyboard.press("Tab")
                await page.wait_for_timeout(500)
                await page.keyboard.press("Tab")
                await page.wait_for_timeout(500)
                await page.keyboard.type("тонометр", delay=100)
                await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"  Error: {str(e)[:200]}")

        # Method 2: Check Next.js RSC for search
        print("\n[4] Trying RSC search endpoint...")
        rsc_result = await page.evaluate("""
            async () => {
                try {
                    const resp = await fetch('/ru/search?query=тонометр', {
                        headers: {
                            'RSC': '1',
                            'Next-Router-State-Tree': '%5B%22%22%2C%7B%22locale%22%3A%22ru%22%7D%5D',
                        }
                    });
                    const text = await resp.text();
                    return text.substring(0, 3000);
                } catch(e) {
                    return 'Error: ' + e.message;
                }
            }
        """)
        print(f"  RSC response ({len(rsc_result)} chars):")
        # Look for medicine IDs in the RSC response
        import re
        medicine_ids = re.findall(r'medicine[=:](\d+)', rsc_result)
        if medicine_ids:
            print(f"  Found medicine IDs: {medicine_ids}")

        # Look for product names
        for keyword in ["тонометр", "omron", "microlife", "prolife", "давлен"]:
            if keyword in rsc_result.lower():
                # Extract surrounding context
                idx = rsc_result.lower().index(keyword)
                context = rsc_result[max(0,idx-50):idx+200]
                print(f"  Found '{keyword}' in RSC: ...{context}...")

        # Save RSC response
        with open("recon_output/rsc_search_response.txt", "w", encoding="utf-8") as f:
            f.write(rsc_result)

        # Method 3: Try fetching RSC for the choose-pharmacy page
        print("\n[5] Trying RSC for choose-pharmacy...")
        rsc_result2 = await page.evaluate("""
            async () => {
                try {
                    const resp = await fetch('/ru/choose-pharmacy?query=тонометр', {
                        headers: { 'RSC': '1' }
                    });
                    return await resp.text();
                } catch(e) {
                    return 'Error: ' + e.message;
                }
            }
        """)
        print(f"  Response: {rsc_result2[:500]}")

        await browser.close()

        # Save all captured calls
        with open("recon_output/search_api_calls.json", "w", encoding="utf-8") as f:
            json.dump(all_calls, f, indent=2, ensure_ascii=False)
        print(f"\nSaved {len(all_calls)} network calls")


if __name__ == "__main__":
    asyncio.run(run())
