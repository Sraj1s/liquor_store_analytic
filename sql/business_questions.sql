-- MySQL 8.0+. Revenue/profit are USD, excluding tax and operating expenses.
-- 1. Monthly sales, gross profit and weighted gross margin.
SELECT DATE_FORMAT(sold_at, '%Y-%m') AS month,
       SUM(revenue_cents)/100 AS net_sales,
       SUM(profit_cents)/100 AS gross_profit,
       SUM(profit_cents)/NULLIF(SUM(revenue_cents),0) AS gross_margin
FROM fact_sales GROUP BY month ORDER BY month;

-- 2. Products ranked by gross profit (not just units).
SELECT product_id, product, category, SUM(quantity) AS units,
       SUM(profit_cents)/100 AS gross_profit,
       DENSE_RANK() OVER (ORDER BY SUM(profit_cents) DESC) AS profit_rank
FROM fact_sales GROUP BY product_id, product, category ORDER BY profit_rank;

-- 3. Busy hours: DISTINCT prevents counting a receipt once per item.
SELECT WEEKDAY(sold_at) AS weekday_monday_zero, HOUR(sold_at) AS hour,
       COUNT(DISTINCT sale_id) AS receipts
FROM fact_sales GROUP BY weekday_monday_zero, hour ORDER BY weekday_monday_zero, hour;

-- 4. Current stock: opening + deliveries - breakage - sold units.
SELECT i.stock_date, p.name, p.category, i.on_hand,
       i.on_hand*p.cost_cents/100 AS catalog_cost_stock_value
FROM inventory_daily i JOIN products p ON p.product_id=i.product_id
WHERE i.stock_date=(SELECT MAX(stock_date) FROM inventory_daily)
ORDER BY catalog_cost_stock_value DESC;

-- 5. Quarantine reasons are auditable.
SELECT reason, COUNT(*) AS rejected_records FROM raw_records
WHERE disposition='rejected' GROUP BY reason ORDER BY rejected_records DESC;
