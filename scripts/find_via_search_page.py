"""
Navigate to search results page and use the SECOND (visible) input.
Also intercept what happens when the search page loads with a query.
"""

import asyncio
import json
import sys
import re
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')

api_calls = []


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="ru-RU",
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        async def on_response(response):
            url = response.url
            skip = [".css", ".png", ".jpg", ".svg", ".woff", ".ico",
                    "google", "analytics", "yandex", "facebook", "_next/static", "fonts."]
            if any(s in url for s in skip):
                return
            try:
                entry = {"url": url, "method": response.request.method, "status": response.status}
                ct = response.headers.get("content-type", "")
                if response.status == 200 and ("json" in ct or "text" in ct or "component" in ct):
                    body = await response.text()
                    entry["body"] = body[:5000]
                    if response.request.post_data:
                        entry["post_data"] = response.request.post_data
                api_calls.append(entry)

                if "api.arzonapteka" in url:
                    print(f"\n*** API: [{response.request.method}] {url} -> {response.status}")
                    if entry.get("post_data"):
                        print(f"    POST: {entry['post_data'][:300]}")
                    if entry.get("body"):
                        print(f"    RESP: {entry['body'][:500]}")
            except Exception:
                pass

        page.on("response", on_response)

        # Step 1: Go to homepage, use the SECOND (visible) search input
        print("[1] Homepage -> use visible search input...")
        await page.goto("https://arzonapteka.uz/ru", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(2000)

        # Use nth(1) - the second, visible input
        search_input = page.locator('input[type="search"]').nth(1)
        try:
            visible = await search_input.is_visible()
            print(f"  Second search input visible: {visible}")

            if visible:
                await search_input.click()
                await page.wait_for_timeout(1000)

                # Type slowly to trigger autocomplete
                print("  Typing 'тонометр'...")
                for char in "тонометр":
                    await search_input.press(char)
                    await page.wait_for_timeout(300)

                await page.wait_for_timeout(3000)

                # Get all links on page
                links = await page.evaluate("""
                    () => {
                        const links = [];
                        document.querySelectorAll('a').forEach(a => {
                            const href = a.getAttribute('href') || '';
                            const text = a.textContent.trim();
                            if ((href.includes('medicine') || href.includes('search') || href.includes('choose'))
                                && text.length > 0 && text.length < 200) {
                                links.push({ text, href });
                            }
                        });
                        return links;
                    }
                """)
                print(f"  Links with medicine/search/choose: {len(links)}")
                for l in links[:20]:
                    print(f"    {l['text'][:80]} -> {l['href']}")

                # Press Enter
                await search_input.press("Enter")
                await page.wait_for_timeout(8000)
                print(f"\n  URL after Enter: {page.url}")
        except Exception as e:
            print(f"  Error: {str(e)[:200]}")

        # Step 2: Try navigating directly to search with specific queries
        search_queries = [
            "тонометр",
            "небулайзер",
            "термометр",
            "тонометр+omron",
        ]

        for query in search_queries:
            print(f"\n\n[SEARCH] Navigating to search: '{query}'...")
            url = f"https://arzonapteka.uz/ru/search?query={query}"
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(5000)

            final_url = page.url
            print(f"  Final URL: {final_url}")

            # Extract medicine IDs from URL
            m_ids = re.findall(r'medicine[=:](\d+)', final_url)
            if m_ids:
                print(f"  Medicine IDs in URL: {m_ids}")

            # Get page content
            try:
                text = await page.inner_text("body")
                lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 5]
                print(f"  Page lines: {len(lines)}")
                for line in lines[:25]:
                    print(f"    {line[:120]}")

                # Look for product elements
                products_in_dom = await page.evaluate("""
                    () => {
                        const products = [];
                        // Look for elements with price-like text
                        const allText = document.body.innerText;
                        const lines = allText.split('\\n').filter(l => l.trim().length > 5);
                        return lines.filter(l =>
                            l.match(/\\d+\\s*сум/) || l.match(/\\d+\\s*UZS/) ||
                            l.toLowerCase().includes('тонометр') ||
                            l.toLowerCase().includes('omron') ||
                            l.toLowerCase().includes('microlife')
                        ).slice(0, 20);
                    }
                """)
                if products_in_dom:
                    print(f"\n  Product-like lines:")
                    for line in products_in_dom:
                        print(f"    {line[:120]}")
            except Exception as e:
                print(f"  Error: {str(e)[:100]}")

        # Step 3: Check JS bundles for the search/autocomplete logic
        print("\n\n[JS] Checking main JS chunks for API endpoints...")
        js_chunks = await page.evaluate("""
            () => {
                const scripts = document.querySelectorAll('script[src*="_next"]');
                return Array.from(scripts).map(s => s.src).slice(0, 10);
            }
        """)
        print(f"  JS chunks: {len(js_chunks)}")
        for chunk_url in js_chunks[:5]:
            print(f"    {chunk_url}")

        await browser.close()

        # Save results
        with open("recon_output/search_page_calls.json", "w", encoding="utf-8") as f:
            json.dump(api_calls, f, indent=2, ensure_ascii=False)

        # Check all API calls for patterns
        print(f"\n\nAll API calls to api.arzonapteka.name:")
        for call in api_calls:
            if "api.arzonapteka" in call["url"]:
                print(f"  [{call['method']}] {call['url']}")
                if call.get("post_data"):
                    print(f"    POST: {call['post_data'][:200]}")


if __name__ == "__main__":
    asyncio.run(run())
