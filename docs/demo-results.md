# Results from the default synthetic dataset

Generated with seed 42, March 1–August 30, 2026. These are simulation results, not evidence about an actual liquor business. Reproduce by following the README demo setup with the default 183-day generator.

| Measure | Result |
|---|---:|
| Receipts | 8,430 |
| Valid sale items | 16,926 |
| Units sold | 34,031 |
| Net sales | $1,281,251.03 |
| Gross profit | $368,505.53 |
| Gross margin | 28.76% |
| End-of-day units in stock | 3,213 |
| Catalog-cost stock value | $83,511.00 |
| Products at reorder point | 11 |

## Category comparison

| Category | Net sales | Gross profit | Units |
|---|---:|---:|---:|
| Whiskey | $749,780.21 | $203,487.71 | 20,329 |
| Rum | $161,776.60 | $50,184.60 | 3,849 |
| Gin | $136,669.59 | $43,427.09 | 3,732 |
| Vodka | $125,889.96 | $37,500.46 | 3,849 |
| Tequila | $107,134.67 | $33,905.67 | 2,272 |

## Interpretation and follow-up

- Whiskey contributes the most gross profit in this simulation. The generator deliberately makes the first 15 whiskey products more popular, so this is a recovery of a modeled assumption, not a market discovery.
- 5 products meet the demo slow-stock rule and hold $2,793.50 at catalog cost. In a real business, review seasonality and purchasing commitments before reducing orders.
- 11 products meet the reorder heuristic. Check incoming purchase orders and actual lead-time reliability before ordering; neither is modeled here.
- The five duplicate rows and three rejected rows do not contribute to sales or stock figures. Gross margin uses total profit divided by total sales.

## Provenance

Net sales, units and profit come from `fact_sales`, filtered through August 30. Inventory comes from `inventory_daily` on that date. Product names, categories and fixed costs come from `products`; reorder lead times come from `suppliers`. See `src/liquor/analytics.py` for the trailing-demand calculation. The operational dashboard can include later batches, so its totals may differ after the 184-day extension demonstration.
