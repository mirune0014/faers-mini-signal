# TODO と 要件定義（faers-mini-signal）

最終更新: 2025-09-27

本ドキュメントは、現状の到達点、優先度付きTODO、機能/非機能要件、受け入れ条件を一箇所にまとめたものです。以後の実装・修正は本書のP0から順に進めます。

## 現状サマリ（2025-09-27）
- スキーマとABCD集計クエリを同梱（`schema.sql`, `abcd.sql`）。
- 指標（PRR, ROR±CI, IC±CI, χ2 1df）は `metrics.py` で実装済み。単体テストあり。
- openFDAローカルJSON/NDJSON/ZIPのETLは実装済み（`ingest_openfda.py`）。冪等（`safetyreportid`単位）。
- CLI（`faers-signal`）とStreamlit UIあり（`build/export/ui`）。
- 四半期ファイルETLはプレースホルダ（`ingest_qfiles.py`）。
- 一部ドキュメントの文字化け/不整合あり。

## 優先度付き TODO

### P0（今すぐ対応）
- ABCD SQLの整形修正（DuckDBでそのまま実行可能な体裁にする）。
- README「Status」を現状に合わせて更新（openFDAローカルETLは実装済み）。
- `AGENTS.md` のパス誤記（`faers_mini_signal` → `faers_signal`）を修正。
- 本ドキュメント（TODO/要件）を追加し、進捗の基準にする。

### P1（次段）
- openFDA ETLの堅牢化（欠損/型不整合の警告ログ、テスト追加、正規化ポリシーの明文化）。
- 四半期ファイルETLの最小実装（小さなASCII/CSVサンプルで `reports/drugs/reactions` に投入）。
- UIの利便性向上（閾値ハイライト、任意ソート、`since/until` フィルタ、`st.cache_data`）。
- `build` コマンドのテスト追加（suspect-only切替、`min-a`、CSV/Parquetの両方）。
- pre-commitとCI（ruff/black/mypy/pytest）導入。

### P2/P3（将来検討）
- openFDA zipped JSONのオンライン取得（レート/リトライ/キャッシュ）オプション。
- 追加指標（EBGM 等）、層別/時系列、重複解決高度化。
- パッケージ配布（PyPI）、スクリーンショット/e2eデモ整備。

## 機能要件（ドラフト）
- データ取り込み
  - 入力: `.json`/`.jsonl`/`.ndjson`（`.gz`可）、`.zip`（上記を内包）、ディレクトリ再帰。
  - フィルタ: `--since/--until`（`receivedate`、YYYY-MM-DD）、`--limit`（0は無制限）。
  - 冪等: `safetyreportid` 単位で既存行を削除→挿入。
- スキーマ（DuckDB）
  - `reports(safetyreportid PK, receivedate, primarysource_qualifier)`
  - `drugs(safetyreportid FK, drug_name, role)`（1: suspect, 2: concomitant, 3: interacting）
  - `reactions(safetyreportid FK, meddra_pt)`
- 集計/出力
  - ABCD集計（既定: suspect-only）。`--no-suspect-only` で role in (1,2,3)。
  - 指標: PRR, χ2(1df), ROR±95%CI, IC±95%CI。`--min-a` でA件数フィルタ。
  - 出力は拡張子で自動切替（`.parquet`/`.csv`）。
- UI
  - フィルタ（suspect-only, Min A, drug/PT前方一致）。表・CSVダウンロード。DBパス指定。
- エクスポート
  - 任意SELECT → CSV/Parquet。

## 非機能要件（ドラフト）
- 環境: Python 3.11+。ローカル完結。Windows PowerShell手順も提示。
- 品質: ruff/black/mypy/pytest、CIで最小検証。小規模データで即時応答。
- ドキュメント: Quickstart/USAGE/METHOD/SPEC/Troubleshooting、免責の明記。
- データ: PII/PHIのコミット禁止。サンプルは合成。

## 受け入れ条件（MVP）
- `pytest -q` が緑（`metrics` と `abcd.sql`、`ingest_openfda` の基本テスト）。
- `faers-signal etl --source demo --db data/faers.duckdb` → `build` → `ui` が通る。
- ローカルopenFDA ZIPで `etl --source openfda --input <zip>` が通り、`build` で指標が出力される。
- `abcd.sql` がDuckDBでエラーなく実行可能。

## 既知の制限/保留
- 四半期ファイルETLは未実装（P1）。
- 一部ドキュメントの文字化け（別PRで是正予定）。

