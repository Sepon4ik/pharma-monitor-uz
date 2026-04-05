"""
Targeted scan: check specific IDs and do a precise scan around known devices.
Also try to cover gaps in previous scan.
"""

import hashlib
import json
import sys
import time
import httpx

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "https://api.arzonapteka.name"
SECRET = "Nx3WWr"


def make_api_key(endpoint):
    raw = f"{BASE_URL}{endpoint}{SECRET}"
    return hashlib.md5(raw.encode()).hexdigest()


def search(ids, region="-3"):
    endpoint = "/api/v4/ru/search"
    api_key = make_api_key(endpoint)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://arzonapteka.uz",
        "Api-Key": api_key,
    }
    data = {
        "country_code": "1", "platform": "web",
        "region": str(region), "search": ids, "user": "scan-003"
    }
    resp = httpx.post(f"{BASE_URL}{endpoint}", json=data, headers=headers, timeout=60)
    return resp.json()


# 1. Verify B.Well at 75027
print("=" * 60)
print("1. Verifying B.Well tonometer at ID 75027")
print("=" * 60)

result = search(["75027"])
if result.get("ok"):
    ds = result["result"]["drugstores"]
    print(f"  Pharmacies: {len(ds)}")
    if ds:
        for drug in ds[0]["drugs"]:
            print(f"  Product: {drug['good_name']}")
            print(f"  Vendor: {drug['vendor_name']}")
            print(f"  Price: {drug['price']} UZS")
else:
    print(f"  Error: {result}")

# 2. Scan precisely around 75027 (75000-75100)
print(f"\n{'='*60}")
print("2. Scanning 74900-75200 precisely")
print("="*60)

devices = []
for start in range(74900, 75200, 50):
    batch = [str(i) for i in range(start, start + 50)]
    result = search(batch)
    if result.get("ok"):
        seen = set()
        for ds in result["result"].get("drugstores", [])[:10]:
            for drug in ds.get("drugs", []):
                gid = drug["good_id"]
                if gid not in seen:
                    seen.add(gid)
                    devices.append({
                        "id": gid,
                        "name": drug["good_name"],
                        "vendor": drug.get("vendor_name", ""),
                    })
                    print(f"  [{gid}] {drug['good_name'][:80]} | {drug.get('vendor_name','')[:40]}")
    time.sleep(0.3)

# 3. Full coverage: scan ALL remaining ranges
# Previous scan covered: 70000-85000, 2000-5000, 10000-15000, 40000-45000, 85000-90000
# Missing: 5000-10000, 15000-40000, 45000-70000
print(f"\n{'='*60}")
print("3. Scanning missing ranges for devices")
print("="*60)

all_found = {}
KEYWORDS = [
    "тонометр", "omron", "microlife", "prolife", "небулайзер",
    "ингалятор", "термометр", "глюкометр", "пульсоксиметр",
    "beurer", "rossmax", "b.well", "little doctor", "cs medica",
    "and ua", "давлен", "манжет", "электронн", "автоматическ",
    "тест-полоск", "ланцет", "стетоскоп",
]

missing_ranges = [
    (5000, 10000),
    (15000, 25000),
    (25000, 35000),
    (35000, 40000),
    (45000, 55000),
    (55000, 65000),
    (65000, 70000),
]

for range_start, range_end in missing_ranges:
    print(f"\n  Scanning {range_start}-{range_end}...")
    for start in range(range_start, range_end, 50):
        batch = [str(i) for i in range(start, min(start + 50, range_end))]
        try:
            result = search(batch)
            if result.get("ok"):
                seen = set()
                for ds in result["result"].get("drugstores", [])[:5]:
                    for drug in ds.get("drugs", []):
                        gid = drug["good_id"]
                        if gid in seen or gid in all_found:
                            continue
                        seen.add(gid)
                        name_lower = f"{drug['good_name']} {drug.get('vendor_name','')}".lower()
                        if any(kw in name_lower for kw in KEYWORDS):
                            all_found[gid] = {
                                "id": gid,
                                "name": drug["good_name"],
                                "vendor": drug.get("vendor_name", ""),
                                "price": drug.get("price", ""),
                            }
                            print(f"    [{gid}] {drug['good_name'][:70]} | {drug.get('vendor_name','')[:30]}")
        except Exception as e:
            pass
        time.sleep(0.2)

    print(f"  ...done, total found: {len(all_found)}")

# Summary
print(f"\n\n{'='*60}")
print(f"TOTAL DEVICES FOUND: {len(all_found)}")
print("="*60)

for gid, d in sorted(all_found.items()):
    brand = ""
    text = f"{d['name']} {d['vendor']}".lower()
    for b in ["omron", "microlife", "prolife", "beurer", "b.well", "rossmax"]:
        if b in text:
            brand = b.upper()
    print(f"  [{gid}] {d['name'][:80]} | {d['vendor'][:30]} {brand}")

with open("recon_output/targeted_devices.json", "w", encoding="utf-8") as f:
    json.dump(list(all_found.values()), f, indent=2, ensure_ascii=False)
