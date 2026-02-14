# faers-mini-signal

DuckDB と Streamlit を使って FAERS（FDA Adverse Event Reporting System）の不均衡解析（PRR / ROR±95%CI / IC±95%CI）を行うツールです。正規化済みの `reports` / `drugs` / `reactions` テーブルから ABCD 分割表を集計し、指標を計算して UI に表示します。

## 背景・目的

- 公式の FAERS Public Dashboard は主に件数ベースの記述統計に特化しており、再現可能な PRR/ROR/IC などの不均衡指標は提供されません。
- 本ツールはローカル完結・再現可能なパイプラインを提供し、手元の PC で柔軟にデータ取り込み～指標計算～可視化まで行えることを目的とします。
- 研究・業務の仮説生成を支援する用途を想定しています（因果関係の証明を目的としません）。

## 主な機能

- **シグナル検出指標**: PRR, ROR±95%CI, IC±95%CI, χ²（Yates 補正付き）
- **シグナル判定ハイライト**: Evans 3 条件（PRR≥2, χ²≥4, A≥3）/ ROR 下限CI>1 / IC 下限CI>0 を自動判定し、⚠️ マーク＋色分け表示
- **可視化（仮設）**: Volcano Plot / バブルチャート / ヒートマップ（選択式）
- **openFDA API ダウンロード**: UI のサイドバーから薬剤名・期間を指定して直接データ取得（最大 26,000 件）
- **複数のデータソース**: openFDA ローカル JSON/ZIP、FAERS 四半期ファイル、デモデータ
- **ゼロセル補正**: Haldane–Anscombe 補正（+0.5）による安定した指標計算
- **サンプルデータ同梱**: 5,000 件の実 FAERS データ（`data/sample.duckdb`）がリポジトリに含まれており、セットアップ直後から分析可能

## Streamlit Cloud で試す

以下の URL でデモを確認できます（サンプルデータ 5,000 件で動作）:

> デプロイ URL をここに記載してください

## ローカルで使う

### セットアップ

```bash
# 仮想環境を作成（Python 3.11+）
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate

# 依存関係をインストール
pip install -e .[dev]
```

### データ取り込み

**方法1: デモデータ（最短動作確認）**
```bash
faers-signal etl --source demo --db data/faers.duckdb
```

**方法2: openFDA ローカルファイル**
```bash
# ZIP/JSON/NDJSON に対応
faers-signal etl --source openfda --input "path/to/drug-event.json.zip" --db data/faers.duckdb
# 期間で絞る場合
faers-signal etl --source openfda --input "path/to/events" --db data/faers.duckdb --since 2024-01-01 --until 2024-12-31
```

**方法3: FAERS 四半期ファイル（DEMO/DRUG/REAC）**
```bash
faers-signal etl --source qfiles --input "path/to/faers_qfiles.zip" --db data/faers.duckdb
```

**方法4: UI から openFDA API 経由で取得**
UI のサイドバー「📥 openFDA データ取得」セクションから、薬剤名・期間を指定してデータをダウンロードできます。

### UI の起動

```bash
faers-signal ui --db data/faers.duckdb
# または直接起動
streamlit run app/streamlit_app.py
```

### UI の使い方

- **フィルタ**（サイドバー）: 被疑薬のみ / 最小A件数 / 薬剤名・PT の前方一致
- **シグナル判定テーブル**: ABCD と各指標を表示。⚠️ マーク行がシグナル検出。「シグナル検出のみ表示」で絞り込み可能
- **可視化（仮設）**: Volcano Plot / バブルチャート / ヒートマップを選択式で表示
- **CSV ダウンロード**: テーブルデータを CSV で出力

### 指標計算・ファイル出力（CLI）

```bash
# Parquet / CSV へエクスポート
faers-signal build --db data/faers.duckdb --out data/metrics.parquet
# 任意の SQL 結果をエクスポート
faers-signal export --db data/faers.duckdb --sql "SELECT * FROM reports LIMIT 10" --out data/export.csv
```

## Windows exe 版

Python 環境がなくても利用できるスタンドアロン exe 版があります。

- `FaersMiniSignal.exe` をダブルクリックするだけで起動します
- サンプルデータ（5,000 件）が同梱されており、すぐに分析を開始できます
- 起動後、ブラウザで Streamlit UI が自動的に開きます

入手方法は Releases ページを確認してください。

## 指標と判定基準

| 指標 | 式 | シグナル基準 |
|------|-----|------------|
| PRR | [A/(A+B)] / [C/(C+D)] | ≥ 2 |
| χ² (1df) | Yates 補正付きカイ二乗 | ≥ 4 |
| ROR | (A×D) / (B×C) | 下限95%CI > 1 |
| IC | log₂(A / E_A) | 下限95%CI > 0 |

**Evans 3 条件**: PRR ≥ 2 かつ χ² ≥ 4 かつ A ≥ 3 を同時に満たす場合にシグナルと判定。

**ゼロセル補正**: A, B, C, D のいずれかが 0 の場合、Haldane–Anscombe 補正として全セルに +0.5 を加算します（Haldane, 1956）。

## プロジェクト構成

```
src/faers_signal/     # メインパッケージ
├── cli.py            # CLI エントリポイント
├── metrics.py        # PRR/ROR/IC/χ² 計算
├── ingest_demo.py    # デモデータ取り込み
├── ingest_openfda.py # openFDA ローカルファイル取り込み
├── ingest_qfiles.py  # 四半期ファイル取り込み
├── download_openfda.py # openFDA API 経由データ取得
├── _resources.py     # SQL/リソース読み込み
├── schema.sql        # DuckDB スキーマ定義
└── abcd.sql          # ABCD 分割表集計クエリ
app/
└── streamlit_app.py  # Streamlit UI
scripts/
└── seed_sample_db.py # サンプルDB生成スクリプト
tests/                # pytest テスト
docs/                 # 仕様書・将来設計ノート
```

## 開発者向け

```bash
# テスト
pytest -q
# Lint
ruff check .
```

## 重要な注意（FAERS データの限界）

- FAERS は自発報告に基づくデータであり、因果関係を示すものではありません
- 曝露人数（分母）が不明で、報告バイアスや重複の可能性があります
- 本ツールの出力は仮説生成の支援を目的としたもので、医療判断の唯一の根拠にはできません

## ライセンス

MIT License
