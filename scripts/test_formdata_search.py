"""
Test text search via FormData (not JSON) - as discovered in JS bundles.
The API key is generated as: md5(BASE_URL + ENDPOINT + SECRET)
where SECRET = "Nx3WWr"
"""

import hashlib
import json
import sys
import httpx

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "https://api.arzonapteka.name"
SECRET = "Nx3WWr"


def make_api_key(endpoint):
    """Generate API key: md5(BASE_URL + endpoint + SECRET)"""
    raw = f"{BASE_URL}{endpoint}{SECRET}"
    return hashlib.md5(raw.encode()).hexdigest()


def search_text(query, region="-3", lang="ru"):
    """Search using FormData (text search)."""
    endpoint = f"/api/v4/{lang}/search"
    api_key = make_api_key(endpoint)

    print(f"\n  Endpoint: {endpoint}")
    print(f"  API Key: {api_key}")
    print(f"  Query: '{query}'")

    form_data = {
        "user": "test-user-123",
        "search": query,
        "region": region,
        "country_code": "1",
        "detail": "true",
        "platform": "web",
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://arzonapteka.uz",
        "Referer": "https://arzonapteka.uz/",
        "Api-Key": api_key,
    }

    resp = httpx.post(f"{BASE_URL}{endpoint}", data=form_data, headers=headers, timeout=30)
    return resp.json()


def search_json(medicine_ids, region="-3", lang="ru"):
    """Search using JSON (by medicine IDs)."""
    endpoint = f"/api/v4/{lang}/search"
    api_key = make_api_key(endpoint)

    data = {
        "country_code": "1",
        "platform": "web",
        "region": region,
        "search": medicine_ids,
        "user": "test-user-123"
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://arzonapteka.uz",
        "Referer": "https://arzonapteka.uz/",
        "Api-Key": api_key,
    }

    resp = httpx.post(f"{BASE_URL}{endpoint}", json=data, headers=headers, timeout=30)
    return resp.json()


# Test 1: Text search via FormData
print("=" * 80)
print("TEST: Text search via FormData")
print("=" * 80)

queries = [
    "тонометр",
    "omron",
    "OMRON",
    "microlife",
    "prolife",
    "небулайзер",
    "термометр",
    "тонометр omron",
    "давление",
    "ингалятор",
]

for query in queries:
    print(f"\n{'='*60}")
    print(f"Query: '{query}'")

    result = search_text(query)

    if result.get("ok"):
        # Check what we get back
        res = result["result"]

        # Could be suggestions/autocomplete or full results
        if isinstance(res, dict):
            keys = list(res.keys())
            print(f"  OK! Keys: {keys}")

            if "drugstores" in res:
                ds = res["drugstores"]
                print(f"  Drugstores: {len(ds)}")
                products = set()
                for d in ds[:20]:
                    for drug in d.get("drugs", []):
                        products.add(f"[{drug['good_id']}] {drug['good_name']}")
                print(f"  Unique products ({len(products)}):")
                for p in sorted(products):
                    print(f"    {p}")
            else:
                # Print whatever we got
                print(f"  Result: {json.dumps(res, ensure_ascii=False)[:1000]}")

        elif isinstance(res, list):
            print(f"  OK! Got list of {len(res)} items")
            for item in res[:10]:
                print(f"    {json.dumps(item, ensure_ascii=False)[:200]}")
    else:
        print(f"  Error: {result.get('error')}")
        print(f"  Full: {json.dumps(result, ensure_ascii=False)[:300]}")


# Test 2: Verify JSON search still works with correct API key
print(f"\n\n{'='*80}")
print("TEST 2: JSON search with computed API key")
print("="*80)

result = search_json(["10854"])
if result.get("ok"):
    ds = result["result"]["drugstores"]
    print(f"OK! {len(ds)} drugstores for medicine 10854")
else:
    print(f"Error: {result}")


# Test 3: Try other endpoints
print(f"\n\n{'='*80}")
print("TEST 3: Other endpoints with proper API key")
print("="*80)

other_endpoints = [
    "/api/v4/ru/regions",
    "/api/v4/ru/pharmacies",
    "/api/v4/ru/categories",
]

for endpoint in other_endpoints:
    api_key = make_api_key(endpoint)
    print(f"\n  [{endpoint}] key={api_key}")

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://arzonapteka.uz",
        "Api-Key": api_key,
    }

    # Try GET
    try:
        resp = httpx.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=10)
        print(f"  GET: {resp.status_code} -> {resp.text[:300]}")
    except Exception as e:
        print(f"  GET failed: {e}")

    # Try POST with FormData
    try:
        resp = httpx.post(f"{BASE_URL}{endpoint}",
                          data={"country_code": "1", "platform": "web"},
                          headers=headers, timeout=10)
        print(f"  POST form: {resp.status_code} -> {resp.text[:300]}")
    except Exception as e:
        print(f"  POST failed: {e}")
