-- Generated reference DDL. The supported installer is: liquor init
-- MySQL 8.0.16+; all currency fields are integer USD cents.


CREATE TABLE ingestion_batches (
	batch_hash VARCHAR(64) NOT NULL, 
	loaded_at DATETIME NOT NULL, 
	PRIMARY KEY (batch_hash)
)

;


CREATE TABLE pipeline_runs (
	run_id VARCHAR(36) NOT NULL, 
	batch_hash VARCHAR(64) NOT NULL, 
	started_at DATETIME NOT NULL, 
	finished_at DATETIME, 
	status VARCHAR(20) NOT NULL, 
	input_rows INTEGER NOT NULL, 
	inserted_rows INTEGER NOT NULL, 
	duplicate_rows INTEGER NOT NULL, 
	rejected_rows INTEGER NOT NULL, 
	message TEXT, 
	PRIMARY KEY (run_id)
)

;


CREATE TABLE sales (
	sale_id VARCHAR(40) NOT NULL, 
	sold_at DATETIME NOT NULL, 
	payment VARCHAR(20) NOT NULL, 
	PRIMARY KEY (sale_id)
)

;

CREATE INDEX ix_sales_sold_at ON sales (sold_at);


CREATE TABLE suppliers (
	supplier_id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(100) NOT NULL, 
	lead_days INTEGER NOT NULL, 
	PRIMARY KEY (supplier_id), 
	CHECK (lead_days > 0)
)

;


CREATE TABLE products (
	product_id INTEGER NOT NULL AUTO_INCREMENT, 
	supplier_id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	category VARCHAR(30) NOT NULL, 
	size_ml INTEGER NOT NULL, 
	cost_cents INTEGER NOT NULL, 
	price_cents INTEGER NOT NULL, 
	PRIMARY KEY (product_id), 
	CHECK (cost_cents > 0 AND price_cents > 0 AND size_ml > 0), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (supplier_id)
)

;


CREATE TABLE raw_records (
	raw_id INTEGER NOT NULL AUTO_INCREMENT, 
	run_id VARCHAR(36) NOT NULL, 
	source_table VARCHAR(40) NOT NULL, 
	`row_number` INTEGER NOT NULL, 
	payload TEXT NOT NULL, 
	disposition VARCHAR(20) NOT NULL, 
	reason TEXT, 
	PRIMARY KEY (raw_id), 
	FOREIGN KEY(run_id) REFERENCES pipeline_runs (run_id)
)

;


CREATE TABLE inventory_daily (
	stock_date DATE NOT NULL, 
	product_id INTEGER NOT NULL, 
	on_hand INTEGER NOT NULL, 
	PRIMARY KEY (stock_date, product_id), 
	CHECK (on_hand >= 0), 
	FOREIGN KEY(product_id) REFERENCES products (product_id)
)

;


CREATE TABLE inventory_movements (
	movement_id VARCHAR(50) NOT NULL, 
	product_id INTEGER NOT NULL, 
	occurred_on DATE NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	quantity INTEGER NOT NULL, 
	PRIMARY KEY (movement_id), 
	CHECK (kind IN ('opening', 'delivery', 'breakage')), 
	CHECK ((kind = 'breakage' AND quantity < 0) OR (kind <> 'breakage' AND quantity > 0)), 
	FOREIGN KEY(product_id) REFERENCES products (product_id)
)

;

CREATE INDEX ix_movements_product_date ON inventory_movements (product_id, occurred_on);


CREATE TABLE sale_items (
	item_id VARCHAR(50) NOT NULL, 
	sale_id VARCHAR(40) NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity INTEGER NOT NULL, 
	unit_price_cents INTEGER NOT NULL, 
	unit_cost_cents INTEGER NOT NULL, 
	discount_cents INTEGER NOT NULL, 
	PRIMARY KEY (item_id), 
	CHECK (quantity > 0 AND unit_price_cents > 0 AND unit_cost_cents >= 0), 
	CHECK (discount_cents >= 0 AND discount_cents <= quantity * unit_price_cents), 
	FOREIGN KEY(sale_id) REFERENCES sales (sale_id), 
	FOREIGN KEY(product_id) REFERENCES products (product_id)
)

;

CREATE INDEX ix_sale_items_product ON sale_items (product_id);

CREATE OR REPLACE VIEW fact_sales AS SELECT i.item_id, i.sale_id, s.sold_at, i.product_id,
 p.name AS product, p.category, i.quantity,
 i.quantity * i.unit_price_cents - i.discount_cents AS revenue_cents,
 i.quantity * i.unit_cost_cents AS cogs_cents,
 i.quantity * (i.unit_price_cents - i.unit_cost_cents) - i.discount_cents AS profit_cents
 FROM sale_items i JOIN sales s ON i.sale_id = s.sale_id
 JOIN products p ON i.product_id = p.product_id;
