# Verification record

## Local checks completed on September 28, 2026

- Python 3.12, dependency environment installed from the project metadata.
- `ruff check src dashboard tests`: passed.
- `ruff format --check src dashboard tests`: passed.
- `python -m pytest -q`: **10 passed, 1 skipped**. The skipped test requires a live MySQL server; SQLite and Streamlit AppTest passed.
- Six-month CLI load: **26,292 input rows, 26,284 inserts, five duplicates, three rejects**.
- Identical batch replay: **skipped**, no business records added.
- Extended 184-day export: **110 new records**, 26,289 duplicate records, three rejects. Existing data remained unchanged.
- Rejected-record CSV export completed successfully.

A local graphical browser could not launch because this execution environment denies the required browser socket operation. Browser rendering is therefore tested separately in GitHub Actions rather than being claimed as locally verified.

## Automated verification

The workflow in `.github/workflows/tests.yml` provisions MySQL 8.0, installs locked dependencies, runs lint/format checks and the entire test suite including the live MySQL test. It then opens the dashboard in Chromium, verifies the three tabs and a CSV download, and saves desktop/mobile screenshots as `dashboard-verification` artifacts.

See [the repository Actions page](https://github.com/Sraj1s/liquor_store_analytic/actions) for current run status and logs. Screenshots and log artifacts have a 14-day retention window. This document records observed results; adding a workflow alone does not establish a passing run.

## Final observed CI result

[Run 36476642172](https://github.com/Sraj1s/liquor_store_analytic/actions/runs/36476642172) completed successfully on code commit `27c32c8730342e463df7eb4c08144bed9b0b9cff`:

- **11 tests passed**, including the live MySQL 8.0 integration and malformed-CSV regression.
- Lint and formatting checks passed.
- Chromium smoke test passed: chart rendering, all three tabs, and sales CSV download.
- Desktop and mobile screenshots were captured. The repository previews were visually reviewed from the preceding successful browser run; the final run used the same dashboard code.

Only documentation and captured screenshots were added after this tested code commit. Your Mac's particular MySQL installation and credentials still need the local connection steps in the README; CI does not configure your computer.
