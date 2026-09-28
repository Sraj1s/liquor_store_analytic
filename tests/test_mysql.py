"""Opt-in live integration test. Use a dedicated empty test database."""

import os

import pytest
from sqlalchemy import text

from liquor.db import get_engine
from liquor.generate import generate
from liquor.pipeline import ingest
from liquor.schema import initialize, metadata


@pytest.mark.skipif(
    os.getenv("RUN_MYSQL_TESTS") != "1", reason="Requires dedicated MySQL test database"
)
def test_live_mysql_load_rerun_and_constraints(tmp_path):
    if not os.environ.get("DB_NAME", "").endswith("_test"):
        pytest.fail("Live test requires a database name ending in _test")
    engine = get_engine()
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP VIEW IF EXISTS fact_sales")
    metadata.drop_all(engine)
    try:
        initialize(engine)
        generate(tmp_path / "mysql", days=8)
        result = ingest(engine, tmp_path / "mysql")
        assert result["rejected_rows"] == 3
        assert result["duplicate_rows"] == 5
        assert ingest(engine, tmp_path / "mysql")["status"] == "skipped"
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT COUNT(*) FROM fact_sales")) > 0
            assert (
                conn.scalar(
                    text("SELECT SUM(revenue_cents-cogs_cents-profit_cents) FROM fact_sales")
                )
                == 0
            )
            assert conn.scalar(text("SELECT MIN(on_hand) FROM inventory_daily")) >= 0
    finally:
        with engine.begin() as conn:
            conn.exec_driver_sql("DROP VIEW IF EXISTS fact_sales")
        metadata.drop_all(engine)
        engine.dispose()
