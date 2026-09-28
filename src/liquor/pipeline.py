"""Single-writer, transactional batch ingestion with immutable source IDs."""

import csv
import hashlib
import io
import json
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import Date, DateTime, Integer, select, text

from .schema import (
    SOURCE_TABLES,
    batches,
    inventory_daily,
    movements,
    products,
    raw,
    runs,
    sale_items,
    sales,
)


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize(table, row):
    if set(row) != {c.name for c in table.columns}:
        raise ValueError("Columns do not match the source contract")
    result = {}
    for col in table.columns:
        value = row[col.name]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing value: {col.name}")
        value = value.strip()
        if isinstance(col.type, Integer):
            value = int(value)
            if not -(2**31) <= value < 2**31:
                raise ValueError(f"Integer out of supported range: {col.name}")
        elif isinstance(col.type, DateTime):
            value = datetime.fromisoformat(value)
            if value.tzinfo:
                raise ValueError("Use naive America/Chicago store-local timestamps")
        elif isinstance(col.type, Date):
            value = date.fromisoformat(value)
        elif len(value) > col.type.length:
            raise ValueError(f"Value too long: {col.name}")
        result[col.name] = value
    return result


def validate(name, r, known):
    if name == "suppliers":
        if r["supplier_id"] <= 0 or r["lead_days"] <= 0:
            raise ValueError("Supplier ID and lead time must be positive")
    elif name == "products":
        if r["supplier_id"] not in known["suppliers"]:
            raise ValueError("Unknown supplier")
        if any(r[k] <= 0 for k in ["product_id", "size_ml", "cost_cents", "price_cents"]):
            raise ValueError("Product numbers must be positive")
        r["category"] = r["category"].title()
    elif name == "sales":
        r["payment"] = r["payment"].lower()
        if r["payment"] not in ["cash", "card"]:
            raise ValueError("Unsupported payment method")
    elif name == "sale_items":
        if r["sale_id"] not in known["sales"]:
            raise ValueError("Unknown sale")
        if r["product_id"] not in known["products"]:
            raise ValueError("Unknown product")
        if r["quantity"] <= 0 or r["unit_price_cents"] <= 0 or r["unit_cost_cents"] < 0:
            raise ValueError("Invalid quantity, price or cost")
        if not 0 <= r["discount_cents"] <= r["quantity"] * r["unit_price_cents"]:
            raise ValueError("Discount outside line total")
    elif name == "inventory_movements":
        if r["product_id"] not in known["products"]:
            raise ValueError("Unknown product")
        r["kind"] = r["kind"].lower()
        if r["kind"] not in ["opening", "delivery", "breakage"]:
            raise ValueError("Unknown movement type")
        if (r["kind"] == "breakage" and r["quantity"] >= 0) or (
            r["kind"] != "breakage" and r["quantity"] <= 0
        ):
            raise ValueError("Invalid movement sign")


def rebuild_inventory(conn):
    changes = defaultdict(int)
    for r in conn.execute(select(movements)).mappings():
        changes[(r["occurred_on"], r["product_id"])] += r["quantity"]
    statement = select(sales.c.sold_at, sale_items.c.product_id, sale_items.c.quantity).join(
        sale_items
    )
    for timestamp, pid, qty in conn.execute(statement):
        changes[(timestamp.date(), pid)] -= qty
    conn.execute(inventory_daily.delete())
    if not changes:
        return
    start, end = min(d for d, _ in changes), max(d for d, _ in changes)
    if (end - start).days > 3650:
        raise ValueError("Inventory dates span more than ten years")
    balances = dict.fromkeys(conn.execute(select(products.c.product_id)).scalars(), 0)
    records = []
    day = start
    while day <= end:
        for pid in balances:
            balances[pid] += changes.get((day, pid), 0)
            if balances[pid] < 0:
                raise ValueError(f"Negative end-of-day stock for product {pid} on {day}")
            records.append(dict(stock_date=day, product_id=pid, on_hand=balances[pid]))
        day += timedelta(days=1)
    for offset in range(0, len(records), 1000):
        conn.execute(inventory_daily.insert(), records[offset : offset + 1000])


def ingest(engine, folder):
    folder = Path(folder)
    source = {}
    digest = hashlib.sha256()
    for table in SOURCE_TABLES:
        content = (folder / f"{table.name}.csv").read_bytes()
        digest.update(table.name.encode() + b"\0" + content)
        with io.StringIO(content.decode("utf-8"), newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != [c.name for c in table.columns]:
                raise ValueError(f"Wrong CSV header for {table.name}")
            source[table.name] = list(reader)
    batch_hash = digest.hexdigest()
    run_id = str(uuid.uuid4())
    counts = dict(
        input_rows=sum(map(len, source.values())),
        inserted_rows=0,
        duplicate_rows=0,
        rejected_rows=0,
    )
    with engine.begin() as conn:
        conn.execute(
            runs.insert().values(
                run_id=run_id, batch_hash=batch_hash, started_at=now(), status="running", **counts
            )
        )
    try:
        with engine.begin() as conn:
            if conn.execute(select(batches).where(batches.c.batch_hash == batch_hash)).first():
                conn.execute(
                    runs.update()
                    .where(runs.c.run_id == run_id)
                    .values(
                        status="skipped",
                        finished_at=now(),
                        message="Identical batch already loaded",
                    )
                )
                return dict(run_id=run_id, status="skipped", **counts)
            known = {}
            for table in SOURCE_TABLES:
                pk = list(table.primary_key.columns)[0].name
                known[table.name] = {r[pk]: dict(r) for r in conn.execute(select(table)).mappings()}
                inserts, audit = [], []
                for number, payload in enumerate(source[table.name], 2):
                    disposition, reason = "inserted", None
                    try:
                        r = normalize(table, payload)
                        validate(table.name, r, known)
                        previous = known[table.name].get(r[pk])
                        if previous is not None:
                            if previous != r:
                                raise ValueError(
                                    "Conflicting existing ID; corrections require an explicit migration"
                                )
                            disposition = "duplicate"
                            counts["duplicate_rows"] += 1
                        else:
                            known[table.name][r[pk]] = r
                            inserts.append(r)
                            counts["inserted_rows"] += 1
                    except (ValueError, TypeError, OverflowError) as exc:
                        disposition, reason = "rejected", str(exc)
                        counts["rejected_rows"] += 1
                    audit.append(
                        dict(
                            run_id=run_id,
                            source_table=table.name,
                            row_number=number,
                            payload=json.dumps(payload, sort_keys=True),
                            disposition=disposition,
                            reason=reason,
                        )
                    )
                for offset in range(0, len(inserts), 1000):
                    conn.execute(table.insert(), inserts[offset : offset + 1000])
                for offset in range(0, len(audit), 1000):
                    conn.execute(raw.insert(), audit[offset : offset + 1000])
            rebuild_inventory(conn)
            # Cross-layer reconciliation before commit; integer cents avoid float drift.
            source_total = conn.scalar(
                text(
                    "SELECT COALESCE(SUM(quantity * unit_price_cents - discount_cents), 0) FROM sale_items"
                )
            )
            fact_total = conn.scalar(text("SELECT COALESCE(SUM(revenue_cents), 0) FROM fact_sales"))
            if source_total != fact_total:
                raise ValueError("Source and analytics revenue do not reconcile")
            conn.execute(batches.insert().values(batch_hash=batch_hash, loaded_at=now()))
            conn.execute(
                runs.update()
                .where(runs.c.run_id == run_id)
                .values(status="success", finished_at=now(), **counts)
            )
    except Exception as exc:
        # The load rolls back. Persist a failure marker without exposing SQL/credentials.
        with engine.begin() as conn:
            conn.execute(
                runs.update()
                .where(runs.c.run_id == run_id)
                .values(
                    status="failed",
                    finished_at=now(),
                    message=type(exc).__name__ + ": batch rolled back",
                )
            )
        raise
    return dict(run_id=run_id, status="success", **counts)
