# Local setup troubleshooting

| Symptom | What to check |
|---|---|
| `python3` unavailable or older than 3.12 | Install a supported Python; use Python 3.12 for the reference environment |
| `liquor` or `streamlit` not found | Run `source .venv/bin/activate` inside the repository and install the requirements/package |
| MySQL connection refused | Confirm the MySQL server is running and `.env` host/port match Workbench. Workbench alone is not a server |
| MySQL access denied | Verify the local username/password and grants. A user created earlier keeps its prior password |
| Cannot read database | Run `liquor init` then `liquor load`, or the same commands with `--demo` for SQLite |
| MySQL CLI not found | Use Workbench for database/user setup; the Python application does not require the `mysql` command |
| Generator says directory is not empty | Reuse existing exports, or choose a new `--output` directory. It intentionally avoids overwriting evidence |
| Dashboard displays demo instead of MySQL | Run `unset LIQUOR_DEMO`, check `DB_BACKEND=mysql` in `.env`, then restart Streamlit |
| Empty category selection | Select at least one category; the dashboard deliberately shows a no-data message |
| Batch fails | Inspect `pipeline_runs` status; check source headers, required values and inventory consistency. No partial business batch is committed |
| Port 8501 is busy | Stop the other local Streamlit process or use `--server.port=8502` |

For an identical skipped batch, zero row-level processing counts are expected. A malformed file/header can fail before an attempt is logged. Failed runs store a safe exception class rather than SQL connection details; original CSVs remain available for investigation.

The app is intended for local use. Do not expose an unauthenticated Streamlit server or a MySQL port to the public Internet. Keep `.env`, generated databases and raw export directories out of Git.
