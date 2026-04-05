"""Main scraper orchestrator — discovers products, collects prices, saves to DB."""

import sys
from datetime import date

from .config import TRACKED_BRANDS, classify_product, detect_brand
from .scrapers.arzonapteka import ArzonAptekaClient
from .db.database import (
    get_connection, init_db, upsert_product, upsert_pharmacy,
    insert_observation, start_scrape_run, finish_scrape_run,
)


def run_scrape(verbose: bool = True):
    """Run a full scrape cycle."""
    init_db()
    client = ArzonAptekaClient()
    conn = get_connection()
    run_id = start_scrape_run(conn)
    today = date.today().isoformat()

    try:
        # Phase 1: Discover products via trigram search
        if verbose:
            print("Phase 1: Discovering products...")
        all_queries = []
        for brand, queries in TRACKED_BRANDS.items():
            all_queries.extend(queries)
        # Also search by category
        all_queries.extend(["тонометр", "небулайзер", "ингалятор", "термометр",
                           "глюкометр", "пульсоксиметр", "стетоскоп"])

        catalog = client.discover_products(all_queries)
        if verbose:
            print(f"  Found {len(catalog)} unique products")

        # Save products to DB
        for pid, prod in catalog.items():
            brand = detect_brand(prod["name"], prod.get("vendor", ""))
            category = classify_product(prod["name"])
            upsert_product(conn, {
                "good_id": pid,
                "good_name": prod["name"],
                "vendor_name": prod.get("vendor", ""),
                "vendor_country": prod.get("country", ""),
                "brand": brand,
                "category": category,
                "photo_url": prod.get("photo_url", ""),
            })
        conn.commit()

        # Phase 2: Get pharmacy/price data for all products
        if verbose:
            print("Phase 2: Collecting prices and availability...")
        medicine_ids = list(catalog.keys())
        observations = client.get_prices_for_products(medicine_ids)
        if verbose:
            print(f"  Collected {len(observations)} price observations")

        # Save observations
        pharmacies_seen = set()
        for obs in observations:
            # Upsert pharmacy
            ph_id = obs["pharmacy_id"]
            if ph_id not in pharmacies_seen:
                upsert_pharmacy(conn, {
                    "pharmacy_id": ph_id,
                    "pharmacy_name": obs["pharmacy_name"],
                    "address": obs["pharmacy_address"],
                    "lat": obs["pharmacy_lat"],
                    "lon": obs["pharmacy_lon"],
                    "region": obs["pharmacy_region"],
                    "phone": obs["pharmacy_phone"],
                })
                pharmacies_seen.add(ph_id)

            # Insert price observation
            insert_observation(conn, obs, today)

        conn.commit()

        stats = {
            "products": len(catalog),
            "observations": len(observations),
            "pharmacies": len(pharmacies_seen),
        }
        finish_scrape_run(conn, run_id, stats)

        if verbose:
            print(f"\nScrape complete!")
            print(f"  Products: {stats['products']}")
            print(f"  Pharmacies: {stats['pharmacies']}")
            print(f"  Observations: {stats['observations']}")

        return stats

    except Exception as e:
        finish_scrape_run(conn, run_id, {}, str(e))
        raise
    finally:
        client.close()
        conn.close()


if __name__ == "__main__":
    run_scrape()
