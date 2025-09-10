# faers-mini-signal

Local FAERS (FDA Adverse Event Reporting System) disproportionality analysis with DuckDB + Streamlit.
Computes PRR, ROR (95% CI), IC (95% CI) from normalized reports/drugs/reactions tables and provides a minimal UI.

## Quickstart

```
# Create venv (example)
python -m venv .venv && . .venv/Scripts/activate  # PowerShell: .\\.venv\\Scripts\\Activate.ps1

# Install
pip install -e .[dev]

# Initialize DB (no data ingest in EVP; schema only)
faers-signal etl --source openfda --db data/faers.duckdb

# Build metrics (from existing DB)
faers-signal build --db data/faers.duckdb --out data/metrics.parquet

# Launch UI
faers-signal ui --db data/faers.duckdb
```

## Notes
- Schema lives in `src/faers_signal/schema.sql`; ABCD counts in `src/faers_signal/abcd.sql`.
- Ingestion functions are placeholders for EVP. Tests cover metrics math and ABCD SQL behavior.
- This tool aids hypothesis generation only; FAERS data does not imply causality.

MIT License.

