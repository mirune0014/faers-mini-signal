# faers-mini-signal リポジトリ調査サマリと利用ガイド

更新日: 2025-09-14

---

## TL;DR
FAERS（FDA有害事象報告システム）データをローカルの DuckDB に正規化し、薬剤×有害事象（PT）ごとの 2×2 表から PRR・ROR・IC（各 95%CI）などの不均衡指標を計算、Streamlit UI で探索できる最小ツールです。CLI エントリポイントは `faers-signal`。

本時点では ETL（openFDA/四半期ファイル）実装はプレースホルダで、スキーマ初期化・ABCD 集計・指標計算・UI は動作します（既存 DB がある場合）。

---

## このリポジトリが提供するもの
- スキーマ初期化（DuckDB）: `src/faers_signal/schema.sql`
- A/B/C/D 集計 SQL: `src/faers_signal/abcd.sql`
- 不均衡指標の計算: `src/faers_signal/metrics.py`（PRR, χ²(1df), ROR±CI, IC±CI）
- CLI ツール: `src/faers_signal/cli.py`（`etl`, `build`, `export`, `ui`, `version`）
- Streamlit UI: `app/streamlit_app.py`
- 単体テスト: `tests/test_metrics.py`, `tests/test_abcd_sql.py`
- ドキュメント: `docs/METHOD.md`（数式）, `docs/PROGRESS.md`（進捗/予定）

---

## ディレクトリ構成（抜粋）
```
faers-mini-signal/
  pyproject.toml           # パッケージ/依存/ビルド設定（Hatch）
  README.md                # 英語のクイックスタート
  src/faers_signal/
    __init__.py
    cli.py                 # Typer CLI（faers-signal）
    metrics.py             # 指標計算（PRR/ROR/IC/χ²）
    schema.sql             # DuckDB スキーマ
    abcd.sql               # A/B/C/D 集計
    ingest_openfda.py      # openFDA 取り込み（プレースホルダ）
    ingest_qfiles.py       # 四半期ファイル取り込み（プレースホルダ）
  app/streamlit_app.py     # UI（Streamlit）
  tests/
    test_metrics.py
    test_abcd_sql.py
  docs/
    METHOD.md              # 数式と近似
    PROGRESS.md            # 進捗/今後
```

---

## セットアップと基本操作
PowerShell 例（Windows）:

```powershell
# 1) 仮想環境とインストール
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e .[dev]    # または: pip install -r requirements.txt

# 2) DB 初期化（スキーマ適用）
faers-signal etl --source openfda --db data/faers.duckdb
# ※ 現状の etl はプレースホルダ。実データ投入は未実装です。

# 3) ABCD→メトリクス計算
faers-signal build --db data/faers.duckdb --out data/metrics.parquet

# 4) UI 起動（環境変数で DB を指定して起動します）
faers-signal ui --db data/faers.duckdb

# 5) 任意のクエリをエクスポート
faers-signal export --db data/faers.duckdb --sql "SELECT * FROM reports LIMIT 10" --out data/export.csv

# 6) テスト実行
pytest -q
```

---

## 指標の定義（概要）
- PRR = (A/(A+B)) / (C/(C+D))
- χ²(1df, Yates) = ((|AD−BC| − N/2)^2 × N) / ((A+B)(C+D)(A+C)(B+D))
- ROR = (A/B) / (C/D); 95%CI は ln(ROR)±1.96×sqrt(1/A+1/B+1/C+1/D)
- IC = log2(A/E[A]); E[A]=(A+B)(A+C)/N; 95%CI は正規近似
- 数値安定性のため微小値 EPS を使用。詳細は `docs/METHOD.md` を参照。

---

## UI の主な操作
- サイドバー: suspect 限定（role=1）の ON/OFF、A の下限、`drug`/`pt` の前方一致フィルタ。
- 本体: `drug, pt, A, B, C, D, PRR, ROR, ROR_CI_L/U, IC, IC_CI_L/U, Chi2_1df` を一覧表示。
- 「Download CSV」ボタンでテーブルを CSV 出力。

---

## 既知の制限・注意事項（2025-09-14 時点）
1. ETL 未実装
   - `ingest_openfda.py` / `ingest_qfiles.py` はプレースホルダです。実データ投入には拡張が必要です。
2. `abcd.sql` の体裁
   - 本リポの `src/faers_signal/abcd.sql` にはコメントと `CREATE` が同一行に連結された箇所が残っており、DuckDB での実行に失敗する可能性があります（例: `-- ... CREATE TEMP TABLE ...`）。
   - 期待形は `docs/PROGRESS.md` 記載の通り、`CREATE TEMP TABLE ... AS` ブロックが独立行で並ぶ形です。実行エラーの際は該当行を改行分離してください。
3. ドキュメントの文字化け
   - `READ.md` と `siyou.md` に文字化けが見られます。本ドキュメントが日本語の要約として代替します。
4. パス表記の揺れ
   - `AGENTS.md` に `src/faers_mini_signal/` の表記がありますが、実体は `src/faers_signal/` が正です。
5. 免責
   - 本ツールは仮説生成支援を目的としたもので、FAERS データは因果を示しません。分母不明、報告バイアス、重複可能性などの制約があります。

---

## よく使うオプション
- `faers-signal build --suspect-only/--no-suspect-only` で suspect 限定の切替（既定: 限定）。
- `--min-a` で A の最小件数フィルタ（既定: 3）。
- 出力は拡張子で自動切替（`.csv`/`.parquet`）。

---

## 参考
- クイックスタート: `README.md`
- 数式と近似: `docs/METHOD.md`
- 進捗・今後の計画: `docs/PROGRESS.md`
- テスト: `tests/test_metrics.py`, `tests/test_abcd_sql.py`

---

## ライセンス
MIT License（`LICENSE` を参照）。

