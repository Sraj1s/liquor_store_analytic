from datetime import timedelta

import pandas as pd
from sqlalchemy import text


def read_frame(engine, sql, params=None):
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def sales_frame(engine):
    df = read_frame(engine, "SELECT * FROM fact_sales ORDER BY sold_at, item_id")
    df["sold_at"] = pd.to_datetime(df["sold_at"])
    for col in ["revenue_cents", "cogs_cents", "profit_cents", "quantity"]:
        df[col] = pd.to_numeric(df[col])
    return df


def inventory_frame(engine, as_of):
    """Stock at selected day; trailing calendar-day demand, including zero-sale days."""
    df = read_frame(
        engine,
        """SELECT p.product_id, p.name AS product, p.category,
        p.cost_cents, s.lead_days, i.on_hand
        FROM inventory_daily i JOIN products p ON i.product_id=p.product_id
        JOIN suppliers s ON p.supplier_id=s.supplier_id WHERE i.stock_date=:day""",
        {"day": str(as_of)},
    )
    start = as_of - timedelta(days=29)
    first = read_frame(engine, "SELECT MIN(stock_date) AS first_day FROM inventory_daily").iloc[
        0, 0
    ]
    if first is not None:
        start = max(start, pd.Timestamp(first).date())
    units = read_frame(
        engine,
        """SELECT product_id, SUM(quantity) AS units_30d
        FROM fact_sales WHERE sold_at >= :start AND sold_at < :end GROUP BY product_id""",
        {"start": str(start), "end": str(as_of + timedelta(days=1))},
    )
    df = df.merge(units, on="product_id", how="left").fillna({"units_30d": 0})
    for col in ["cost_cents", "lead_days", "on_hand", "units_30d"]:
        df[col] = pd.to_numeric(df[col])
    df["daily_units"] = df["units_30d"] / ((as_of - start).days + 1)
    df["reorder_point"] = (df["daily_units"] * (df["lead_days"] + 3)).apply(__import__("math").ceil)
    df["needs_reorder"] = df["on_hand"] <= df["reorder_point"]
    df["stock_value"] = df["on_hand"] * df["cost_cents"] / 100
    df["days_cover"] = df["on_hand"] / df["daily_units"].replace(0, float("nan"))
    return df
