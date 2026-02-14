# Progress Summary (2025-09-27)

This update focuses on making the ABCD SQL executable, loading packaged SQL reliably from installed wheels, and preparing packaging for distribution.

## Done
- Restored and verified `src/faers_signal/abcd.sql` with clean `CREATE TEMP TABLE ... AS` blocks (DuckDBで実行可能な体裁)。
- CLI and UI load packaged SQL via `importlib.resources` instead of repo-relative paths:
  - `cli._ensure_db()` loads `schema.sql` as a resource.
  - `cli.build` loads `abcd.sql` as a resource.
  - `app/streamlit_app.py` loads `abcd.sql` as a resource.
- Packaging (Hatch): include `.sql` files and `app/streamlit_app.py` in wheels/sdists to support `faers-signal ui` after installation.
- Added `LICENSE` (MIT) file.
- Implemented local openFDA JSON/NDJSON/ZIP ingest with idempotent upsert and date filters (`ingest_openfda.py`), including tests.
- Implemented minimal quarterly files ingest for DEMO/DRUG/REAC from zip/dir (`ingest_qfiles.py`), with role mapping (PS/SS=1, C=2, I=3).
- Added consolidated TODO/requirements doc (`docs/TODO_REQUIREMENTS.md`).

## Not Yet Implemented
- CI and pre-commit hooks are not configured.

## How to Verify Locally
1) Create venv and install:
   - `python -m venv .venv && . .venv/Scripts/activate` (PowerShell: `.\\.venv\\Scripts\\Activate.ps1`)
   - `pip install -e .[dev]`
2) Run tests:
   - `pytest -q`
3) Build metrics on a tiny hand-made dataset (optional):
   - Insert a few rows into `reports/drugs/reactions` in `data/faers.duckdb` (or use `tests/test_abcd_sql.py` as a reference), then run:
   - `faers-signal build --db data/faers.duckdb --out data/metrics.parquet`
4) Launch UI:
   - `faers-signal ui --db data/faers.duckdb`

## Next Steps
- Implement minimal quarterly files ingestion and small sample recipe.
- Add CI (lint/type/test) and pre-commit.
- Improve docs with screenshots and an end-to-end demo script.
