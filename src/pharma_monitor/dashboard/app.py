"""Streamlit dashboard for Pharma Monitor."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.pharma_monitor.db.database import get_connection, init_db
from src.pharma_monitor.analytics.metrics import (
    load_observations, get_available_dates, get_scrape_runs,
    numeric_distribution, sku_coverage, price_summary,
    brand_scorecard,
)
from src.pharma_monitor.scraper import run_scrape

# ─── Page Config ───
st.set_page_config(
    page_title="Pharma Monitor — Uzbekistan",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Dark theme friendly CSS ───
st.markdown("""
<style>
    div[data-testid="stMetric"] {
        background-color: rgba(28, 131, 225, 0.1);
        border: 1px solid rgba(28, 131, 225, 0.2);
        padding: 15px 20px;
        border-radius: 10px;
    }
    div[data-testid="stMetric"] label {
        color: #a0aec0 !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-size: 1.8rem !important;
    }
    .brand-card {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        cursor: pointer;
        transition: all 0.2s;
    }
    .brand-card:hover {
        background: rgba(255,255,255,0.1);
        border-color: rgba(28, 131, 225, 0.5);
    }
    .brand-name { font-size: 1.3rem; font-weight: 700; margin-bottom: 0.5rem; }
    .brand-stat { color: #a0aec0; font-size: 0.9rem; }
    .pharmacy-row {
        background: rgba(255,255,255,0.03);
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.5rem;
        border-left: 3px solid #1c83e1;
    }
</style>
""", unsafe_allow_html=True)

# ─── Init DB ───
init_db()
conn = get_connection()

# ─── Navigation state ───
if "page" not in st.session_state:
    st.session_state.page = "overview"
if "selected_brand" not in st.session_state:
    st.session_state.selected_brand = None
if "selected_product" not in st.session_state:
    st.session_state.selected_product = None


def go_to(page, brand=None, product=None):
    st.session_state.page = page
    st.session_state.selected_brand = brand
    st.session_state.selected_product = product


# ─── Sidebar ───
with st.sidebar:
    st.title("Pharma Monitor")
    st.caption("Medical device distribution tracking")

    if st.button("Run Scrape Now", type="primary", use_container_width=True):
        with st.spinner("Scraping ArzonApteka..."):
            try:
                stats = run_scrape(verbose=False)
                st.success(f"{stats['products']} products, {stats['pharmacies']} pharmacies, {stats['observations']:,} obs")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()

    dates = get_available_dates(conn)
    if dates:
        selected_date = st.selectbox("Scrape Date", dates, index=0)
    else:
        selected_date = None
        st.warning("No data. Click 'Run Scrape Now'.")

    # Navigation
    st.divider()
    if st.button("Overview", use_container_width=True):
        go_to("overview")
    if st.button("Brand Drill-Down", use_container_width=True):
        go_to("brands")
    if st.button("Chain Analysis", use_container_width=True):
        go_to("chains")

    # Breadcrumbs
    if st.session_state.page == "brand_detail":
        st.divider()
        st.caption(f"Brand: **{st.session_state.selected_brand}**")
        if st.session_state.selected_product:
            st.caption(f"Product: **{st.session_state.selected_product}**")

    # Scrape history
    st.divider()
    st.caption("Recent scrapes")
    runs = get_scrape_runs(conn)
    if not runs.empty:
        for _, run in runs.head(5).iterrows():
            icon = "✅" if run["status"] == "done" else "❌"
            st.text(f"{icon} {run['started_at'][:16]} | {run['observations_count'] or 0} obs")

# ─── Load data ───
if not selected_date:
    st.title("Pharma Monitor")
    st.info("No data available. Use the sidebar to run a scrape first.")
    st.stop()

df_raw = load_observations(conn, selected_date)
if df_raw.empty:
    st.info("No data for this date.")
    st.stop()

# Filter out "Other" brand from all views
df = df_raw[df_raw["brand"] != "Other"]
in_stock = df[df["price"] > 0]

# ═══════════════════════════════════════════════════════════════
# PAGE: OVERVIEW
# ═══════════════════════════════════════════════════════════════
if st.session_state.page == "overview":
    st.title(f"Distribution Dashboard — {selected_date}")

    # KPI Row
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Products", in_stock["good_id"].nunique())
    with col2:
        st.metric("Pharmacies", f"{in_stock['pharmacy_id'].nunique():,}")
    with col3:
        st.metric("Brands", in_stock["brand"].nunique())
    with col4:
        st.metric("Observations", f"{len(in_stock):,}")
    with col5:
        st.metric("Avg Price", f"{int(in_stock['price'].mean()):,} UZS")

    st.divider()

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Scorecard", "Price Analysis", "Distribution", "Pharmacy Map"])

    # ─── Scorecard ───
    with tab1:
        scorecard = brand_scorecard(df)
        if not scorecard.empty:
            st.subheader("Brand Scorecard")
            st.dataframe(
                scorecard.style.format({
                    "avg_price": "{:,.0f}",
                    "min_price": "{:,.0f}",
                    "max_price": "{:,.0f}",
                    "nd_pct": "{:.1f}%",
                    "avg_skus_per_pharmacy": "{:.1f}",
                }),
                use_container_width=True, hide_index=True,
            )

            col1, col2 = st.columns(2)
            with col1:
                fig = px.bar(scorecard, x="brand", y="pharmacies", title="Pharmacies per Brand",
                             color="brand", text="pharmacies")
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig = px.pie(scorecard, values="pharmacies", names="brand",
                             title="Market Share by Pharmacy Presence", hole=0.4)
                st.plotly_chart(fig, use_container_width=True)

            st.info("Click **Brand Drill-Down** in sidebar to explore each brand in detail.")

    # ─── Price Analysis ───
    with tab2:
        prices = price_summary(df)
        if not prices.empty:
            cat_filter = st.selectbox("Category", ["All"] + sorted(prices["category"].unique()), key="pc")
            show = prices if cat_filter == "All" else prices[prices["category"] == cat_filter]
            st.dataframe(
                show[["brand", "good_name", "category", "pharmacies", "avg_price", "min_price", "max_price", "total_stock"]]
                .style.format({"avg_price": "{:,.0f}", "min_price": "{:,.0f}", "max_price": "{:,.0f}"}),
                use_container_width=True, hide_index=True,
            )
            fig = px.box(in_stock, x="brand", y="price", title="Price Distribution by Brand",
                         color="brand", points=False)
            fig.update_yaxes(title="Price (UZS)")
            st.plotly_chart(fig, use_container_width=True)

    # ─── Distribution ───
    with tab3:
        nd = numeric_distribution(df)
        if not nd.empty:
            col1, col2 = st.columns(2)
            with col1:
                fig = px.bar(nd, x="brand", y="nd_pct", title="Numeric Distribution (%)",
                             color="brand", text="nd_pct")
                fig.update_layout(showlegend=False, yaxis_title="% of pharmacies")
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                skus = sku_coverage(df)
                fig = px.bar(skus, x="brand", y="unique_skus", title="SKU Coverage",
                             color="brand", text="unique_skus")
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

        # Distribution gaps
        st.subheader("Distribution Gaps — Prolife")
        st.caption("Pharmacies carrying competitors but NOT Prolife")
        prolife_pharms = set(in_stock[in_stock["brand"] == "Prolife"]["pharmacy_id"])
        competitor_data = in_stock[
            (in_stock["brand"].isin(["OMRON", "Microlife", "B.Well"])) &
            (~in_stock["pharmacy_id"].isin(prolife_pharms))
        ]
        if not competitor_data.empty:
            gaps = (
                competitor_data.groupby(["pharmacy_id", "pharmacy_name", "address"])
                .agg(competitor_brands=("brand", lambda x: ", ".join(sorted(x.unique()))))
                .reset_index()
            )
            st.metric("Gap pharmacies (opportunity)", len(gaps))
            st.dataframe(gaps.head(50), use_container_width=True, hide_index=True)

    # ─── Map ───
    with tab4:
        map_brand = st.selectbox("Show pharmacies for", ["All"] + sorted(df["brand"].unique()), key="mb")
        map_df = in_stock if map_brand == "All" else in_stock[in_stock["brand"] == map_brand]
        pharm_map = (
            map_df.groupby(["pharmacy_id", "pharmacy_name", "lat", "lon", "address"])
            .agg(products=("good_id", "nunique"), brands=("brand", "nunique"))
            .reset_index()
        )
        pharm_map["lat"] = pd.to_numeric(pharm_map["lat"], errors="coerce")
        pharm_map["lon"] = pd.to_numeric(pharm_map["lon"], errors="coerce")
        pharm_map = pharm_map.dropna(subset=["lat", "lon"])
        if not pharm_map.empty:
            center_lat = pharm_map["lat"].mean()
            center_lon = pharm_map["lon"].mean()
            m = folium.Map(location=[center_lat, center_lon], zoom_start=6,
                           tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
                           attr="Google Maps")
            cluster = MarkerCluster()
            for _, row in pharm_map.iterrows():
                popup_html = f"""
                <div style="font-family:Arial;min-width:180px">
                    <b>{row['pharmacy_name']}</b><br>
                    <span style="color:#666">{row['address'][:80]}</span><br>
                    <hr style="margin:4px 0">
                    Products: {row['products']} | Brands: {row['brands']}
                </div>
                """
                folium.Marker(
                    [row["lat"], row["lon"]],
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=f"{row['pharmacy_name']} ({row['products']} products)",
                    icon=folium.Icon(color="blue", icon="plus-sign"),
                ).add_to(cluster)
            cluster.add_to(m)
            st_folium(m, use_container_width=True, height=600)
            st.caption(f"Showing {len(pharm_map)} pharmacies")

# ═══════════════════════════════════════════════════════════════
# PAGE: BRAND SELECTION
# ═══════════════════════════════════════════════════════════════
elif st.session_state.page == "brands":
    st.title("Brand Drill-Down")
    st.caption("Select a brand to see its products and distribution")

    # Exclude "Other" from brand cards, show main brands first
    main_brands = ["Prolife", "OMRON", "Microlife", "B.Well", "Beurer", "Rossmax", "Little Doctor", "A&D",
                   "Citizen", "YUWELL", "KD Medical", "Amrus", "Accu-Chek", "OneTouch", "Dr.Frei",
                   "MediTech", "Braun", "Medico", "CS Medica"]
    scorecard = brand_scorecard(df)

    cols = st.columns(3)
    col_idx = 0

    for brand in main_brands:
        brand_data = scorecard[scorecard["brand"] == brand]
        if brand_data.empty:
            continue

        row = brand_data.iloc[0]
        with cols[col_idx % 3]:
            st.markdown(f"""
            <div class="brand-card">
                <div class="brand-name">{brand}</div>
                <div class="brand-stat">{int(row['products'])} products | {int(row['pharmacies'])} pharmacies | ND: {row['nd_pct']:.1f}%</div>
                <div class="brand-stat">Avg price: {int(row['avg_price']):,} UZS | Stock: {int(row['total_stock']):,}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"Explore {brand}", key=f"btn_{brand}", use_container_width=True):
                go_to("brand_detail", brand=brand)
                st.rerun()
        col_idx += 1

    # Also show "Other" summary
    other_data = scorecard[~scorecard["brand"].isin(main_brands)]
    if not other_data.empty:
        st.divider()
        st.subheader("Other brands")
        st.dataframe(
            other_data.style.format({
                "avg_price": "{:,.0f}", "min_price": "{:,.0f}", "max_price": "{:,.0f}",
                "nd_pct": "{:.1f}%", "avg_skus_per_pharmacy": "{:.1f}",
            }),
            use_container_width=True, hide_index=True,
        )

# ═══════════════════════════════════════════════════════════════
# PAGE: BRAND DETAIL (products + pharmacies)
# ═══════════════════════════════════════════════════════════════
elif st.session_state.page == "brand_detail":
    brand = st.session_state.selected_brand
    brand_df = in_stock[in_stock["brand"] == brand]

    # Back button
    if st.button("← Back to brands"):
        go_to("brands")
        st.rerun()

    st.title(f"{brand}")

    # Brand KPIs
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Products", brand_df["good_id"].nunique())
    with col2:
        st.metric("Pharmacies", f"{brand_df['pharmacy_id'].nunique():,}")
    with col3:
        total_pharm = in_stock["pharmacy_id"].nunique()
        nd = brand_df["pharmacy_id"].nunique() / total_pharm * 100 if total_pharm > 0 else 0
        st.metric("Distribution", f"{nd:.1f}%")
    with col4:
        st.metric("Total Stock", f"{brand_df['count'].sum():,}")

    st.divider()

    # Product list with aggregated stats
    products = (
        brand_df
        .groupby(["good_id", "good_name", "category", "vendor_name"])
        .agg(
            pharmacies=("pharmacy_id", "nunique"),
            avg_price=("price", "mean"),
            min_price=("price", "min"),
            max_price=("price", "max"),
            total_stock=("count", "sum"),
        )
        .reset_index()
        .sort_values("pharmacies", ascending=False)
    )

    # ─── Two-column layout: product selector LEFT, pharmacies RIGHT ───
    product_names = products["good_name"].tolist()

    # Product selector — prominent at the top
    st.subheader("Select product to filter pharmacies")
    selected_product_name = st.selectbox(
        "Product",
        product_names,
        index=0,
        key="product_select",
        label_visibility="collapsed",
    )

    # ─── Show selected product info + pharmacies ───
    product_row = products[products["good_name"] == selected_product_name].iloc[0]
    product_df = brand_df[brand_df["good_name"] == selected_product_name]

    pharmacy_list = (
        product_df
        .groupby(["pharmacy_id", "pharmacy_name", "address", "lat", "lon"])
        .agg(
            price=("price", "first"),
            stock=("count", "first"),
            last_update=("last_update", "first"),
        )
        .reset_index()
        .sort_values("price")
    )

    # Product KPIs
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Pharmacies", len(pharmacy_list))
    with col2:
        st.metric("Min Price", f"{pharmacy_list['price'].min():,} UZS")
    with col3:
        st.metric("Avg Price", f"{int(pharmacy_list['price'].mean()):,} UZS")
    with col4:
        st.metric("Max Price", f"{pharmacy_list['price'].max():,} UZS")
    with col5:
        st.metric("Total Stock", f"{pharmacy_list['stock'].sum():,}")

    # Price histogram + pharmacy table side by side
    col_chart, col_map = st.columns([1, 1])

    with col_chart:
        cheapest = pharmacy_list.nsmallest(10, "price")[["pharmacy_name", "price"]].copy()
        cheapest["pharmacy_name"] = cheapest["pharmacy_name"].str[:35]
        cheapest = cheapest.sort_values("price", ascending=True)

        fig = px.bar(
            cheapest, y="pharmacy_name", x="price",
            orientation="h",
            title="Top 10 cheapest pharmacies",
            text=cheapest["price"].apply(lambda p: f"{p:,}"),
            color_discrete_sequence=["#48bb78"],
        )
        fig.update_layout(
            yaxis_title="", xaxis_title="Price (UZS)",
            margin=dict(t=40, b=20, l=10),
            showlegend=False, height=350,
        )
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

    with col_map:
        map_data = pharmacy_list.copy()
        map_data["lat"] = pd.to_numeric(map_data["lat"], errors="coerce")
        map_data["lon"] = pd.to_numeric(map_data["lon"], errors="coerce")
        map_data = map_data.dropna(subset=["lat", "lon"])
        if not map_data.empty:
            center_lat = map_data["lat"].mean()
            center_lon = map_data["lon"].mean()
            m = folium.Map(location=[center_lat, center_lon], zoom_start=6,
                           tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
                           attr="Google Maps")
            cluster = MarkerCluster()
            for _, row in map_data.iterrows():
                popup_html = f"""
                <div style="font-family:Arial;min-width:200px">
                    <b>{row['pharmacy_name']}</b><br>
                    <span style="color:#666">{row['address'][:80]}</span><br>
                    <hr style="margin:4px 0">
                    <b style="color:#e53e3e;font-size:1.1em">{row['price']:,} UZS</b><br>
                    Stock: {row['stock']} pcs
                </div>
                """
                color = "green" if row["price"] <= pharmacy_list["price"].median() else "red"
                folium.Marker(
                    [row["lat"], row["lon"]],
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=f"{row['pharmacy_name']} — {row['price']:,} UZS",
                    icon=folium.Icon(color=color, icon="plus-sign"),
                ).add_to(cluster)
            cluster.add_to(m)
            st_folium(m, use_container_width=True, height=400)
        else:
            st.info("No location data")

    # Full pharmacy table
    st.subheader(f"Pharmacies ({len(pharmacy_list)})")
    st.dataframe(
        pharmacy_list[["pharmacy_name", "address", "price", "stock", "last_update"]]
        .rename(columns={
            "pharmacy_name": "Pharmacy",
            "address": "Address",
            "price": "Price (UZS)",
            "stock": "Stock",
            "last_update": "Last Update",
        })
        .style.format({"Price (UZS)": "{:,}"}),
        use_container_width=True, hide_index=True,
        height=500,
    )

    # ─── All products summary (collapsible) ───
    with st.expander(f"All {brand} products ({len(products)})"):
        st.dataframe(
            products[["good_name", "category", "pharmacies", "avg_price", "min_price", "max_price", "total_stock"]]
            .rename(columns={
                "good_name": "Product",
                "category": "Category",
                "pharmacies": "Pharmacies",
                "avg_price": "Avg Price",
                "min_price": "Min Price",
                "max_price": "Max Price",
                "total_stock": "Stock",
            })
            .style.format({
                "Avg Price": "{:,.0f}",
                "Min Price": "{:,.0f}",
                "Max Price": "{:,.0f}",
            }),
            use_container_width=True, hide_index=True,
        )


# ═══════════════════════════════════════════════════════════════
# PAGE: CHAIN ANALYSIS
# ═══════════════════════════════════════════════════════════════
elif st.session_state.page == "chains":
    st.title("Chain Analysis")
    st.caption("Distribution coverage by pharmacy chains")

    # Only chains (exclude Independent for clarity)
    chains_only = in_stock[in_stock["chain"] != "Independent"]
    all_chains = sorted(chains_only["chain"].unique())

    # Brand selector
    chain_brand = st.selectbox("Select brand", sorted(in_stock["brand"].unique()), key="chain_brand")
    brand_data = in_stock[in_stock["brand"] == chain_brand]

    st.divider()

    # ─── Chain coverage table ───
    st.subheader(f"{chain_brand} — Coverage by Chain")

    # For each chain: total pharmacies in chain, pharmacies carrying this brand, products carried
    chain_stats = []
    for chain in all_chains:
        chain_pharmacies = in_stock[in_stock["chain"] == chain]["pharmacy_id"].nunique()
        brand_in_chain = brand_data[brand_data["chain"] == chain]
        brand_pharmacies = brand_in_chain["pharmacy_id"].nunique()
        brand_products = brand_in_chain["good_id"].nunique()
        product_list = ", ".join(sorted(brand_in_chain["good_name"].unique())[:5])

        chain_stats.append({
            "Chain": chain,
            "Total Pharmacies": chain_pharmacies,
            f"{chain_brand} Present": brand_pharmacies,
            "Coverage %": round(brand_pharmacies / chain_pharmacies * 100, 0) if chain_pharmacies > 0 else 0,
            "Products": brand_products,
            "Product Names": product_list[:100],
        })

    chain_df = pd.DataFrame(chain_stats).sort_values(f"{chain_brand} Present", ascending=False)

    # KPIs
    total_chain_pharm = chains_only["pharmacy_id"].nunique()
    brand_in_chains = brand_data[brand_data["chain"] != "Independent"]["pharmacy_id"].nunique()
    chains_with_brand = chain_df[chain_df[f"{chain_brand} Present"] > 0].shape[0]
    chains_without = chain_df[chain_df[f"{chain_brand} Present"] == 0].shape[0]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Chains with brand", f"{chains_with_brand}/{len(all_chains)}")
    with col2:
        st.metric("Chain pharmacies covered", f"{brand_in_chains}/{total_chain_pharm}")
    with col3:
        pct = round(brand_in_chains / total_chain_pharm * 100, 1) if total_chain_pharm > 0 else 0
        st.metric("Chain coverage", f"{pct}%")
    with col4:
        st.metric("Chains WITHOUT brand", chains_without)

    # Coverage chart
    top_chains = chain_df.head(20)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=top_chains["Chain"], x=top_chains["Total Pharmacies"],
        name="Total in chain",
        orientation="h",
        marker_color="rgba(100, 100, 100, 0.3)",
    ))
    fig.add_trace(go.Bar(
        y=top_chains["Chain"], x=top_chains[f"{chain_brand} Present"],
        name=f"{chain_brand} present",
        orientation="h",
        marker_color="#48bb78",
    ))
    fig.update_layout(
        title=f"{chain_brand} coverage in top 20 chains",
        barmode="overlay",
        height=600,
        yaxis=dict(autorange="reversed"),
        xaxis_title="Number of pharmacies",
        legend=dict(orientation="h", y=1.05),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Table
    st.dataframe(chain_df, use_container_width=True, hide_index=True, height=400)

    st.divider()

    # ─── Competitor comparison in chains ───
    st.subheader("Competitor Comparison by Chain")
    st.caption("How each brand covers the same chains")

    compare_brands = st.multiselect(
        "Brands to compare",
        sorted(in_stock["brand"].unique()),
        default=["Prolife", "OMRON", "B.Well", "Microlife"],
        key="chain_compare_brands"
    )

    if compare_brands:
        # Build pivot: chain x brand → pharmacy count
        pivot_data = []
        for chain in all_chains:
            row = {"Chain": chain, "Chain Size": in_stock[in_stock["chain"] == chain]["pharmacy_id"].nunique()}
            for brand in compare_brands:
                brand_chain = in_stock[(in_stock["brand"] == brand) & (in_stock["chain"] == chain)]
                row[brand] = brand_chain["pharmacy_id"].nunique()
            pivot_data.append(row)

        pivot_df = pd.DataFrame(pivot_data).sort_values("Chain Size", ascending=False)

        # Heatmap
        heatmap_chains = pivot_df.head(25)
        fig = go.Figure()
        for brand in compare_brands:
            fig.add_trace(go.Bar(
                y=heatmap_chains["Chain"],
                x=heatmap_chains[brand],
                name=brand,
                orientation="h",
            ))
        fig.update_layout(
            title="Brand presence in chains (pharmacy count)",
            barmode="group",
            height=700,
            yaxis=dict(autorange="reversed"),
            xaxis_title="Pharmacies in chain carrying brand",
            legend=dict(orientation="h", y=1.05),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Pivot table
        st.dataframe(pivot_df, use_container_width=True, hide_index=True, height=400)

    st.divider()

    # ─── Gap analysis: chains where competitors are but selected brand isn't ───
    st.subheader(f"Chain Gaps — {chain_brand}")
    st.caption(f"Chains where competitors are present but {chain_brand} is NOT")

    brand_chains = set(brand_data[brand_data["chain"] != "Independent"]["chain"].unique())
    gap_chains = []
    for chain in all_chains:
        if chain in brand_chains:
            continue
        chain_data = in_stock[in_stock["chain"] == chain]
        competitors = chain_data[chain_data["brand"] != "Other"]["brand"].unique()
        if len(competitors) > 0:
            gap_chains.append({
                "Chain": chain,
                "Pharmacies": chain_data["pharmacy_id"].nunique(),
                "Competitor Brands": ", ".join(sorted(competitors)),
                "Products Available": chain_data["good_id"].nunique(),
            })

    if gap_chains:
        gap_df = pd.DataFrame(gap_chains).sort_values("Pharmacies", ascending=False)
        st.metric("Chains without brand (opportunity)", len(gap_df))
        st.dataframe(gap_df, use_container_width=True, hide_index=True)
    else:
        st.success(f"{chain_brand} is present in all chains!")


# ─── Footer ───
st.divider()
st.caption(f"Pharma Monitor v1.0 | Data: ArzonApteka.uz | Scrape: {selected_date}")
