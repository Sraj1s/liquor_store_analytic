# Verification record

## Local checks completed on September 28, 2026

- Python 3.12, dependency environment installed from the project metadata.
- `ruff check src dashboard tests`: passed.
- `ruff format --check src dashboard tests`: passed.
- `python -m pytest -q`: **9 passed, 1 skipped**. The skipped test requires a live MySQL server; SQLite and Streamlit AppTest passed.
- Six-month CLI load: **26,292 input rows, 26,284 inserts, five duplicates, three rejects**.
- Identical batch replay: **skipped**, no business records added.
- Extended 184-day export: **110 new records**, 26,289 duplicate records, three rejects. Existing data remained unchanged.
- Rejected-record CSV export completed successfully.

A local graphical browser could not launch because this execution environment denies the required browser socket operation. Browser rendering is therefore tested separately in GitHub Actions rather than being claimed as locally verified.

## Automated verification

The workflow in `.github/workflows/tests.yml` provisions MySQL 8.0, installs locked dependencies, runs lint/format checks and the entire test suite including the live MySQL test. It then opens the dashboard in Chromium, verifies the three tabs and a CSV download, and saves desktop/mobile screenshots as `dashboard-verification` artifacts.

See [the repository Actions page](https://github.com/Sraj1s/liquor_store_analytic/actions) for current run status and logs. Screenshots and log artifacts have a 14-day retention window. This document records observed results; adding a workflow alone does not establish a passing run.
