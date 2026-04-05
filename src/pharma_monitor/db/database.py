"""SQLite database layer for storing scrape data."""

import sqlite3
from datetime import datetime, date
from pathlib import Path
from ..config import DB_PATH


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path = DB_PATH):
    """Create tables if they don't exist."""
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            good_id TEXT PRIMARY KEY,
            good_name TEXT NOT NULL,
            vendor_name TEXT,
            vendor_country TEXT,
            brand TEXT,
            category TEXT,
            photo_url TEXT,
            first_seen DATE,
            last_seen DATE
        );

        CREATE TABLE IF NOT EXISTS pharmacies (
            pharmacy_id TEXT PRIMARY KEY,
            pharmacy_name TEXT NOT NULL,
            address TEXT,
            lat TEXT,
            lon TEXT,
            region TEXT,
            phone TEXT,
            first_seen DATE,
            last_seen DATE
        );

        CREATE TABLE IF NOT EXISTS price_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scrape_date DATE NOT NULL,
            good_id TEXT NOT NULL,
            pharmacy_id TEXT NOT NULL,
            price INTEGER NOT NULL,
            count INTEGER DEFAULT 0,
            last_update TEXT,
            FOREIGN KEY (good_id) REFERENCES products(good_id),
            FOREIGN KEY (pharmacy_id) REFERENCES pharmacies(pharmacy_id),
            UNIQUE(scrape_date, good_id, pharmacy_id)
        );

        CREATE TABLE IF NOT EXISTS scrape_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT DEFAULT 'running',
            products_count INTEGER DEFAULT 0,
            observations_count INTEGER DEFAULT 0,
            pharmacies_count INTEGER DEFAULT 0,
            error TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_obs_date ON price_observations(scrape_date);
        CREATE INDEX IF NOT EXISTS idx_obs_product ON price_observations(good_id);
        CREATE INDEX IF NOT EXISTS idx_obs_pharmacy ON price_observations(pharmacy_id);
        CREATE INDEX IF NOT EXISTS idx_obs_date_product ON price_observations(scrape_date, good_id);
        CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand);
        CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
    """)
    conn.commit()
    conn.close()


def upsert_product(conn: sqlite3.Connection, product: dict):
    today = date.today().isoformat()
    conn.execute("""
        INSERT INTO products (good_id, good_name, vendor_name, vendor_country, brand, category, photo_url, first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(good_id) DO UPDATE SET
            good_name = excluded.good_name,
            vendor_name = excluded.vendor_name,
            brand = excluded.brand,
            category = excluded.category,
            last_seen = excluded.last_seen
    """, (
        product["good_id"], product["good_name"],
        product.get("vendor_name", ""), product.get("vendor_country", ""),
        product.get("brand", ""), product.get("category", ""),
        product.get("photo_url", ""),
        today, today,
    ))


def upsert_pharmacy(conn: sqlite3.Connection, pharmacy: dict):
    today = date.today().isoformat()
    conn.execute("""
        INSERT INTO pharmacies (pharmacy_id, pharmacy_name, address, lat, lon, region, phone, first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(pharmacy_id) DO UPDATE SET
            pharmacy_name = excluded.pharmacy_name,
            address = excluded.address,
            last_seen = excluded.last_seen
    """, (
        pharmacy["pharmacy_id"], pharmacy["pharmacy_name"],
        pharmacy.get("address", ""), pharmacy.get("lat", ""),
        pharmacy.get("lon", ""), pharmacy.get("region", ""),
        pharmacy.get("phone", ""),
        today, today,
    ))


def insert_observation(conn: sqlite3.Connection, obs: dict, scrape_date: str):
    conn.execute("""
        INSERT OR REPLACE INTO price_observations (scrape_date, good_id, pharmacy_id, price, count, last_update)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        scrape_date, obs["good_id"], obs["pharmacy_id"],
        obs["price"], obs["count"], obs.get("last_update", ""),
    ))


def start_scrape_run(conn: sqlite3.Connection) -> int:
    cursor = conn.execute(
        "INSERT INTO scrape_runs (started_at) VALUES (?)",
        (datetime.now().isoformat(),)
    )
    conn.commit()
    return cursor.lastrowid


def finish_scrape_run(conn: sqlite3.Connection, run_id: int, stats: dict, error: str = None):
    conn.execute("""
        UPDATE scrape_runs SET
            finished_at = ?,
            status = ?,
            products_count = ?,
            observations_count = ?,
            pharmacies_count = ?,
            error = ?
        WHERE id = ?
    """, (
        datetime.now().isoformat(),
        "error" if error else "done",
        stats.get("products", 0),
        stats.get("observations", 0),
        stats.get("pharmacies", 0),
        error,
        run_id,
    ))
    conn.commit()
