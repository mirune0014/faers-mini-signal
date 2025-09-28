**Troubleshooting**

- **Error**: `ModuleNotFoundError: No module named 'faers_signal'` when running `app/streamlit_app.py`.

- **Root Cause**: The project uses a `src/`-layout (`src/faers_signal`). When you run a script directly with `python app/streamlit_app.py`, Python’s import path doesn’t include `src/` unless the package is installed (editable or wheel) or `PYTHONPATH` is set. As a result, `from faers_signal...` fails.

- **Solutions** (choose one):
  - Recommended: install the package in editable mode.
    - PowerShell
      - `python -m venv .venv; .\.venv\Scripts\Activate.ps1`
      - `pip install -e .`  (or `pip install -e .[dev]`)
      - Run the app: `streamlit run app/streamlit_app.py`
  - Quick run without install: set `PYTHONPATH` for the process.
    - PowerShell: `$env:PYTHONPATH = 'src'; python app/streamlit_app.py`

- **What changed**: `app/streamlit_app.py` now prepends the repo’s `src/` directory to `sys.path` when run directly, so it works even if you haven’t done an editable install. Installing with `pip install -e .` remains the recommended approach for development and avoids import issues in all commands.

- **Python version**: This project targets Python 3.11+ (see `pyproject.toml`). If you are on Python 3.8/3.9, you may hit `AttributeError: module 'importlib.resources' has no attribute 'files'`. Fix by upgrading to Python 3.11+ and reinstalling the venv, for example:
  - `py -3.11 -m venv .venv; .\.venv\Scripts\Activate.ps1`
  - `pip install -e .[dev]`
  - `streamlit run app/streamlit_app.py`

- **Streamlit invocation**: Prefer `streamlit run app/streamlit_app.py` over `python app/streamlit_app.py` for the full UI experience. The latter can work after the path fix but is not the standard way to run Streamlit apps.

- **DuckDB schema missing**: If you see an error like `Catalog Error: Table 'reports' does not exist`, initialize the DB schema first:
  - CLI (after install): `faers-signal etl --source openfda --db data/faers.duckdb` (ingest is a placeholder; this creates schema).
  - Or minimal snippet: `python - << "PY"\nfrom pathlib import Path; import duckdb; p=Path('src/faers_signal/schema.sql'); s=p.read_text(encoding='utf-8'); con=duckdb.connect('data/faers.duckdb'); con.execute(s); print('schema ok')\nPY`
