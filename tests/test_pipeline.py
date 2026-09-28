import csv
from datetime import date

import pytest
from sqlalchemy import text

from liquor.analytics import inventory_frame, sales_frame
from liquor.generate import generate
from liquor.pipeline import ingest


def scalar(engine, query):
    with engine.connect() as conn:
        return conn.scalar(text(query))


def rewrite(path, change):
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    change(rows)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_quality_reconciliation_and_exact_rerun(engine, tmp_path):
    folder = tmp_path / "base"
    generate(folder, days=8)
    result = ingest(engine, folder)
    assert result["rejected_rows"] == 3
    assert result["duplicate_rows"] == 5
    assert result["input_rows"] == sum(
        result[k] for k in ["inserted_rows", "duplicate_rows", "rejected_rows"]
    )
    expected, seen = 0, set()
    with (folder / "sale_items.csv").open() as f:
        for row in csv.DictReader(f):
            if row["item_id"].startswith("BAD") or row["item_id"] in seen:
                continue
            seen.add(row["item_id"])
            expected += int(row["quantity"]) * int(row["unit_price_cents"]) - int(
                row["discount_cents"]
            )
    assert scalar(engine, "SELECT SUM(revenue_cents) FROM fact_sales") == expected
    before = scalar(engine, "SELECT COUNT(*) FROM sale_items")
    assert ingest(engine, folder)["status"] == "skipped"
    assert scalar(engine, "SELECT COUNT(*) FROM sale_items") == before
    assert scalar(engine, "SELECT MIN(on_hand) FROM inventory_daily") >= 0
    assert scalar(engine, "SELECT COUNT(*) FROM raw_records") == result["input_rows"]
    assert scalar(engine, "SELECT COUNT(*) FROM raw_records WHERE disposition='rejected'") == 3


def test_extended_snapshot_loads_only_new_ids(engine, tmp_path):
    generate(tmp_path / "first", days=5)
    generate(tmp_path / "extended", days=6)
    ingest(engine, tmp_path / "first")
    before = scalar(engine, "SELECT COUNT(*) FROM sale_items")
    result = ingest(engine, tmp_path / "extended")
    assert result["status"] == "success"
    assert result["duplicate_rows"] > 5
    assert result["rejected_rows"] == 3
    assert scalar(engine, "SELECT COUNT(*) FROM sale_items") > before
    assert str(scalar(engine, "SELECT MAX(stock_date) FROM inventory_daily")) == "2026-03-06"
    assert ingest(engine, tmp_path / "extended")["status"] == "skipped"


def test_new_batch_same_records_does_not_inflate(engine, tmp_path):
    folder = tmp_path / "base"
    generate(folder, days=3)
    ingest(engine, folder)
    before = scalar(engine, "SELECT SUM(revenue_cents) FROM fact_sales")
    rewrite(folder / "sale_items.csv", lambda rows: rows.reverse())
    assert ingest(engine, folder)["inserted_rows"] == 0
    assert scalar(engine, "SELECT SUM(revenue_cents) FROM fact_sales") == before


def test_negative_inventory_rolls_back_whole_batch(engine, tmp_path):
    folder = tmp_path / "bad"
    generate(folder, days=3)

    def bad(rows):
        rows.append(
            dict(
                movement_id="IMPOSSIBLE",
                product_id="1",
                occurred_on="2026-03-03",
                kind="breakage",
                quantity="-999999",
            )
        )

    rewrite(folder / "inventory_movements.csv", bad)
    with pytest.raises(ValueError, match="Negative end-of-day"):
        ingest(engine, folder)
    assert scalar(engine, "SELECT COUNT(*) FROM products") == 0
    assert scalar(engine, "SELECT COUNT(*) FROM ingestion_batches") == 0
    assert scalar(engine, "SELECT COUNT(*) FROM pipeline_runs WHERE status='failed'") == 1
    rewrite(folder / "inventory_movements.csv", lambda rows: rows.pop())
    assert ingest(engine, folder)["status"] == "success"


def test_conflicting_ids_quarantined_not_overwritten(engine, tmp_path):
    folder = tmp_path / "base"
    generate(folder, days=3)
    ingest(engine, folder)
    before = scalar(engine, "SELECT SUM(revenue_cents) FROM fact_sales")
    rewrite(folder / "sale_items.csv", lambda rows: rows[0].update(unit_price_cents="99999"))
    assert ingest(engine, folder)["rejected_rows"] == 4
    assert scalar(engine, "SELECT SUM(revenue_cents) FROM fact_sales") == before


def test_metrics_inventory_and_calendar_denominator(engine, tmp_path):
    generate(tmp_path / "base", days=5)
    ingest(engine, tmp_path / "base")
    df = sales_frame(engine)
    assert (df.revenue_cents - df.cogs_cents == df.profit_cents).all()
    stock = inventory_frame(engine, date(2026, 3, 5))
    assert len(stock) == 100
    assert (stock.daily_units == stock.units_30d / 5).all()
    delivered = scalar(engine, "SELECT SUM(quantity) FROM inventory_movements")
    sold = scalar(engine, "SELECT SUM(quantity) FROM sale_items")
    assert stock.on_hand.sum() == delivered - sold


def test_schema_contract_prevents_partial_load(engine, tmp_path):
    folder = tmp_path / "badheader"
    generate(folder, days=2)
    path = folder / "products.csv"
    path.write_text(path.read_text().replace("product_id", "wrong_id", 1))
    with pytest.raises(ValueError, match="Wrong CSV header"):
        ingest(engine, folder)
    assert scalar(engine, "SELECT COUNT(*) FROM products") == 0


def test_reproducible_generation(tmp_path):
    generate(tmp_path / "a", days=3)
    generate(tmp_path / "b", days=3)
    for path in (tmp_path / "a").glob("*.csv"):
        assert path.read_bytes() == (tmp_path / "b" / path.name).read_bytes()
    with pytest.raises(ValueError, match="not empty"):
        generate(tmp_path / "a", days=3)
