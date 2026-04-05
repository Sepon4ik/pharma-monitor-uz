"""
Get full pharmacy list and try text search with specific regions.
Also try to find medicine IDs by scanning from the Playwright-captured search page.
"""

import hashlib
import json
import sys
import httpx

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "https://api.arzonapteka.name"
SECRET = "Nx3WWr"


def make_api_key(endpoint):
    raw = f"{BASE_URL}{endpoint}{SECRET}"
    return hashlib.md5(raw.encode()).hexdigest()


def get_pharmacies(lang="ru"):
    endpoint = f"/api/v4/{lang}/pharmacies"
    api_key = make_api_key(endpoint)
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://arzonapteka.uz",
        "Api-Key": api_key,
    }
    resp = httpx.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=30)
    return resp.json()


def search_formdata(query, region, lang="ru"):
    endpoint = f"/api/v4/{lang}/search"
    api_key = make_api_key(endpoint)
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://arzonapteka.uz",
        "Api-Key": api_key,
    }
    form_data = {
        "user": "test-user-123",
        "search": query,
        "region": str(region),
        "country_code": "1",
        "detail": "true",
        "platform": "web",
    }
    resp = httpx.post(f"{BASE_URL}{endpoint}", data=form_data, headers=headers, timeout=30)
    return resp.json()


def search_json(ids, region="-3", lang="ru"):
    endpoint = f"/api/v4/{lang}/search"
    api_key = make_api_key(endpoint)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://arzonapteka.uz",
        "Api-Key": api_key,
    }
    data = {
        "country_code": "1",
        "platform": "web",
        "region": str(region),
        "search": ids,
        "user": "test-user-123"
    }
    resp = httpx.post(f"{BASE_URL}{endpoint}", json=data, headers=headers, timeout=30)
    return resp.json()


# PHASE 1: Get pharmacies
print("=" * 80)
print("PHASE 1: Get pharmacy list")
print("=" * 80)

result = get_pharmacies()
if result.get("ok"):
    pharmacies = result["result"]["result"]
    print(f"Total pharmacies: {len(pharmacies)}")

    # Save full list
    with open("recon_output/pharmacies_list.json", "w", encoding="utf-8") as f:
        json.dump(pharmacies, f, indent=2, ensure_ascii=False)

    # Show first few
    for ph in pharmacies[:5]:
        print(f"  [{ph['id']}] {ph['name']} - {ph['address'][:80]}")

    # Get unique regions
    # The pharmacy objects might have region info
    print(f"\n  Pharmacy keys: {list(pharmacies[0].keys())}")
    print(f"  Sample pharmacy: {json.dumps(pharmacies[0], ensure_ascii=False)[:500]}")
else:
    print(f"Error: {result}")
    pharmacies = []

# PHASE 2: Try text search with specific region codes
print(f"\n\n{'='*80}")
print("PHASE 2: Text search with specific regions")
print("="*80)

# Region codes found in data: 1726 (Tashkent city), 1727 (Tashkent region)
regions = ["1726", "1727", "1", "0"]
queries = ["тонометр", "omron", "небулайзер"]

for region in regions:
    for query in queries:
        print(f"\n  Region={region}, Query='{query}'...")
        result = search_formdata(query, region)
        if result.get("ok"):
            res = result["result"]
            if "drugstores" in res:
                print(f"    OK! {len(res['drugstores'])} drugstores")
            else:
                print(f"    OK! Keys: {list(res.keys())}")
                print(f"    Data: {json.dumps(res, ensure_ascii=False)[:300]}")
        else:
            err = result.get("error")
            if err != -3:
                print(f"    Error: {err} (new!)")

# PHASE 3: Try different search endpoint format
print(f"\n\n{'='*80}")
print("PHASE 3: Try alternate search format")
print("="*80)

# Maybe the search needs the text in search[] array with FormData
alt_headers = {
    "User-Agent": "Mozilla/5.0",
    "Origin": "https://arzonapteka.uz",
    "Api-Key": make_api_key("/api/v4/ru/search"),
    "Content-Type": "application/x-www-form-urlencoded",
}

# Try urlencoded with array-style search
import urllib.parse
for query in ["тонометр", "omron"]:
    for region in ["1726", "-3"]:
        body = urllib.parse.urlencode({
            "user": "test-user-123",
            "search": query,
            "region": region,
            "country_code": "1",
            "detail": "true",
            "platform": "web",
        })
        print(f"\n  urlencoded: search={query}, region={region}")
        try:
            resp = httpx.post(
                f"{BASE_URL}/api/v4/ru/search",
                content=body.encode(),
                headers=alt_headers,
                timeout=10
            )
            result = resp.json()
            if result.get("ok"):
                res = result["result"]
                print(f"    OK! {json.dumps(res, ensure_ascii=False)[:500]}")
            else:
                print(f"    Error: {result.get('error')}")
        except Exception as e:
            print(f"    Failed: {e}")

# PHASE 4: Try reverse lookup - search by vendor
print(f"\n\n{'='*80}")
print("PHASE 4: Search by vendor via full scan")
print("="*80)

# We'll pick random high IDs to check if medical devices exist
# Medical devices might be in a different ID range
import random
test_ranges = [
    range(50000, 50050),
    range(55000, 55050),
    range(60000, 60050),
    range(65000, 65050),
    range(70000, 70050),
    range(75000, 75050),
    range(80000, 80050),
    range(82000, 82100),
]

medical_devices = []

for r in test_ranges:
    ids = [str(i) for i in r]
    # Search in batches of 25
    for i in range(0, len(ids), 25):
        batch = ids[i:i+25]
        result = search_json(batch)
        if result.get("ok"):
            for ds in result["result"].get("drugstores", [])[:3]:
                for drug in ds.get("drugs", []):
                    name = drug["good_name"].lower()
                    vendor = drug.get("vendor_name", "").lower()
                    text = f"{name} {vendor}"
                    if any(kw in text for kw in [
                        "тонометр", "omron", "microlife", "prolife",
                        "небулайзер", "термометр", "глюкометр",
                        "beurer", "and ", "a&d", "rossmax",
                        "давлен", "артериальн", "пульсоксиметр",
                        "ингалятор", "b.well", "little doctor",
                    ]):
                        entry = {
                            "good_id": drug["good_id"],
                            "good_name": drug["good_name"],
                            "vendor_name": drug.get("vendor_name", ""),
                            "price": drug.get("price", ""),
                        }
                        if entry not in medical_devices:
                            medical_devices.append(entry)
                            print(f"  FOUND: [{drug['good_id']}] {drug['good_name']} | {drug.get('vendor_name','')}")

print(f"\n\nTotal medical devices found: {len(medical_devices)}")
with open("recon_output/medical_devices_scan.json", "w", encoding="utf-8") as f:
    json.dump(medical_devices, f, indent=2, ensure_ascii=False)
