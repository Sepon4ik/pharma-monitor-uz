"""
Full scan for medical devices in the arzonapteka database.
Focus on ID ranges 70000-85000 where devices are likely located.
Use large batches for efficiency.
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


def search_json(ids, region="-3", lang="ru"):
    endpoint = f"/api/v4/{lang}/search"
    api_key = make_api_key(endpoint)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://arzonapteka.uz",
        "Api-Key": api_key,
    }
    data = {
        "country_code": "1",
        "platform": "web",
        "region": str(region),
        "search": ids,
        "user": "scanner-002"
    }
    resp = httpx.post(f"{BASE_URL}{endpoint}", json=data, headers=headers, timeout=60)
    return resp.json()


DEVICE_KEYWORDS = [
    "тонометр", "tonometer", "omron", "microlife", "prolife",
    "небулайзер", "nebulizer", "ингалятор", "inhaler",
    "термометр", "thermometer",
    "глюкометр", "glucometer",
    "пульсоксиметр", "oximeter",
    "давлен", "blood pressure",
    "beurer", "rossmax", "b.well", "b. well",
    "little doctor", "cs medica",
    "and ua-", "and dt-", "and ub-",
    "электронн", "автоматическ",
    "манжет", "тест-полоск", "ланцет",
    "компрессорн", "мед.техн", "мед. тех",
    "массаж", "ирригатор", "стетоскоп",
    "бандаж", "корсет", "ортопед",
]

all_devices = {}
batch_size = 50

# Scan ranges where devices are likely
# We found B.Well at 75027, so let's scan 70000-85000 comprehensively
scan_ranges = [
    (70000, 85000),  # Main device range
    (2000, 5000),    # Low range (might have some old devices)
    (10000, 15000),  # Mid range
    (40000, 45000),  # Mid-high range
    (85000, 90000),  # High range
]

total_scanned = 0

for range_start, range_end in scan_ranges:
    print(f"\n{'='*60}")
    print(f"Scanning range {range_start}-{range_end}...")
    print(f"{'='*60}")

    for start in range(range_start, range_end, batch_size):
        batch = [str(i) for i in range(start, min(start + batch_size, range_end))]
        total_scanned += len(batch)

        try:
            result = search_json(batch)
            if result.get("ok"):
                seen_ids = set()
                for ds in result["result"].get("drugstores", [])[:5]:
                    for drug in ds.get("drugs", []):
                        gid = drug["good_id"]
                        if gid in seen_ids:
                            continue
                        seen_ids.add(gid)

                        name = drug["good_name"].lower()
                        vendor = drug.get("vendor_name", "").lower()
                        text = f"{name} {vendor}"

                        if any(kw in text for kw in DEVICE_KEYWORDS):
                            if gid not in all_devices:
                                all_devices[gid] = {
                                    "good_id": gid,
                                    "good_name": drug["good_name"],
                                    "vendor_name": drug.get("vendor_name", ""),
                                    "vendor_country": drug.get("vendor_country", ""),
                                    "group_id": drug.get("group_id", ""),
                                    "price": drug.get("price", ""),
                                    "is_prescription": drug.get("is_prescription", ""),
                                }
                                print(f"  [{gid}] {drug['good_name'][:70]} | {drug.get('vendor_name','')[:40]}")
        except Exception as e:
            print(f"  Error at {start}: {str(e)[:100]}")

        # Progress every 500 IDs
        if (start - range_start) % 500 == 0 and start > range_start:
            print(f"  ...scanned {start - range_start}/{range_end - range_start}, found {len(all_devices)} devices so far")

        time.sleep(0.3)  # Be polite

print(f"\n\n{'='*80}")
print(f"SCAN COMPLETE")
print(f"{'='*80}")
print(f"Total IDs scanned: {total_scanned}")
print(f"Medical devices found: {len(all_devices)}")

# Categorize by type
categories = {
    "tonometer": [],
    "nebulizer": [],
    "thermometer": [],
    "glucometer": [],
    "oximeter": [],
    "other": [],
}

for gid, device in sorted(all_devices.items()):
    name = device["good_name"].lower()
    if "тонометр" in name or "давлен" in name:
        categories["tonometer"].append(device)
    elif "небулайзер" in name or "ингалятор" in name or "компрессорн" in name:
        categories["nebulizer"].append(device)
    elif "термометр" in name:
        categories["thermometer"].append(device)
    elif "глюкометр" in name or "тест-полоск" in name or "ланцет" in name:
        categories["glucometer"].append(device)
    elif "пульсоксиметр" in name or "оксиметр" in name:
        categories["oximeter"].append(device)
    else:
        categories["other"].append(device)

print("\nBy category:")
for cat, devices in categories.items():
    print(f"\n  {cat.upper()} ({len(devices)}):")
    for d in devices:
        brand = ""
        name_lower = d["good_name"].lower()
        vendor_lower = d.get("vendor_name", "").lower()
        for b in ["omron", "microlife", "prolife", "beurer", "b.well", "rossmax", "and ", "little doctor", "cs medica"]:
            if b in name_lower or b in vendor_lower:
                brand = b.upper()
                break
        print(f"    [{d['good_id']}] {d['good_name'][:80]} [{brand}] {d.get('price','')} UZS")

# Save
with open("recon_output/all_medical_devices.json", "w", encoding="utf-8") as f:
    json.dump({
        "total": len(all_devices),
        "categories": {k: v for k, v in categories.items()},
        "all_devices": list(all_devices.values()),
    }, f, indent=2, ensure_ascii=False)

print(f"\nSaved to recon_output/all_medical_devices.json")
