# Usage Guide (faers-mini-signal)

This guide explains how to set up the environment, ingest data, build metrics, and launch the UI.

## Prerequisites

- Python 3.11+ (Windows PowerShell examples below)
- Optional: DuckDB CLI for ad-hoc queries

## Setup

```
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

Run tests (optional): `pytest -q`

## Path A: Try with Demo Data (quickest)

1) Create (or reset) DuckDB and load a tiny demo dataset:

```
faers-signal etl --source demo --db data/faers.duckdb
```

2) Build metrics (ABCD → PRR/ROR/IC/χ²):

```
faers-signal build --db data/faers.duckdb --out data/metrics.parquet
```

3) Launch the Streamlit UI:

```
faers-signal ui --db data/faers.duckdb
```

## Path B: Ingest local openFDA JSON/ZIP

- Download openFDA Drug Adverse Event data locally (JSON/NDJSON or ZIP).
- Supported inputs for `--input`:
  - Files: `.json`, `.jsonl`, `.ndjson` (optionally `.gz`)
  - Archives: `.zip` containing the above
  - Directories: processed recursively for matching files

Ingest command:

```
faers-signal etl --source openfda --input path\to\openfda_events.zip --db data\faers.duckdb --since 2024-01-01 --until 2024-12-31 --limit 0
```

Notes:
- `--since` / `--until` filter on `receivedate` (YYYY-MM-DD)
- `--limit` caps the number of reports ingested (`0` = no limit)
- Ingest is idempotent per `safetyreportid` (re-inserting same IDs overwrites rows)

Then run `build` and `ui` as in the demo path.

## Path C: Ingest FAERS Quarterly Files (minimal)

- Prepare a zip or directory containing DEMO/DRUG/REAC tables (pipe/tab/csv delimited, with headers).
- Minimal expected columns (case-insensitive):
  - DEMO: `PRIMARYID`, `FDA_DT` (YYYYMMDD)
  - DRUG: `PRIMARYID`, `DRUGNAME`, `ROLE_COD` (PS/SS/C/I)
  - REAC: `PRIMARYID`, `PT`

Ingest command:

```
faers-signal etl --source qfiles --input path\to\faers_qfiles.zip --db data\faers.duckdb --since 2024-01-01 --until 2024-12-31
```

Notes:
- `--since` / `--until` filter on FDA_DT (normalized to YYYY-MM-DD).
- ROLE_COD is mapped as PS/SS=1, C=2, I=3.

## Export arbitrary SELECT

```
faers-signal export --db data/faers.duckdb --sql "SELECT * FROM reports LIMIT 10" --out data/export.csv
```

## What the UI shows

- Sidebar filters: suspect-only, min A, startswith filters for `drug` and `pt`
- Main table: ABCD counts and metrics (PRR, ROR±CI, IC±CI, χ²)
- CSV download of the current table

## Project Layout (relevant files)

- `src/faers_signal/schema.sql` — DB schema (reports/drugs/reactions)
- `src/faers_signal/abcd.sql` — ABCD aggregation query
- `src/faers_signal/metrics.py` — metric functions (PRR/ROR/IC/χ²)
- `src/faers_signal/cli.py` — Typer CLI (`faers-signal`)
- `app/streamlit_app.py` — Streamlit UI

## Tips & Troubleshooting

- If imports fail in the UI, ensure editable install: `pip install -e .[dev]` or see `docs/troubleshooting.md`.
- If the schema is missing, run `faers-signal etl --source demo --db data/faers.duckdb` to initialize.
- Windows PowerShell: activate venv via `. .\.venv\Scripts\Activate.ps1`
