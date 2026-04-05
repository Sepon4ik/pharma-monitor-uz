"""
Direct API testing for api.arzonapteka.name
Now that we know the endpoint structure, test it directly with httpx.
"""

import json
import sys
import os

# Fix encoding for Windows console
sys.stdout.reconfigure(encoding='utf-8')

try:
    import httpx
except ImportError:
    os.system("pip install httpx")
    import httpx

BASE_URL = "https://api.arzonapteka.name/api/v4"

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Origin": "https://arzonapteka.uz",
    "Referer": "https://arzonapteka.uz/",
}

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "recon_output")


def api_post(endpoint, data, lang="ru"):
    """Make a POST request to the API."""
    url = f"{BASE_URL}/{lang}/{endpoint}"
    print(f"\n[POST] {url}")
    print(f"  Body: {json.dumps(data, ensure_ascii=False)[:300]}")

    resp = httpx.post(url, json=data, headers=HEADERS, timeout=30)
    print(f"  Status: {resp.status_code}")

    try:
        result = resp.json()
        return result
    except Exception:
        print(f"  Response: {resp.text[:500]}")
        return None


def api_get(endpoint, lang="ru"):
    """Make a GET request to the API."""
    url = f"{BASE_URL}/{lang}/{endpoint}"
    print(f"\n[GET] {url}")

    resp = httpx.get(url, headers=HEADERS, timeout=30)
    print(f"  Status: {resp.status_code}")

    try:
        result = resp.json()
        return result
    except Exception:
        print(f"  Response: {resp.text[:500]}")
        return None


def test_search_by_id():
    """Test search by medicine ID — we know this works."""
    print("\n" + "="*80)
    print("TEST 1: Search by medicine ID (10854)")
    print("="*80)

    data = {
        "country_code": "1",
        "platform": "web",
        "region": "-3",
        "search": ["10854"],
        "user": "test-user-123"
    }

    result = api_post("search", data)
    if result and result.get("ok"):
        drugstores = result["result"].get("drugstores", [])
        print(f"\n  Found {len(drugstores)} pharmacies")
        if drugstores:
            ds = drugstores[0]
            print(f"  First pharmacy: {ds['org_name']}")
            print(f"  Address: {ds['address']}")
            if ds.get("drugs"):
                drug = ds["drugs"][0]
                print(f"  Product: {drug['good_name']}")
                print(f"  Price: {drug['price']} UZS")
                print(f"  Count: {drug['count']}")
                print(f"  Vendor: {drug['vendor_name']}")
    else:
        print(f"  Error: {result}")

    return result


def test_search_by_text():
    """Try various text search approaches."""
    print("\n" + "="*80)
    print("TEST 2: Search by text")
    print("="*80)

    queries = [
        {"search": ["omron"], "desc": "text 'omron'"},
        {"search": ["OMRON"], "desc": "text 'OMRON'"},
        {"search": ["тонометр"], "desc": "text 'тонометр'"},
        {"search": ["тонометр omron"], "desc": "text 'тонометр omron'"},
    ]

    for q in queries:
        print(f"\n--- {q['desc']} ---")
        data = {
            "country_code": "1",
            "platform": "web",
            "region": "-3",
            "search": q["search"],
            "user": "test-user-123"
        }
        result = api_post("search", data, lang="ru")
        if result:
            if result.get("ok"):
                drugstores = result["result"].get("drugstores", [])
                print(f"  OK! {len(drugstores)} pharmacies found")
                if drugstores and drugstores[0].get("drugs"):
                    for drug in drugstores[0]["drugs"][:3]:
                        print(f"    - {drug['good_name']} | {drug['price']} UZS")
            else:
                print(f"  Not OK: error={result.get('error')}")


def test_other_endpoints():
    """Try to discover other API endpoints."""
    print("\n" + "="*80)
    print("TEST 3: Other API endpoints")
    print("="*80)

    # Common REST API patterns
    endpoints_get = [
        "catalog",
        "categories",
        "medicines",
        "products",
        "regions",
        "cities",
        "pharmacies",
        "drugstores",
        "brands",
        "vendors",
        "autocomplete",
        "suggest",
    ]

    endpoints_post = [
        ("autocomplete", {"query": "omron", "platform": "web"}),
        ("suggest", {"query": "omron", "platform": "web"}),
        ("medicines", {"query": "omron"}),
        ("catalog", {"query": "omron"}),
        ("search/suggest", {"query": "omron", "platform": "web"}),
        ("search/autocomplete", {"query": "omron"}),
    ]

    for ep in endpoints_get:
        result = api_get(ep)
        if result:
            print(f"  >>> FOUND: {ep} -> {json.dumps(result, ensure_ascii=False)[:300]}")

    for ep, body in endpoints_post:
        result = api_post(ep, body)
        if result:
            print(f"  >>> FOUND: {ep} -> {json.dumps(result, ensure_ascii=False)[:300]}")


def test_different_api_versions():
    """Try v1, v2, v3 API versions."""
    print("\n" + "="*80)
    print("TEST 4: API versions")
    print("="*80)

    for version in ["v1", "v2", "v3", "v5"]:
        url = f"https://api.arzonapteka.name/api/{version}/ru/search"
        print(f"\n[POST] {url}")
        try:
            resp = httpx.post(url, json={
                "country_code": "1",
                "platform": "web",
                "region": "-3",
                "search": ["10854"],
                "user": "test-user-123"
            }, headers=HEADERS, timeout=10)
            print(f"  Status: {resp.status_code}")
            if resp.status_code == 200:
                result = resp.json()
                print(f"  Response: {json.dumps(result, ensure_ascii=False)[:200]}")
        except Exception as e:
            print(f"  Error: {e}")


def test_search_multiple_ids():
    """Test searching for multiple medicine IDs at once."""
    print("\n" + "="*80)
    print("TEST 5: Multiple medicine IDs")
    print("="*80)

    # Try searching for multiple IDs
    data = {
        "country_code": "1",
        "platform": "web",
        "region": "-3",
        "search": ["10854", "2610", "2167"],
        "user": "test-user-123"
    }

    result = api_post("search", data, lang="ru")
    if result and result.get("ok"):
        drugstores = result["result"].get("drugstores", [])
        print(f"  Found {len(drugstores)} pharmacies")
        # Collect all unique product names
        products = set()
        for ds in drugstores:
            for drug in ds.get("drugs", []):
                products.add(drug["good_name"])
        print(f"  Unique products: {len(products)}")
        for p in list(products)[:10]:
            print(f"    - {p}")


def test_autocomplete_via_site():
    """Try to find the autocomplete endpoint by testing known patterns."""
    print("\n" + "="*80)
    print("TEST 6: Autocomplete endpoint discovery")
    print("="*80)

    # Try common autocomplete URL patterns
    patterns = [
        f"{BASE_URL}/ru/search/autocomplete?query=omron",
        f"{BASE_URL}/ru/autocomplete?query=omron",
        f"{BASE_URL}/ru/suggest?query=omron",
        "https://api.arzonapteka.name/autocomplete?query=omron",
        "https://api.arzonapteka.name/suggest?query=omron",
        "https://api.arzonapteka.name/api/autocomplete?query=omron",
        "https://arzonapteka.uz/api/search?query=omron",
        "https://arzonapteka.uz/api/autocomplete?query=omron",
        "https://arzonapteka.uz/api/suggest?query=omron",
    ]

    for url in patterns:
        print(f"\n[GET] {url}")
        try:
            resp = httpx.get(url, headers=HEADERS, timeout=10)
            print(f"  Status: {resp.status_code}")
            if resp.status_code == 200:
                print(f"  >>> FOUND! Response: {resp.text[:500]}")
        except Exception as e:
            print(f"  Error: {e}")

    # Also try POST variants
    post_patterns = [
        (f"{BASE_URL}/ru/search", {"query": "omron", "platform": "web"}),
        (f"{BASE_URL}/ru/search", {"search_text": "omron", "platform": "web"}),
        (f"{BASE_URL}/ru/search", {"text": "omron", "platform": "web", "country_code": "1"}),
    ]

    for url, body in post_patterns:
        print(f"\n[POST] {url}")
        print(f"  Body: {json.dumps(body, ensure_ascii=False)}")
        try:
            resp = httpx.post(url, json=body, headers=HEADERS, timeout=10)
            print(f"  Status: {resp.status_code}")
            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok"):
                    print(f"  >>> FOUND! {json.dumps(result, ensure_ascii=False)[:500]}")
                else:
                    print(f"  Response: {json.dumps(result, ensure_ascii=False)[:200]}")
        except Exception as e:
            print(f"  Error: {e}")


if __name__ == "__main__":
    test_search_by_id()
    test_search_by_text()
    test_other_endpoints()
    test_different_api_versions()
    test_search_multiple_ids()
    test_autocomplete_via_site()
