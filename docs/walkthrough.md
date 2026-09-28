# Understand and demonstrate the project

## The story you should be able to explain

A fictional store has separate sales, product and stock records. We build a repeatable way to turn those records into trustworthy tables, then answer questions about revenue, margins and inventory. We deliberately inject bad data so reliability can be demonstrated, not merely claimed.

## Walk through one purchase

A receipt contains two bottles priced at $25 each, with a $5 line discount. Each bottle cost the store $18.

- The receipt appears once in `sales`; its line appears once in `sale_items`.
- The line stores quantity 2, unit price 2500 cents, unit cost 1800 cents and discount 500 cents.
- Net sales = 2 × 2500 − 500 = 4500 cents ($45).
- COGS = 2 × 1800 = 3600 cents ($36).
- Gross profit = 900 cents ($9), and margin = 9 / 45 = 20%.
- Inventory decreases by two. The receipt count is one, regardless of how many other lines it contains.

## Five-minute demonstration

1. Open the dashboard. Explain that the data is simulated and point to the time window.
2. Filter one category. Show how net sales, profit, product rankings and downloads change together.
3. Open Inventory decisions. Explain a restocking queue row using its stock, demand and supplier lead time.
4. Open Pipeline health. Find the three rejected records and read their reasons.
5. In Terminal, run `liquor load --demo` again. Show `skipped`, refresh the dashboard and explain why revenue stayed unchanged.
6. Load the 184-day extended export from the README. Explain that only new IDs are inserted, while inventory snapshots are recomputed.
7. Run `python -m pytest -q`. Explain what the rollback and reconciliation tests prove and which database backend was tested.

## Questions to prepare for

**Why split sales and sale items?** One purchase can contain many products. Separating header and line data avoids repeating header fields and permits correct receipt counts.

**What does idempotent mean here?** Reprocessing an identical batch, or a reordered batch with the same business IDs and values, does not increase business totals.

**Why preserve rejected records?** To show exactly what failed and where it came from. Guessing a missing product or silently fixing a negative quantity would create unsupported business facts.

**Why store cents rather than float dollars?** Integer arithmetic keeps financial reconciliation exact within the supported amount range. Formatting to dollars happens only for display.

**What is incremental?** New IDs append to normalized tables. Extraction is a full CSV snapshot and daily inventory is fully refreshed. Do not call this CDC or a streaming pipeline.

**Why could a batch fail after row validation?** Individually valid stock movements can collectively make inventory negative. That cross-record invariant rolls the transaction back.

**What would you improve at scale?** Chunked extraction, a source watermark or CDC, changed-record handling, migrations, orchestration, monitored SLAs, and a database-enforced single-writer lock. Those are future improvements, not current features.

**Can these simulated findings guide a real business?** No. The project proves mechanics. Real recommendations require actual sales, costs, supplier performance and business context.
