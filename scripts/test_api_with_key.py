"""
Test API with discovered api-key header.
"""

import json
import sys
import httpx

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "https://api.arzonapteka.name/api/v4"
API_KEY = "34319a8fb16208800380e63955a4a49c"

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "https://arzonapteka.uz",
    "Referer": "https://arzonapteka.uz/",
    "api-key": API_KEY,
}


def search(medicine_ids, region="-3", lang="ru"):
    url = f"{BASE_URL}/{lang}/search"
    data = {
        "country_code": "1",
        "platform": "web",
        "region": region,
        "search": medicine_ids,
        "user": "test-user-12345"
    }
    resp = httpx.post(url, json=data, headers=HEADERS, timeout=30)
    return resp.json()


# Test 1: Single medicine ID
print("="*80)
print("TEST 1: Single ID (10854)")
print("="*80)
result = search(["10854"])
if result.get("ok"):
    drugstores = result["result"]["drugstores"]
    print(f"OK! {len(drugstores)} pharmacies")
    for ds in drugstores[:3]:
        print(f"\n  Pharmacy: {ds['org_name']} ({ds['address'][:60]})")
        for drug in ds["drugs"]:
            print(f"    Product: {drug['good_name']}")
            print(f"    Price: {drug['price']} UZS | Count: {drug['count']}")
            print(f"    Vendor: {drug['vendor_name']}")
            print(f"    Updated: {drug['last_update']}")
else:
    print(f"Error: {result}")

# Test 2: Multiple IDs
print("\n" + "="*80)
print("TEST 2: Multiple IDs")
print("="*80)
result2 = search(["10854", "2610", "2167"])
if result2.get("ok"):
    drugstores = result2["result"]["drugstores"]
    print(f"OK! {len(drugstores)} pharmacies")
    products = set()
    for ds in drugstores:
        for drug in ds.get("drugs", []):
            products.add(f"{drug['good_name']} ({drug['vendor_name']})")
    print(f"Unique products: {len(products)}")
    for p in sorted(products):
        print(f"  - {p}")
else:
    print(f"Error: {result2}")

# Test 3: Text search
print("\n" + "="*80)
print("TEST 3: Text search 'omron'")
print("="*80)
result3 = search(["omron"])
print(f"Result: {json.dumps(result3, ensure_ascii=False)[:300]}")

# Test 4: Text search 'тонометр'
print("\n" + "="*80)
print("TEST 4: Text search 'тонометр'")
print("="*80)
result4 = search(["тонометр"])
print(f"Result: {json.dumps(result4, ensure_ascii=False)[:300]}")

# Test 5: Regions
print("\n" + "="*80)
print("TEST 5: Regions endpoint")
print("="*80)
for endpoint in ["regions", "pharmacies"]:
    url = f"{BASE_URL}/ru/{endpoint}"
    resp = httpx.post(url, json={"country_code": "1", "platform": "web"}, headers=HEADERS, timeout=10)
    print(f"\n[POST] {endpoint}: {resp.status_code}")
    try:
        data = resp.json()
        print(f"  {json.dumps(data, ensure_ascii=False)[:500]}")
    except Exception:
        print(f"  {resp.text[:200]}")

# Test 6: Try with GET
print("\n" + "="*80)
print("TEST 6: GET regions")
print("="*80)
resp = httpx.get(f"{BASE_URL}/ru/regions", headers=HEADERS, timeout=10)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:500]}")

# Test 7: Save full response for single ID
print("\n" + "="*80)
print("TEST 7: Full response structure")
print("="*80)
result7 = search(["10854"], region="-3")
if result7.get("ok"):
    with open("recon_output/api_response_10854.json", "w", encoding="utf-8") as f:
        json.dump(result7, f, indent=2, ensure_ascii=False)
    print(f"Saved full response ({len(json.dumps(result7))} chars)")
    print(f"Token: {result7['result'].get('token')}")
    print(f"Drugstores: {len(result7['result']['drugstores'])}")

    # Analyze structure
    ds = result7["result"]["drugstores"][0]
    print(f"\nDrugstore fields: {list(ds.keys())}")
    print(f"Drug fields: {list(ds['drugs'][0].keys())}")
