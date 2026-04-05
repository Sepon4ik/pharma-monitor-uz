"""Distribution and pricing metrics for the dashboard."""

import sqlite3
import pandas as pd
from ..db.database import get_connection


def load_observations(conn: sqlite3.Connection = None, scrape_date: str = None) -> pd.DataFrame:
    """Load observations joined with product and pharmacy info."""
    if conn is None:
        conn = get_connection()

    date_filter = ""
    params = []
    if scrape_date:
        date_filter = "WHERE o.scrape_date = ?"
        params = [scrape_date]

    query = f"""
        SELECT
            o.scrape_date, o.price, o.count, o.last_update,
            p.good_id, p.good_name, p.brand, p.category, p.vendor_name, p.vendor_country,
            ph.pharmacy_id, ph.pharmacy_name, ph.address, ph.lat, ph.lon, ph.region,
            COALESCE(ph.chain, 'Independent') as chain
        FROM price_observations o
        JOIN products p ON o.good_id = p.good_id
        JOIN pharmacies ph ON o.pharmacy_id = ph.pharmacy_id
        {date_filter}
        ORDER BY o.scrape_date DESC
    """
    df = pd.read_sql_query(query, conn, params=params)
    return df


def get_available_dates(conn: sqlite3.Connection = None) -> list[str]:
    """Get list of dates with data."""
    if conn is None:
        conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT scrape_date FROM price_observations ORDER BY scrape_date DESC"
    ).fetchall()
    return [r[0] for r in rows]


def get_scrape_runs(conn: sqlite3.Connection = None) -> pd.DataFrame:
    if conn is None:
        conn = get_connection()
    return pd.read_sql_query("SELECT * FROM scrape_runs ORDER BY id DESC LIMIT 20", conn)


def numeric_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate numeric distribution per brand."""
    total_pharmacies = df["pharmacy_id"].nunique()
    nd = (
        df[df["price"] > 0]
        .groupby("brand")["pharmacy_id"]
        .nunique()
        .reset_index()
        .rename(columns={"pharmacy_id": "pharmacies"})
    )
    nd["total"] = total_pharmacies
    nd["nd_pct"] = (nd["pharmacies"] / total_pharmacies * 100).round(1)
    return nd.sort_values("nd_pct", ascending=False)


def sku_coverage(df: pd.DataFrame) -> pd.DataFrame:
    """Count unique SKUs per brand."""
    return (
        df[df["price"] > 0]
        .groupby("brand")
        .agg(
            unique_skus=("good_id", "nunique"),
            total_listings=("good_id", "count"),
        )
        .reset_index()
        .sort_values("unique_skus", ascending=False)
    )


def price_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Price statistics per product."""
    in_stock = df[df["price"] > 0]
    return (
        in_stock
        .groupby(["brand", "good_id", "good_name", "category"])
        .agg(
            pharmacies=("pharmacy_id", "nunique"),
            avg_price=("price", "mean"),
            min_price=("price", "min"),
            max_price=("price", "max"),
            median_price=("price", "median"),
            total_stock=("count", "sum"),
        )
        .reset_index()
        .sort_values(["brand", "pharmacies"], ascending=[True, False])
    )


def brand_scorecard(df: pd.DataFrame, exclude_other: bool = True) -> pd.DataFrame:
    """Competitive scorecard comparing all brands."""
    total_pharmacies = df["pharmacy_id"].nunique()
    in_stock = df[df["price"] > 0]

    scorecard = []
    for brand in df["brand"].unique():
        if exclude_other and brand == "Other":
            continue
        brand_data = in_stock[in_stock["brand"] == brand]
        if brand_data.empty:
            continue

        scorecard.append({
            "brand": brand,
            "products": brand_data["good_id"].nunique(),
            "pharmacies": brand_data["pharmacy_id"].nunique(),
            "nd_pct": round(brand_data["pharmacy_id"].nunique() / total_pharmacies * 100, 1),
            "avg_price": int(brand_data["price"].mean()),
            "min_price": int(brand_data["price"].min()),
            "max_price": int(brand_data["price"].max()),
            "total_stock": int(brand_data["count"].sum()),
            "avg_skus_per_pharmacy": round(
                brand_data.groupby("pharmacy_id")["good_id"].nunique().mean(), 1
            ),
        })

    return pd.DataFrame(scorecard).sort_values("pharmacies", ascending=False)


def price_comparison(df: pd.DataFrame, category: str = None) -> pd.DataFrame:
    """Price comparison across brands for same category."""
    in_stock = df[df["price"] > 0]
    if category:
        in_stock = in_stock[in_stock["category"] == category]

    return (
        in_stock
        .groupby(["brand", "category"])
        .agg(
            avg_price=("price", "mean"),
            products=("good_id", "nunique"),
            pharmacies=("pharmacy_id", "nunique"),
        )
        .reset_index()
        .sort_values(["category", "avg_price"])
    )


def top_pharmacies(df: pd.DataFrame, brand: str = None) -> pd.DataFrame:
    """Top pharmacies by number of products carried."""
    in_stock = df[df["price"] > 0]
    if brand:
        in_stock = in_stock[in_stock["brand"] == brand]

    return (
        in_stock
        .groupby(["pharmacy_id", "pharmacy_name", "address"])
        .agg(
            products=("good_id", "nunique"),
            brands=("brand", "nunique"),
            avg_price=("price", "mean"),
        )
        .reset_index()
        .sort_values("products", ascending=False)
        .head(50)
    )
