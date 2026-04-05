"""
Scan medicine IDs from sitemap via API to find medical device products.
The API supports multiple IDs per request, so we batch them.
"""

import json
import sys
import time
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

# IDs from sitemap
ALL_IDS = [
    "10854", "2610", "2167", "44944", "10327", "2609", "13046", "3437",
    "63873", "37974", "11280", "2057", "29577", "2036", "3460", "2089",
    "11056", "46378", "2461", "10452", "10533", "11012", "7092", "3875",
    "12181", "9952", "6868", "4321", "6709", "32149", "10299", "22028",
    "4230", "3626", "22873", "11018", "4938", "51424", "3532", "9751",
    "40221", "11930", "44018", "15474", "65452", "2168", "11230", "10569",
    "13743", "11112", "9280", "11949", "10855", "3996", "63854", "3874",
    "39877", "3457", "4628", "10530", "18423", "3126", "10410", "27314",
    "16746", "15753", "3690", "2039", "2070", "9934", "3100", "3198",
    "11049", "10174", "26907", "10890", "9205", "26807", "2176", "20516",
]

# Keywords for medical devices
DEVICE_KEYWORDS = [
    "тонометр", "tonometer", "omron", "microlife", "prolife", "beurer",
    "небулайзер", "nebulizer", "ингалятор", "inhaler",
    "термометр", "thermometer",
    "глюкометр", "glucometer",
    "пульсоксиметр", "oximeter",
    "давлен", "blood pressure",
    "a&d", "and ", "rossmax", "b.well",
    "little doctor", "cs medica",
    "электронный", "цифровой", "автоматический",
    "манжет", "cuff",
    "компрессор", "compressor",
    "мед.техн", "мед. техн", "медицинск",
]


def search_ids(ids, region="-3"):
    """Search for multiple medicine IDs."""
    data = {
        "country_code": "1",
        "platform": "web",
        "region": region,
        "search": ids,
        "user": "scanner-001"
    }
    resp = httpx.post(f"{BASE_URL}/ru/search", json=data, headers=HEADERS, timeout=30)
    return resp.json()


def is_medical_device(product_name, vendor_name):
    """Check if product is likely a medical device."""
    text = f"{product_name} {vendor_name}".lower()
    return any(kw in text for kw in DEVICE_KEYWORDS)


def main():
    print("Scanning medicine IDs for medical devices...")
    print(f"Total IDs to scan: {len(ALL_IDS)}")
    print(f"Searching with keywords: {DEVICE_KEYWORDS[:10]}...")
    print()

    found_devices = []
    all_products = {}
    batch_size = 10  # IDs per API call

    for i in range(0, len(ALL_IDS), batch_size):
        batch = ALL_IDS[i:i+batch_size]
        print(f"Scanning batch {i//batch_size + 1}/{(len(ALL_IDS) + batch_size - 1)//batch_size}: IDs {batch[0]}-{batch[-1]}...")

        try:
            result = search_ids(batch)
            if result.get("ok"):
                drugstores = result["result"].get("drugstores", [])
                # Collect unique products from first few pharmacies
                seen_products = set()
                for ds in drugstores[:5]:  # Only check first 5 pharmacies
                    for drug in ds.get("drugs", []):
                        pid = drug["good_id"]
                        if pid not in seen_products:
                            seen_products.add(pid)
                            name = drug["good_name"]
                            vendor = drug.get("vendor_name", "")

                            all_products[pid] = {
                                "good_id": pid,
                                "good_name": name,
                                "vendor_name": vendor,
                                "vendor_country": drug.get("vendor_country", ""),
                                "group_id": drug.get("group_id", ""),
                                "price_example": drug.get("price", ""),
                            }

                            if is_medical_device(name, vendor):
                                found_devices.append(all_products[pid])
                                print(f"  *** DEVICE: [{pid}] {name} | {vendor}")
            else:
                print(f"  Error: {result.get('error')}")

        except Exception as e:
            print(f"  Request failed: {e}")

        time.sleep(1)  # Be polite

    # Also try a range scan for higher IDs (medical devices might have different IDs)
    print("\n\nScanning additional ID ranges...")
    # Try some ranges that might contain devices
    extra_ranges = list(range(70000, 70100)) + list(range(80000, 80100)) + list(range(60000, 60050))
    extra_ids = [str(i) for i in extra_ranges]

    for i in range(0, len(extra_ids), batch_size):
        batch = extra_ids[i:i+batch_size]
        try:
            result = search_ids(batch)
            if result.get("ok"):
                drugstores = result["result"].get("drugstores", [])
                seen = set()
                for ds in drugstores[:3]:
                    for drug in ds.get("drugs", []):
                        pid = drug["good_id"]
                        if pid not in seen:
                            seen.add(pid)
                            name = drug["good_name"]
                            vendor = drug.get("vendor_name", "")
                            all_products[pid] = {
                                "good_id": pid,
                                "good_name": name,
                                "vendor_name": vendor,
                                "vendor_country": drug.get("vendor_country", ""),
                                "group_id": drug.get("group_id", ""),
                                "price_example": drug.get("price", ""),
                            }
                            if is_medical_device(name, vendor):
                                found_devices.append(all_products[pid])
                                print(f"  *** DEVICE: [{pid}] {name} | {vendor}")
        except Exception:
            pass
        time.sleep(0.5)

    # Summary
    print(f"\n\n{'='*80}")
    print(f"SCAN COMPLETE")
    print(f"{'='*80}")
    print(f"Total products found: {len(all_products)}")
    print(f"Medical devices found: {len(found_devices)}")

    if found_devices:
        print(f"\nMedical devices:")
        for d in found_devices:
            print(f"  [{d['good_id']}] {d['good_name']}")
            print(f"    Vendor: {d['vendor_name']} ({d['vendor_country']})")
            print(f"    Price: {d['price_example']} UZS")
            print()

    # Save results
    with open("recon_output/all_products_scanned.json", "w", encoding="utf-8") as f:
        json.dump(all_products, f, indent=2, ensure_ascii=False)

    with open("recon_output/medical_devices_found.json", "w", encoding="utf-8") as f:
        json.dump(found_devices, f, indent=2, ensure_ascii=False)

    print(f"\nSaved to recon_output/all_products_scanned.json ({len(all_products)} products)")
    print(f"Saved to recon_output/medical_devices_found.json ({len(found_devices)} devices)")


if __name__ == "__main__":
    main()
