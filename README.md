# faers-mini-signal

DuckDB と Streamlit を使ってローカルで FAERS（FDA Adverse Event Reporting System）の不均衡解析（PRR / ROR±95%CI / IC±95%CI）を行うツールです。正規化済みの `reports` / `drugs` / `reactions` テーブルから ABCD を集計し、指標を計算して最小限の UI に表示します。

## クイックスタート（Windows PowerShell 想定）

```
# 1) 仮想環境を作成（Python 3.11+）
py -3.11 -m venv .venv; . .\.venv\Scripts\Activate.ps1

# 2) 依存関係をインストール（編集可能インストール）
pip install -e .[dev]

# 3) デモデータでDB初期化（または openFDA / 四半期ファイルを取り込み）
faers-signal etl --source demo --db data\faers.duckdb
# 例: openFDA ローカルZIP/JSONを取り込み
# faers-signal etl --source openfda --input "C:\\path\\to\\openfda_events.zip" --db data\faers.duckdb
# 例: 四半期ファイル（DEMO/DRUG/REAC）を取り込み
# faers-signal etl --source qfiles --input "C:\\path\\to\\faers_qfiles.zip" --db data\faers.duckdb

# 4) （任意）ファイルに書き出す場合の指標計算
faers-signal build --db data\faers.duckdb --out data\metrics.parquet

# 5) UI を起動
faers-signal ui --db data\faers.duckdb
```

macOS/Linux の例:

```
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
faers-signal etl --source demo --db data/faers.duckdb
faers-signal ui --db data/faers.duckdb
```

## 実行手順（詳細）

### インストール / セットアップ

- Python 3.11 以上を推奨します。
- 仮想環境の作成（PowerShell）: `python -m venv .venv; .\\.venv\\Scripts\\Activate.ps1`
- 依存関係の導入: `pip install -e .[dev]`（または `pip install -r requirements.txt`）

### データ取り込み（ETL）

- デモデータ（最短動作確認）
  - `faers-signal etl --source demo --db data\faers.duckdb`

- openFDA ローカル JSON/NDJSON/ZIP を取り込み
  - 入力形式: `.json` / `.jsonl` / `.ndjson`（必要に応じて `.gz`）/ これらを含む `.zip` / それらを含むディレクトリ
  - 例（ZIP 1 ファイルを指定）:
    - `faers-signal etl --source openfda --input "C:\\Users\\<YOU>\\Downloads\\drug-event-0001-of-0031.json.zip" --db data\faers.duckdb --limit 50000`
  - 例（ディレクトリを指定）:
    - `faers-signal etl --source openfda --input "D:\\openfda\\events_dir" --db data\faers.duckdb`
  - 期間で絞る場合: `--since 2024-01-01 --until 2024-12-31`（`receivedate` によるフィルタ）
  - 同一 `safetyreportid` は上書き（冪等）

- FAERS 四半期ファイル（DEMO/DRUG/REAC）を取り込み（最小実装）
  - 例: `faers-signal etl --source qfiles --input "C:\\path\\to\\faers_qfiles.zip" --db data\faers.duckdb --since 2024-01-01 --until 2024-12-31`
  - 期待列（最低限, 大文字小文字は不問）:
    - DEMO: `PRIMARYID`, `FDA_DT` (YYYYMMDD)
    - DRUG: `PRIMARYID`, `DRUGNAME`, `ROLE_COD` (PS/SS/C/I → 1/1/2/3 に正規化)
    - REAC: `PRIMARYID`, `PT`

### 指標計算・エクスポート

- ABCD 集計と指標（PRR, ROR±CI, IC±CI, χ²）のファイル出力（任意）
  - `faers-signal build --db data\faers.duckdb --suspect-only true --min-a 3 --out data\metrics.parquet`
  - 出力は拡張子で自動判定（`.parquet` または `.csv`）

- 任意の SELECT を CSV/Parquet へエクスポート
  - `faers-signal export --db data\faers.duckdb --sql "SELECT * FROM reports LIMIT 10" --out data\export.csv`

### UI の使い方（Streamlit）

- サイドバーでフィルタを設定（Suspect only / Min A / drug・PT の前方一致）
- 本文に ABCD と各指標（PRR, ROR±CI, IC±CI, χ²）を表示。CSV ダウンロード可
- 起動は `faers-signal ui --db data\faers.duckdb` が簡単。直接起動する場合は以下:
  - `streamlit run app/streamlit_app.py`（環境変数 `FAERS_DB` で DB を指定可）

### 開発者向け（テスト・Lint）

- テスト: `pytest -q`
- Lint/Format: `ruff check .` と `black .`
- 主な配置: `src/faers_signal/`（実装）, `tests/`（pytest）, `app/streamlit_app.py`（UI）

### データと SQL の配置

- スキーマ: `src/faers_signal/schema.sql`
- ABCD 集計 SQL: `src/faers_signal/abcd.sql`
- いずれもパッケージに同梱され、CLI/UI から `importlib.resources` 経由で読み込みます

## トラブルシューティング（抜粋）

- `faers-signal` が見つからない
  - 仮想環境を有効化して `pip install -e .[dev]`
  - 代替: `python -m faers_signal.cli ...` または `.\.venv\Scripts\faers-signal.exe ...`

- `ModuleNotFoundError: No module named 'faers_signal'`
  - 編集可能インストールを実施（上記）。`streamlit run` で起動する場合も推奨

- `streamlit run` でファイルが見つからない
  - CLI 側でパス解決を改善済み。改善前の環境なら `streamlit run app/streamlit_app.py` を使用

- `UnicodeDecodeError`（openFDA 取り込み時）
  - `.json.zip` を zip として正しく処理するよう修正済み。引き続き再現する場合はファイル形式を確認

- スキーマがない/テーブル不存在
  - まず `faers-signal etl --source demo --db data\faers.duckdb` を実行（スキーマ初期化）

より詳しい説明は `docs/USAGE.md` と `docs/troubleshooting.md` を参照してください。

## 備考
- スキーマは `src/faers_signal/schema.sql`、ABCD 集計は `src/faers_signal/abcd.sql`
- CLI/UI は `importlib.resources` で同梱 SQL と UI を読み込みます
- 本ツールは仮説立案支援を目的としたもので、FAERS データは因果関係を保証するものではありません

MIT License.

## ステータス（2025-09-27 時点）
- openFDA のローカル JSON/NDJSON/ZIP 取り込みは実装済み（`faers-signal etl --source openfda --input <file|dir>`）
- 四半期ファイル取り込みは最小実装（将来拡張の予定）
- ABCD SQL はパッケージ同梱版を UI/CLI から読み込み、`build` / Streamlit UI が動作
- 進捗や TODO はリポジトリ内のドキュメントを参照
