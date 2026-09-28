"""Read-only dashboard. Launch from the repository root."""

import os
from datetime import timedelta

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import inspect

from liquor.analytics import inventory_frame, read_frame, sales_frame
from liquor.db import get_engine

st.set_page_config(page_title="Liquor Store Analytics", page_icon="📊", layout="wide")
st.markdown(
    """<style>
.block-container {padding-top:2rem; max-width:1480px;}
[data-testid="stMetric"] {background:#122b32; border:1px solid #28515a; padding:18px; border-radius:12px;}
[data-testid="stMetricLabel"] {color:#b4cbd0;}
</style>""",
    unsafe_allow_html=True,
)
st.title("Liquor Store Analytics")
st.caption("SYNTHETIC PORTFOLIO PROJECT · One store · USD · America/Chicago store-local time")


@st.cache_resource
def database():
    return get_engine(demo=os.getenv("LIQUOR_DEMO") == "1")


try:
    engine = database()
    if not inspect(engine).has_table("sale_items"):
        st.info("Initialize and load the database first. See the README quick start.")
        st.stop()
    df = sales_frame(engine)
except Exception:
    st.error("Cannot read the database. Check your local .env and run the README setup commands.")
    st.stop()
if df.empty:
    st.info("No accepted sales yet. Run the generator and pipeline first.")
    st.stop()

st.sidebar.title("Explore the store")
st.sidebar.caption(
    "Filters apply to sales charts and downloads. Inventory uses the end date and category."
)
min_day, max_day = df.sold_at.min().date(), df.sold_at.max().date()
dates = st.sidebar.date_input(
    "Sales period", value=(min_day, max_day), min_value=min_day, max_value=max_day
)
categories = sorted(df.category.unique())
selected = st.sidebar.multiselect("Categories", categories, default=categories)
if len(dates) != 2:
    st.info("Select a start and end date.")
    st.stop()
start, end = dates
filtered = df[
    (df.sold_at >= pd.Timestamp(start))
    & (df.sold_at < pd.Timestamp(end + timedelta(days=1)))
    & df.category.isin(selected)
].copy()
st.sidebar.caption(f"Data covers {min_day:%b %d, %Y} – {max_day:%b %d, %Y}.")
st.sidebar.button("Refresh data", help="Rerun after loading a new batch.")
sales_tab, inventory_tab, quality_tab = st.tabs(
    ["Sales & profitability", "Inventory decisions", "Pipeline health"]
)


def chart(fig):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=15, t=35, b=10),
        font=dict(family="sans-serif"),
        legend_title_text="",
    )
    st.plotly_chart(fig, width="stretch")


with sales_tab:
    if filtered.empty:
        st.info("No sales match these filters. Select another category or period.")
    else:
        revenue = filtered.revenue_cents.sum() / 100
        profit = filtered.profit_cents.sum() / 100
        cols = st.columns(4)
        cols[0].metric("Net sales", f"${revenue:,.0f}")
        cols[1].metric("Gross profit", f"${profit:,.0f}")
        cols[2].metric("Gross margin", f"{profit / revenue:.1%}" if revenue else "—")
        cols[3].metric("Receipts", f"{filtered.sale_id.nunique():,}")
        st.caption(
            "Net sales = item price × quantity − line discounts, before tax. Gross profit subtracts item cost; it excludes operating expenses. Receipts count purchases containing a selected category."
        )
        daily = (
            filtered.set_index("sold_at")[["revenue_cents", "profit_cents"]]
            .resample("D")
            .sum()
            .reindex(pd.date_range(start, end), fill_value=0)
            / 100
        )
        daily.index.name = "Date"
        daily = daily.rename(columns={"revenue_cents": "Net sales", "profit_cents": "Gross profit"})
        st.subheader("Daily sales and gross profit")
        chart(
            px.line(
                daily,
                labels={"value": "USD", "variable": "Measure"},
                color_discrete_sequence=["#56d6bd", "#eeb96a"],
            )
        )
        left, right = st.columns(2)
        with left:
            st.subheader("Gross profit by category")
            cat = (
                filtered.groupby("category", as_index=False)
                .profit_cents.sum()
                .sort_values("profit_cents")
            )
            cat["Gross profit ($)"] = cat.profit_cents / 100
            chart(
                px.bar(
                    cat,
                    x="Gross profit ($)",
                    y="category",
                    orientation="h",
                    color_discrete_sequence=["#56d6bd"],
                    labels={"category": ""},
                )
            )
        with right:
            st.subheader("Top 10 products by gross profit")
            top = (
                filtered.groupby("product", as_index=False)
                .profit_cents.sum()
                .nlargest(10, "profit_cents")
                .sort_values("profit_cents")
            )
            top["Gross profit ($)"] = top.profit_cents / 100
            chart(
                px.bar(
                    top,
                    x="Gross profit ($)",
                    y="product",
                    orientation="h",
                    color_discrete_sequence=["#eeb96a"],
                    labels={"product": ""},
                )
            )
        st.subheader("When do customers buy?")
        receipts = filtered.drop_duplicates("sale_id").copy()
        receipts["Day"] = receipts.sold_at.dt.dayofweek
        receipts["Hour"] = receipts.sold_at.dt.hour
        heat = (
            receipts.groupby(["Day", "Hour"])
            .size()
            .unstack(fill_value=0)
            .reindex(index=range(7), columns=range(24), fill_value=0)
        )
        heat.index = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        chart(
            px.imshow(
                heat,
                labels={"x": "Hour (store-local)", "y": "", "color": "Receipts"},
                aspect="auto",
                color_continuous_scale="Teal",
            )
        )
        st.caption("Counts across the selected period, not an average per weekday.")
        st.download_button(
            "Download filtered sale items",
            filtered.to_csv(index=False),
            "filtered_sales.csv",
            "text/csv",
        )

with inventory_tab:
    st.subheader(f"Inventory as of {end:%B %d, %Y}")
    st.caption(
        "End-of-day stock. Category filter applies; demand uses up to 30 calendar days ending on this date, regardless of the sales start-date filter."
    )
    stock = inventory_frame(engine, end)
    stock = stock[stock.category.isin(selected)]
    if stock.empty:
        st.info("No inventory matches the selection.")
    else:
        cols = st.columns(3)
        cols[0].metric("Units on hand", f"{stock.on_hand.sum():,}")
        cols[1].metric("Stock value at catalog cost", f"${stock.stock_value.sum():,.0f}")
        cols[2].metric("Products at reorder point", int(stock.needs_reorder.sum()))
        st.caption(
            "Reorder point = ceiling(recent units/day × (supplier lead days + 3 buffer days)). This is a heuristic, not a demand forecast; it ignores open purchase orders."
        )
        action = stock[stock.needs_reorder].sort_values("days_cover")
        st.subheader("Restocking queue")
        display = [
            "product",
            "category",
            "on_hand",
            "daily_units",
            "lead_days",
            "reorder_point",
            "days_cover",
        ]
        if action.empty:
            st.success("No products are at or below the reorder point for this selection.")
        else:
            st.dataframe(action[display].round(1), hide_index=True, width="stretch")
        st.subheader("Stock value and recent movement")
        chart(
            px.scatter(
                stock,
                x="units_30d",
                y="stock_value",
                color="category",
                hover_name="product",
                labels={
                    "units_30d": "Units sold in trailing window",
                    "stock_value": "Stock value ($)",
                    "category": "Category",
                },
                color_discrete_sequence=["#56d6bd", "#eeb96a", "#80aef0", "#d798ca", "#b8ce76"],
            )
        )
        st.subheader("Slow-moving stock")
        st.caption(
            "Products with stock and fewer than 5 units sold in the trailing window. Threshold is an explicit demo assumption."
        )
        slow = stock[(stock.units_30d < 5) & (stock.on_hand > 0)].sort_values(
            "stock_value", ascending=False
        )
        st.dataframe(
            slow[["product", "on_hand", "units_30d", "stock_value"]].round(2),
            hide_index=True,
            width="stretch",
        )
        st.download_button(
            "Download inventory snapshot",
            stock.to_csv(index=False),
            "inventory_snapshot.csv",
            "text/csv",
        )

with quality_tab:
    st.subheader("Batch processing history")
    st.caption(
        "All pipeline runs; unaffected by business filters. Timestamps are UTC. Failed transactions commit no business rows. Skipped batches were previously loaded."
    )
    history = read_frame(engine, "SELECT * FROM pipeline_runs ORDER BY started_at DESC")
    st.dataframe(history.drop(columns=["batch_hash"]), hide_index=True, width="stretch")
    rejects = read_frame(
        engine,
        "SELECT source_table, row_number, reason, payload FROM raw_records WHERE disposition='rejected'",
    )
    st.subheader("Quarantined records")
    st.dataframe(rejects, hide_index=True, width="stretch")
    st.download_button(
        "Download rejected records", rejects.to_csv(index=False), "rejected_records.csv", "text/csv"
    )
    with st.expander("Data lineage and limitations"):
        st.write(
            "Deterministic synthetic CSV exports → raw_records audit → validated relational tables → fact_sales view and inventory_daily snapshots → this dashboard. Original source files remain under data/raw/."
        )
        st.write(
            "No real customers, tax, returns, open purchase orders, or variable-cost inventory accounting. Inventory is checked at day end, not within each day. Demand during stockouts is unobserved. Generator deliveries are simplified."
        )
