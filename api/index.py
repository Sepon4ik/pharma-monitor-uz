"""FastAPI dashboard for Pharma Monitor — Vercel-compatible."""

import json
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote, unquote

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.pharma_monitor.config import DB_PATH
from src.pharma_monitor.analytics.metrics import (
    load_observations, get_available_dates, get_scrape_runs,
    numeric_distribution, sku_coverage, price_summary,
    brand_scorecard,
)

app = FastAPI()


@app.get("/debug")
def debug():
    """Diagnostic endpoint."""
    import os
    root = str(PROJECT_ROOT)
    return {
        "project_root": root,
        "root_exists": os.path.isdir(root),
        "root_contents": os.listdir(root) if os.path.isdir(root) else [],
        "templates_exists": os.path.isdir(str(PROJECT_ROOT / "templates")),
        "static_exists": os.path.isdir(str(PROJECT_ROOT / "static")),
        "db_path": str(DB_PATH),
        "db_exists": os.path.isfile(str(DB_PATH)),
        "data_dir_exists": os.path.isdir(str(PROJECT_ROOT / "data")),
        "data_contents": os.listdir(str(PROJECT_ROOT / "data")) if os.path.isdir(str(PROJECT_ROOT / "data")) else [],
        "cwd": os.getcwd(),
    }


# Mount static files
app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "static")), name="static")

# Templates
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))
templates.env.filters["quote"] = lambda s: quote(str(s), safe="")


def render(request: Request, name: str, context: dict):
    """Render template with Starlette 1.0 compatible signature."""
    return templates.TemplateResponse(name=name, request=request, context=context)


def get_db():
    """Get read-only DB connection (Vercel has read-only filesystem)."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def common_context(request: Request, conn, selected_date: str = None):
    """Build context shared across all pages."""
    dates = get_available_dates(conn)
    if not selected_date and dates:
        selected_date = dates[0]

    runs_df = get_scrape_runs(conn)
    runs = runs_df.head(5).to_dict("records") if not runs_df.empty else []

    return {
        "dates": dates,
        "selected_date": selected_date,
        "runs": runs,
    }


MAIN_BRANDS = [
    "Prolife", "OMRON", "Microlife", "B.Well", "Beurer", "Rossmax",
    "Little Doctor", "A&D", "Citizen", "YUWELL", "KD Medical", "Amrus",
    "Accu-Chek", "OneTouch", "Dr.Frei", "MediTech", "Braun", "Medico", "CS Medica",
]


@app.get("/", response_class=RedirectResponse)
def root():
    return RedirectResponse(url="/overview")


@app.get("/overview")
def overview(request: Request, date: str = None):
    try:
        conn = get_db()
        ctx = common_context(request, conn, date)
        selected_date = ctx["selected_date"]

        if not selected_date:
            conn.close()
            return render(request, "overview.html", {**ctx, "has_data": False})

        df_raw = load_observations(conn, selected_date)
        conn.close()

        if df_raw.empty:
            return render(request, "overview.html", {**ctx, "has_data": False})

        df = df_raw[df_raw["brand"] != "Other"]
        in_stock = df[df["price"] > 0]

        # KPIs
        kpis = {
            "products": int(in_stock["good_id"].nunique()),
            "pharmacies": int(in_stock["pharmacy_id"].nunique()),
            "brands": int(in_stock["brand"].nunique()),
            "observations": int(len(in_stock)),
            "avg_price": int(in_stock["price"].mean()) if len(in_stock) > 0 else 0,
        }

        # Scorecard
        sc = brand_scorecard(df)
        scorecard_data = sc.to_dict("records") if not sc.empty else []
        scorecard_labels = json.dumps([r["brand"] for r in scorecard_data])
        scorecard_pharmacies = json.dumps([int(r["pharmacies"]) for r in scorecard_data])

        # Numeric distribution
        nd = numeric_distribution(df)
        nd_data = nd.to_dict("records") if not nd.empty else []
        nd_labels = json.dumps([r["brand"] for r in nd_data])
        nd_values = json.dumps([float(r["nd_pct"]) for r in nd_data])

        # SKU coverage
        skus = sku_coverage(df)
        sku_data = skus.to_dict("records") if not skus.empty else []
        sku_labels = json.dumps([r["brand"] for r in sku_data])
        sku_values = json.dumps([int(r["unique_skus"]) for r in sku_data])

        # Price summary
        prices = price_summary(df)
        price_data = prices.to_dict("records") if not prices.empty else []
        categories = sorted(prices["category"].unique().tolist()) if not prices.empty else []

        # Price box data (min/avg/max per brand)
        price_box = (
            in_stock.groupby("brand")["price"]
            .agg(["min", "mean", "max"])
            .reset_index()
            .sort_values("mean", ascending=False)
            .head(15)
        )
        price_box_labels = json.dumps(price_box["brand"].tolist())
        price_box_min = json.dumps(price_box["min"].astype(int).tolist())
        price_box_avg = json.dumps(price_box["mean"].astype(int).tolist())
        price_box_max = json.dumps(price_box["max"].astype(int).tolist())

        # Distribution gaps
        prolife_pharms = set(in_stock[in_stock["brand"] == "Prolife"]["pharmacy_id"])
        competitor_data = in_stock[
            (in_stock["brand"].isin(["OMRON", "Microlife", "B.Well"])) &
            (~in_stock["pharmacy_id"].isin(prolife_pharms))
        ]
        gaps = []
        if not competitor_data.empty:
            gap_df = (
                competitor_data.groupby(["pharmacy_id", "pharmacy_name", "address"])
                .agg(competitor_brands=("brand", lambda x: ", ".join(sorted(x.unique()))))
                .reset_index()
            )
            gaps = gap_df.head(50).to_dict("records")

        return render(request, "overview.html", {
            **ctx, "has_data": True, "kpis": kpis,
            "scorecard_data": scorecard_data,
            "scorecard_labels": scorecard_labels,
            "scorecard_pharmacies": scorecard_pharmacies,
            "nd_labels": nd_labels, "nd_values": nd_values,
            "sku_labels": sku_labels, "sku_values": sku_values,
            "price_data": price_data, "categories": categories,
            "price_box_labels": price_box_labels,
            "price_box_min": price_box_min,
            "price_box_avg": price_box_avg,
            "price_box_max": price_box_max,
            "gaps": gaps, "gap_count": len(gaps),
        })
    except Exception as e:
        import traceback
        return JSONResponse({"error": str(e), "traceback": traceback.format_exc()}, status_code=500)


@app.get("/brands")
def brands_page(request: Request, date: str = None):
    conn = get_db()
    ctx = common_context(request, conn, date)
    selected_date = ctx["selected_date"]

    if not selected_date:
        conn.close()
        return render(request,"brands.html", {**ctx, "has_data": False, "brand_cards": [], "other_brands": []})

    df_raw = load_observations(conn, selected_date)
    conn.close()
    df = df_raw[df_raw["brand"] != "Other"]

    sc = brand_scorecard(df)
    brand_cards = []
    for brand in MAIN_BRANDS:
        row = sc[sc["brand"] == brand]
        if row.empty:
            continue
        r = row.iloc[0]
        brand_cards.append({
            "brand": brand,
            "products": int(r["products"]),
            "pharmacies": int(r["pharmacies"]),
            "nd_pct": round(float(r["nd_pct"]), 1),
            "avg_price": int(r["avg_price"]),
            "total_stock": int(r["total_stock"]),
        })

    other_brands = sc[~sc["brand"].isin(MAIN_BRANDS)].to_dict("records")

    return render(request,"brands.html", {
        **ctx, "has_data": True,
        "brand_cards": brand_cards, "other_brands": other_brands,
    })


@app.get("/brands/{brand_name}", response_class=HTMLResponse)
def brand_detail(request: Request, brand_name: str, date: str = None, product: str = None):
    conn = get_db()
    ctx = common_context(request, conn, date)
    selected_date = ctx["selected_date"]
    brand = unquote(brand_name)

    if not selected_date:
        conn.close()
        return render(request,"brand_detail.html", {**ctx, "has_data": False, "brand": brand})

    df_raw = load_observations(conn, selected_date)
    conn.close()
    df = df_raw[df_raw["brand"] != "Other"]
    in_stock = df[df["price"] > 0]
    brand_df = in_stock[in_stock["brand"] == brand]

    if brand_df.empty:
        return render(request,"brand_detail.html", {**ctx, "has_data": False, "brand": brand})

    total_pharm = in_stock["pharmacy_id"].nunique()
    nd = brand_df["pharmacy_id"].nunique() / total_pharm * 100 if total_pharm > 0 else 0

    brand_kpis = {
        "products": int(brand_df["good_id"].nunique()),
        "pharmacies": int(brand_df["pharmacy_id"].nunique()),
        "distribution": round(nd, 1),
        "total_stock": int(brand_df["count"].sum()),
    }

    products = (
        brand_df
        .groupby(["good_id", "good_name", "category", "vendor_name"])
        .agg(pharmacies=("pharmacy_id", "nunique"), avg_price=("price", "mean"),
             min_price=("price", "min"), max_price=("price", "max"), total_stock=("count", "sum"))
        .reset_index().sort_values("pharmacies", ascending=False)
    )
    product_names = products["good_name"].tolist()

    if product:
        product = unquote(product)
    if not product or product not in product_names:
        product = product_names[0] if product_names else None

    pharmacy_list = []
    product_kpis = {}
    cheapest_labels = "[]"
    cheapest_prices = "[]"
    map_points = "[]"

    if product:
        product_df = brand_df[brand_df["good_name"] == product]
        pl = (
            product_df
            .groupby(["pharmacy_id", "pharmacy_name", "address", "lat", "lon"])
            .agg(price=("price", "first"), stock=("count", "first"), last_update=("last_update", "first"))
            .reset_index().sort_values("price")
        )
        pharmacy_list = pl.to_dict("records")

        product_kpis = {
            "pharmacies": len(pl),
            "min_price": int(pl["price"].min()) if len(pl) > 0 else 0,
            "avg_price": int(pl["price"].mean()) if len(pl) > 0 else 0,
            "max_price": int(pl["price"].max()) if len(pl) > 0 else 0,
            "total_stock": int(pl["stock"].sum()),
        }

        cheapest = pl.nsmallest(10, "price")
        cheapest_labels = json.dumps(cheapest["pharmacy_name"].str[:35].tolist())
        cheapest_prices = json.dumps(cheapest["price"].astype(int).tolist())

        import pandas as pd
        map_df = pl.copy()
        map_df["lat"] = pd.to_numeric(map_df["lat"], errors="coerce")
        map_df["lon"] = pd.to_numeric(map_df["lon"], errors="coerce")
        map_df = map_df.dropna(subset=["lat", "lon"])
        median_price = pl["price"].median() if len(pl) > 0 else 0
        points = []
        for _, row in map_df.iterrows():
            points.append({
                "lat": float(row["lat"]), "lon": float(row["lon"]),
                "name": row["pharmacy_name"], "address": str(row["address"])[:80],
                "price": int(row["price"]), "stock": int(row["stock"]),
                "cheap": bool(row["price"] <= median_price),
            })
        map_points = json.dumps(points)

    all_products = products.to_dict("records")

    return render(request,"brand_detail.html", {
        **ctx, "has_data": True, "brand": brand,
        "brand_kpis": brand_kpis, "product_names": product_names,
        "selected_product": product, "product_kpis": product_kpis,
        "pharmacy_list": pharmacy_list, "all_products": all_products,
        "cheapest_labels": cheapest_labels, "cheapest_prices": cheapest_prices,
        "map_points": map_points,
    })


@app.get("/chains", response_class=HTMLResponse)
def chains_page(request: Request, date: str = None, brand: str = None,
                compare: list[str] = Query(default=None)):
    conn = get_db()
    ctx = common_context(request, conn, date)
    selected_date = ctx["selected_date"]

    if not selected_date:
        conn.close()
        return render(request,"chains.html", {**ctx, "has_data": False})

    df_raw = load_observations(conn, selected_date)
    conn.close()
    df = df_raw[df_raw["brand"] != "Other"]
    in_stock = df[df["price"] > 0]

    all_brand_names = sorted(in_stock["brand"].unique().tolist())
    if not brand:
        brand = "Prolife" if "Prolife" in all_brand_names else (all_brand_names[0] if all_brand_names else "")

    brand_data = in_stock[in_stock["brand"] == brand]
    chains_only = in_stock[in_stock["chain"] != "Independent"]
    all_chains = sorted(chains_only["chain"].unique().tolist())

    chain_stats = []
    for chain in all_chains:
        chain_pharmacies = in_stock[in_stock["chain"] == chain]["pharmacy_id"].nunique()
        brand_in_chain = brand_data[brand_data["chain"] == chain]
        brand_pharmacies = brand_in_chain["pharmacy_id"].nunique()
        brand_products = brand_in_chain["good_id"].nunique()
        product_list = ", ".join(sorted(brand_in_chain["good_name"].unique())[:5])
        chain_stats.append({
            "chain": chain, "total": chain_pharmacies,
            "present": brand_pharmacies,
            "coverage": round(brand_pharmacies / chain_pharmacies * 100) if chain_pharmacies > 0 else 0,
            "products": brand_products, "product_names": product_list[:100],
        })
    chain_stats.sort(key=lambda x: x["present"], reverse=True)

    total_chain_pharm = chains_only["pharmacy_id"].nunique()
    brand_in_chains = brand_data[brand_data["chain"] != "Independent"]["pharmacy_id"].nunique()
    chains_with = sum(1 for c in chain_stats if c["present"] > 0)
    chains_without = sum(1 for c in chain_stats if c["present"] == 0)
    chain_pct = round(brand_in_chains / total_chain_pharm * 100, 1) if total_chain_pharm > 0 else 0

    chain_kpis = {
        "chains_with": f"{chains_with}/{len(all_chains)}",
        "covered": f"{brand_in_chains}/{total_chain_pharm}",
        "coverage_pct": f"{chain_pct}%",
        "chains_without": chains_without,
    }

    top20 = chain_stats[:20]
    coverage_labels = json.dumps([c["chain"] for c in top20])
    coverage_total = json.dumps([c["total"] for c in top20])
    coverage_present = json.dumps([c["present"] for c in top20])

    # Competitor comparison
    if not compare:
        compare = ["Prolife", "OMRON", "B.Well", "Microlife"]
    compare = [b for b in compare if b in all_brand_names]

    pivot_data = []
    for chain in all_chains:
        row = {"chain": chain, "size": in_stock[in_stock["chain"] == chain]["pharmacy_id"].nunique()}
        for b in compare:
            bc = in_stock[(in_stock["brand"] == b) & (in_stock["chain"] == chain)]
            row[b] = bc["pharmacy_id"].nunique()
        pivot_data.append(row)
    pivot_data.sort(key=lambda x: x["size"], reverse=True)

    compare_json = json.dumps({
        "labels": [p["chain"] for p in pivot_data[:25]],
        "datasets": [{"label": b, "data": [p.get(b, 0) for p in pivot_data[:25]]} for b in compare],
    })

    # Gap analysis
    brand_chains_set = set(brand_data[brand_data["chain"] != "Independent"]["chain"].unique())
    gap_chains = []
    for chain in all_chains:
        if chain in brand_chains_set:
            continue
        cd = in_stock[in_stock["chain"] == chain]
        competitors = cd[cd["brand"] != "Other"]["brand"].unique()
        if len(competitors) > 0:
            gap_chains.append({
                "chain": chain,
                "pharmacies": cd["pharmacy_id"].nunique(),
                "competitors": ", ".join(sorted(competitors)),
                "products": cd["good_id"].nunique(),
            })
    gap_chains.sort(key=lambda x: x["pharmacies"], reverse=True)

    return render(request,"chains.html", {
        **ctx, "has_data": True,
        "brand": brand, "all_brands": all_brand_names,
        "chain_stats": chain_stats, "chain_kpis": chain_kpis,
        "coverage_labels": coverage_labels,
        "coverage_total": coverage_total,
        "coverage_present": coverage_present,
        "compare_brands": compare, "compare_json": compare_json,
        "gap_chains": gap_chains,
    })


@app.get("/api/map", response_class=JSONResponse)
def map_data(date: str = None, brand: str = None):
    conn = get_db()
    dates = get_available_dates(conn)
    if not date and dates:
        date = dates[0]
    if not date:
        conn.close()
        return []

    import pandas as pd
    df_raw = load_observations(conn, date)
    conn.close()
    df = df_raw[df_raw["brand"] != "Other"]
    in_stock = df[df["price"] > 0]

    if brand and brand != "All":
        in_stock = in_stock[in_stock["brand"] == brand]

    pharm_map = (
        in_stock.groupby(["pharmacy_id", "pharmacy_name", "lat", "lon", "address"])
        .agg(products=("good_id", "nunique"), brands=("brand", "nunique"))
        .reset_index()
    )
    pharm_map["lat"] = pd.to_numeric(pharm_map["lat"], errors="coerce")
    pharm_map["lon"] = pd.to_numeric(pharm_map["lon"], errors="coerce")
    pharm_map = pharm_map.dropna(subset=["lat", "lon"])

    points = []
    for _, row in pharm_map.iterrows():
        points.append({
            "lat": float(row["lat"]), "lon": float(row["lon"]),
            "name": row["pharmacy_name"], "address": str(row["address"])[:80],
            "products": int(row["products"]), "brands": int(row["brands"]),
        })
    return points
