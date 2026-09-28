from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)

metadata = MetaData()
suppliers = Table(
    "suppliers",
    metadata,
    Column("supplier_id", Integer, primary_key=True),
    Column("name", String(100), nullable=False),
    Column("lead_days", Integer, nullable=False),
    CheckConstraint("lead_days > 0"),
)
products = Table(
    "products",
    metadata,
    Column("product_id", Integer, primary_key=True),
    Column("supplier_id", ForeignKey("suppliers.supplier_id"), nullable=False),
    Column("name", String(100), nullable=False),
    Column("category", String(30), nullable=False),
    Column("size_ml", Integer, nullable=False),
    Column("cost_cents", Integer, nullable=False),
    Column("price_cents", Integer, nullable=False),
    CheckConstraint("cost_cents > 0 AND price_cents > 0 AND size_ml > 0"),
)
sales = Table(
    "sales",
    metadata,
    Column("sale_id", String(40), primary_key=True),
    Column("sold_at", DateTime, nullable=False),
    Column("payment", String(20), nullable=False),
)
sale_items = Table(
    "sale_items",
    metadata,
    Column("item_id", String(50), primary_key=True),
    Column("sale_id", ForeignKey("sales.sale_id"), nullable=False),
    Column("product_id", ForeignKey("products.product_id"), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("unit_price_cents", Integer, nullable=False),
    Column("unit_cost_cents", Integer, nullable=False),
    Column("discount_cents", Integer, nullable=False),
    CheckConstraint("quantity > 0 AND unit_price_cents > 0 AND unit_cost_cents >= 0"),
    CheckConstraint("discount_cents >= 0 AND discount_cents <= quantity * unit_price_cents"),
)
# Sales are derived from sale_items: never also enter them as stock movements.
movements = Table(
    "inventory_movements",
    metadata,
    Column("movement_id", String(50), primary_key=True),
    Column("product_id", ForeignKey("products.product_id"), nullable=False),
    Column("occurred_on", Date, nullable=False),
    Column("kind", String(20), nullable=False),
    Column("quantity", Integer, nullable=False),
    CheckConstraint("kind IN ('opening', 'delivery', 'breakage')"),
    CheckConstraint(
        "(kind = 'breakage' AND quantity < 0) OR (kind <> 'breakage' AND quantity > 0)"
    ),
)
batches = Table(
    "ingestion_batches",
    metadata,
    Column("batch_hash", String(64), primary_key=True),
    Column("loaded_at", DateTime, nullable=False),
)
runs = Table(
    "pipeline_runs",
    metadata,
    Column("run_id", String(36), primary_key=True),
    Column("batch_hash", String(64), nullable=False),
    Column("started_at", DateTime, nullable=False),
    Column("finished_at", DateTime),
    Column("status", String(20), nullable=False),
    Column("input_rows", Integer, nullable=False, default=0),
    Column("inserted_rows", Integer, nullable=False, default=0),
    Column("duplicate_rows", Integer, nullable=False, default=0),
    Column("rejected_rows", Integer, nullable=False, default=0),
    Column("message", Text),
)
raw = Table(
    "raw_records",
    metadata,
    Column("raw_id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", ForeignKey("pipeline_runs.run_id"), nullable=False),
    Column("source_table", String(40), nullable=False),
    Column("row_number", Integer, nullable=False),
    Column("payload", Text, nullable=False),
    Column("disposition", String(20), nullable=False),
    Column("reason", Text),
)
inventory_daily = Table(
    "inventory_daily",
    metadata,
    Column("stock_date", Date, primary_key=True),
    Column("product_id", ForeignKey("products.product_id"), primary_key=True),
    Column("on_hand", Integer, nullable=False),
    CheckConstraint("on_hand >= 0"),
)
Index("ix_sales_sold_at", sales.c.sold_at)
Index("ix_sale_items_product", sale_items.c.product_id)
Index("ix_movements_product_date", movements.c.product_id, movements.c.occurred_on)

SOURCE_TABLES = [suppliers, products, sales, sale_items, movements]

FACT_SQL = """SELECT i.item_id, i.sale_id, s.sold_at, i.product_id,
 p.name AS product, p.category, i.quantity,
 i.quantity * i.unit_price_cents - i.discount_cents AS revenue_cents,
 i.quantity * i.unit_cost_cents AS cogs_cents,
 i.quantity * (i.unit_price_cents - i.unit_cost_cents) - i.discount_cents AS profit_cents
 FROM sale_items i JOIN sales s ON i.sale_id = s.sale_id
 JOIN products p ON i.product_id = p.product_id"""


def initialize(engine):
    metadata.create_all(engine)
    with engine.begin() as conn:
        if engine.dialect.name == "mysql":
            conn.exec_driver_sql("CREATE OR REPLACE VIEW fact_sales AS " + FACT_SQL)
        else:
            conn.exec_driver_sql("CREATE VIEW IF NOT EXISTS fact_sales AS " + FACT_SQL)
