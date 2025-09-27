# faers-mini-signal

Local FAERS (FDA Adverse Event Reporting System) disproportionality analysis with DuckDB + Streamlit.
Computes PRR, ROR (95% CI), IC (95% CI) from normalized reports/drugs/reactions tables and provides a minimal UI.

## Quickstart

```
# Create venv (Python 3.11+)
py -3.11 -m venv .venv && . .venv/Scripts/activate  # PowerShell: .\\.venv\\Scripts\\Activate.ps1

# Install
pip install -e .[dev]

# Initialize DB (demo data) or ingest local openFDA JSON
faers-signal etl --source demo --db data/faers.duckdb
# or: faers-signal etl --source openfda --input path/to/openfda_events.zip --db data/faers.duckdb
# or: faers-signal etl --source qfiles --input path/to/faers_qfiles.zip --db data/faers.duckdb

# Build metrics (from existing DB)
faers-signal build --db data/faers.duckdb --out data/metrics.parquet

# Launch UI
faers-signal ui --db data/faers.duckdb
```

## 使い方 (Usage)

### インストール / セットアップ

- Python 3.11 以上を推奨します。
- 仮想環境の作成（PowerShell）: `python -m venv .venv; .\\.venv\\Scripts\\Activate.ps1`
- 開発インストール: `pip install -e .[dev]`（または `pip install -r requirements.txt`）

### CLI コマンド概要（`faers-signal`）

- `etl`（スキーマ初期化とデータ取り込み）
  - 例1: デモ投入 `faers-signal etl --source demo --db data/faers.duckdb`
  - 例2: openFDA のローカル zip/JSON を取り込み: `faers-signal etl --source openfda --input path/to/zip_or_dir --db data/faers.duckdb`
  - `--input` は `.zip` / `.json` / `.jsonl` / `.ndjson`（`.gz`対応可） もしくはそれらを含むディレクトリを指定。
  - `since`/`until` は `YYYY-MM-DD` で `receivedate` によるフィルタ。
- `build`（ABCD 集計と指標計算）
  - 例: `faers-signal build --db data/faers.duckdb --suspect-only true --min-a 3 --out data/metrics.parquet`
  - `--suspect-only false` で concomitant/interacting も含めた集計に切替。
  - 出力は拡張子で自動判定（`.parquet` または `.csv`）。
- `export`（任意 SELECT を CSV/Parquet へ）
  - 例: `faers-signal export --db data/faers.duckdb --sql "SELECT * FROM reports LIMIT 10" --out data/export.csv`
- `ui`（Streamlit UI 起動）
  - 例: `faers-signal ui --db data/faers.duckdb`

コマンドの詳細は `faers-signal --help` および各サブコマンドの `--help` を参照してください。

### UI の使い方（Streamlit）

- サイドバーでフィルタを設定：`Suspect only`/`Min A`/drug・PT の前方一致など。
- 本文に ABCD と各指標（PRR, ROR±CI, IC±CI, χ²）を表示。CSV ダウンロード可。
- UI 起動は `faers-signal ui --db data/faers.duckdb` が最も簡単です。

### 開発者向け（テスト・Lint）

- テスト実行: `pytest -q`
- Lint/Format（設定済みの場合）: `ruff check .` と `black .`
- パッケージ構成: `src/faers_signal/`（実装）, `tests/`（pytest）, `app/streamlit_app.py`（UI）

### データとSQLの位置づけ

- スキーマ: `src/faers_signal/schema.sql`
- ABCD 集計 SQL: `src/faers_signal/abcd.sql`
- いずれもパッケージに同梱され、CLI/UI から `importlib.resources` 経由で読み込みます。

### 追加ドキュメント

- 実行手順の詳細: `docs/USAGE.md`
- 仕様とマッピング: `docs/SPEC.md`
- 数式と背景: `docs/METHOD.md`
- トラブル対応: `docs/troubleshooting.md`

## Notes
- Schema lives in `src/faers_signal/schema.sql`; ABCD counts in `src/faers_signal/abcd.sql`.
- Ingestion functions are placeholders for EVP. Tests cover metrics math and ABCD SQL behavior.
- CLI/UI load packaged SQL via `importlib.resources`; packaging includes `.sql` and `app/streamlit_app.py`.
- This tool aids hypothesis generation only; FAERS data does not imply causality.

MIT License.

## Status (as of 2025-09-27)
- openFDA ローカルJSON/NDJSON/ZIPのETLは実装済み（`faers-signal etl --source openfda --input <file|dir>`）。
- 四半期ファイルETLはプレースホルダ（今後対応）。
- ABCD SQLはパッケージ同梱版をUI/CLIから読み込み、`build`/Streamlit UIが動作します。
- 詳細な進捗とTODOは `docs/PROGRESS.md` と `docs/TODO_REQUIREMENTS.md` を参照。

## Troubleshooting
- If you see `ModuleNotFoundError: No module named 'faers_signal'` when running the UI, install the package in editable mode (`pip install -e .`) or see `docs/troubleshooting.md` for alternatives.
