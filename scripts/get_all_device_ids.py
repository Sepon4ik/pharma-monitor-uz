"""
Use the /trigrams endpoint to get ALL medicine IDs for medical device brands.
Then verify them via the /search endpoint to get full data.
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


def trigram_search(query, lang="ru"):
    """Text search via trigrams endpoint - returns product catalog."""
    endpoint = f"/api/v4/{lang}/trigrams"
    api_key = make_api_key(endpoint)
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://arzonapteka.uz",
        "Referer": "https://arzonapteka.uz/",
        "Api-Key": api_key,
    }
    form_data = {
        "user": "scanner-004",
        "search": query,
        "region": "-3",
        "country_code": "1",
        "detail": "true",
        "platform": "web",
    }
    resp = httpx.post(f"{BASE_URL}{endpoint}", data=form_data, headers=headers, timeout=30)
    return resp.json()


def search_by_ids(ids, lang="ru"):
    """Get full pharmacy/price data by medicine IDs."""
    endpoint = f"/api/v4/{lang}/search"
    api_key = make_api_key(endpoint)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://arzonapteka.uz",
        "Api-Key": api_key,
    }
    data = {
        "country_code": "1", "platform": "web",
        "region": "-3", "search": ids, "user": "scanner-004"
    }
    resp = httpx.post(f"{BASE_URL}{endpoint}", json=data, headers=headers, timeout=60)
    return resp.json()


# Search queries to find all medical device products
search_queries = [
    # Brand searches
    "prolife", "omron", "microlife", "beurer", "b.well",
    "rossmax", "little doctor", "cs medica", "a&d", "and company",
    # Category searches
    "тонометр", "небулайзер", "ингалятор", "термометр",
    "глюкометр", "пульсоксиметр", "стетоскоп",
    "тонометр автоматический", "тонометр механический",
    "термометр электронный", "термометр инфракрасный",
    "компрессорный небулайзер",
]

all_products = {}

print("=" * 80)
print("PHASE 1: Trigram search for all medical device products")
print("=" * 80)

for query in search_queries:
    print(f"\nSearching '{query}'...")
    result = trigram_search(query)

    if result.get("ok"):
        products = result["result"]
        if isinstance(products, list):
            new_count = 0
            for prod in products:
                pid = str(prod["id"])
                if pid not in all_products:
                    all_products[pid] = {
                        "id": pid,
                        "name": prod.get("name", ""),
                        "fullname": prod.get("fullname", ""),
                        "vendor": prod.get("vendor", ""),
                        "country": prod.get("country", ""),
                        "photo_url": prod.get("photo_url", ""),
                        "search_query": query,
                    }
                    new_count += 1
            print(f"  Found {len(products)} products, {new_count} new (total: {len(all_products)})")

            # Show first few
            for prod in products[:5]:
                print(f"    [{prod['id']}] {prod.get('name', '')[:70]} | {prod.get('vendor', '')[:30]}")
            if len(products) > 5:
                print(f"    ... and {len(products) - 5} more")
        else:
            print(f"  Unexpected format: {type(products)}")
    else:
        print(f"  Error: {result.get('error')}")

# Summary
print(f"\n\n{'='*80}")
print(f"TOTAL UNIQUE PRODUCTS FOUND: {len(all_products)}")
print(f"{'='*80}")

# Categorize by brand
brands = {}
for pid, prod in all_products.items():
    text = f"{prod['name']} {prod['vendor']}".lower()
    brand = "other"
    for b in ["omron", "microlife", "prolife", "beurer", "b.well", "b. well",
              "rossmax", "little doctor", "cs medica", "a and d", "a&d"]:
        if b in text:
            brand = b.upper()
            break
    if brand not in brands:
        brands[brand] = []
    brands[brand].append(prod)

print("\nBy brand:")
for brand, products in sorted(brands.items()):
    print(f"\n  {brand} ({len(products)} products):")
    for p in products:
        print(f"    [{p['id']}] {p['name'][:70]} | {p['vendor'][:30]} ({p['country']})")

# Save catalog
with open("recon_output/device_catalog.json", "w", encoding="utf-8") as f:
    json.dump({
        "total": len(all_products),
        "brands": {k: v for k, v in brands.items()},
        "all_products": all_products,
    }, f, indent=2, ensure_ascii=False)

print(f"\nSaved to recon_output/device_catalog.json")

# PHASE 2: Get pharmacy/price data for key brands
print(f"\n\n{'='*80}")
print("PHASE 2: Get pharmacy data for key brands")
print("="*80)

key_brands = ["OMRON", "MICROLIFE", "PROLIFE", "B.WELL", "ROSSMAX", "LITTLE DOCTOR"]

for brand in key_brands:
    if brand in brands:
        brand_ids = [p["id"] for p in brands[brand]]
        print(f"\n{brand}: {len(brand_ids)} products, IDs: {brand_ids}")

        # Get pharmacy data
        result = search_by_ids(brand_ids)
        if result.get("ok"):
            drugstores = result["result"]["drugstores"]
            print(f"  Available in {len(drugstores)} pharmacies")

            # Summary per product
            product_stats = {}
            for ds in drugstores:
                for drug in ds.get("drugs", []):
                    gid = drug["good_id"]
                    if gid not in product_stats:
                        product_stats[gid] = {
                            "name": drug["good_name"],
                            "pharmacies": 0,
                            "min_price": float("inf"),
                            "max_price": 0,
                            "vendor": drug.get("vendor_name", ""),
                        }
                    product_stats[gid]["pharmacies"] += 1
                    price = int(drug["price"])
                    product_stats[gid]["min_price"] = min(product_stats[gid]["min_price"], price)
                    product_stats[gid]["max_price"] = max(product_stats[gid]["max_price"], price)

            for gid, stats in product_stats.items():
                print(f"    [{gid}] {stats['name'][:60]}")
                print(f"        Pharmacies: {stats['pharmacies']} | Price: {stats['min_price']:,}-{stats['max_price']:,} UZS")
        else:
            print(f"  Error: {result.get('error')}")

# Save full data
with open("recon_output/brand_pharmacy_data.json", "w", encoding="utf-8") as f:
    json.dump({
        "brands": {k: v for k, v in brands.items() if k in key_brands},
        "product_ids": {brand: [p["id"] for p in prods] for brand, prods in brands.items() if brand in key_brands},
    }, f, indent=2, ensure_ascii=False)
