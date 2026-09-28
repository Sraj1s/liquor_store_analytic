"""Generate deterministic POS-style exports; no real people or businesses."""

import csv
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from .schema import SOURCE_TABLES


def generate(output, days=183, seed=42, start=date(2026, 3, 1)):
    if not 1 <= days <= 730:
        raise ValueError("days must be between 1 and 730")
    out = Path(output)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Output directory is not empty; choose a new directory.")
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    rows = {t.name: [] for t in SOURCE_TABLES}
    for sid in range(1, 6):
        rows["suppliers"].append(
            dict(supplier_id=sid, name=f"Demo Distributor {sid}", lead_days=sid + 2)
        )
    categories = ["Whiskey", "Vodka", "Rum", "Gin", "Tequila"]
    for pid in range(1, 101):
        cost = rng.randrange(700, 4501, 50)
        rows["products"].append(
            dict(
                product_id=pid,
                supplier_id=1 + (pid - 1) // 20,
                name=f"{categories[(pid - 1) // 20]} Reserve {pid:03}",
                category=categories[(pid - 1) // 20],
                size_ml=750,
                cost_cents=cost,
                price_cents=round(cost * rng.uniform(1.25, 1.65)),
            )
        )
    stock = {p["product_id"]: 45 for p in rows["products"]}

    def movement(pid, day, kind, qty):
        rows["inventory_movements"].append(
            dict(
                movement_id=f"M{len(rows['inventory_movements']) + 1:07}",
                product_id=pid,
                occurred_on=day.isoformat(),
                kind=kind,
                quantity=qty,
            )
        )

    for pid in stock:
        movement(pid, start, "opening", stock[pid])
    weights = [7 if pid <= 15 else (0.15 if pid > 90 else 1) for pid in stock]
    for d in range(days):
        day = start + timedelta(days=d)
        for pid in stock:
            if stock[pid] < 12:
                movement(pid, day, "delivery", 48)
                stock[pid] += 48
        n = rng.randint(30, 48) + (25 if day.weekday() in [4, 5] else 0)
        for receipt in range(n):
            sale_id = f"S{day:%Y%m%d}-{receipt:03}"
            stamp = datetime.combine(day, datetime.min.time()).replace(
                hour=rng.choices(range(10, 22), weights=[1, 1, 1, 2, 2, 3, 4, 5, 6, 5, 4, 2])[0],
                minute=rng.randrange(60),
            )
            pending = []
            for line in range(rng.randint(1, 3)):
                pid = rng.choices(list(stock), weights=weights)[0]
                qty = rng.randint(1, 3)
                if stock[pid] < qty:
                    continue
                p = rows["products"][pid - 1]
                discount = (qty * p["price_cents"] // 10) if rng.random() < 0.12 else 0
                pending.append(
                    dict(
                        item_id=f"{sale_id}-{line}",
                        sale_id=sale_id,
                        product_id=pid,
                        quantity=qty,
                        unit_price_cents=p["price_cents"],
                        unit_cost_cents=p["cost_cents"],
                        discount_cents=discount,
                    )
                )
                stock[pid] -= qty
            if pending:
                rows["sales"].append(
                    dict(
                        sale_id=sale_id,
                        sold_at=stamp.isoformat(sep=" "),
                        payment=rng.choice(["card", "card", "cash"]),
                    )
                )
                rows["sale_items"].extend(pending)
        pid = rng.choice(list(stock))
        if stock[pid] > 0 and rng.random() < 0.25:
            movement(pid, day, "breakage", -1)
            stock[pid] -= 1
    # Controlled defects affect exports only; the valid underlying simulation stays consistent.
    rows["sale_items"].extend(dict(r) for r in rows["sale_items"][:5])
    first = rows["sale_items"][0]
    rows["sale_items"].extend(
        [
            dict(first, item_id="BAD-UNKNOWN", product_id=9999),
            dict(first, item_id="BAD-QUANTITY", quantity=-3),
            dict(first, item_id="BAD-DISCOUNT", discount_cents=999999),
        ]
    )
    for table in SOURCE_TABLES:
        with (out / f"{table.name}.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[c.name for c in table.columns])
            writer.writeheader()
            writer.writerows(rows[table.name])
    return {name: len(values) for name, values in rows.items()}
