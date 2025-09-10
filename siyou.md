はい、**このまま渡して実装スタートしてOK**です。
仕上げに、\*\*codex cli にそのまま貼れる“実装指示書（MVP）”\*\*をまとめました。これを最初のプロンプトに使ってください。

---

# 実装指示書（MVP / コピペ用）

## プロダクト

* リポ名：`faers-mini-signal`
* 目的：FAERSデータをローカルで取り込み、**PRR / ROR / IC** を計算・可視化（Streamlit）。
  公式ダッシュボードに無い **再現性・統計指標・ローカル完結** を提供。

## スタック & 開発規約

* Python 3.11+
* ライブラリ：`duckdb`, `polars`（または`pandas`でも可）, `pyarrow`, `streamlit`, `jinja2`, `typer`（CLI）, `numpy`, `scipy`, `pytest`, `ruff`, `black`, `mypy`
* パッケージング：`pyproject.toml`（PEP 621）、エントリポイントは `faers-signal` コマンド
* コード規約：ruff + black + mypy、`pre-commit`
* CI：GitHub Actions（lint / type / test）

## ディレクトリ構成

```
faers-mini-signal/
  pyproject.toml
  README.md
  LICENSE (MIT)
  Makefile (任意)
  src/faers_signal/
    __init__.py
    cli.py
    ingest_openfda.py
    ingest_qfiles.py
    schema.sql
    abcd.sql
    metrics.py
  app/streamlit_app.py
  tests/
    test_metrics.py
    test_abcd_sql.py
  docs/
    METHOD.md
  data/
    .gitkeep
```

## DuckDB スキーマ

`src/faers_signal/schema.sql` を生成：

```sql
CREATE TABLE IF NOT EXISTS reports (
  safetyreportid VARCHAR PRIMARY KEY,
  receivedate DATE,
  primarysource_qualifier INTEGER
);

CREATE TABLE IF NOT EXISTS drugs (
  safetyreportid VARCHAR,
  drug_name VARCHAR,
  role INTEGER, -- 1: suspect, 2: concomitant, 3: interacting
  FOREIGN KEY (safetyreportid) REFERENCES reports(safetyreportid)
);

CREATE TABLE IF NOT EXISTS reactions (
  safetyreportid VARCHAR,
  meddra_pt VARCHAR,
  FOREIGN KEY (safetyreportid) REFERENCES reports(safetyreportid)
);
```

## 2×2 集計 SQL

`src/faers_signal/abcd.sql` を生成（**レポート単位**集計）：

```sql
-- suspect=1 の薬剤集合
CREATE TEMP TABLE suspect AS
SELECT DISTINCT safetyreportid, lower(drug_name) AS drug
FROM drugs WHERE role = 1;

-- 反応集合（PT）
CREATE TEMP TABLE rxn AS
SELECT DISTINCT safetyreportid, lower(meddra_pt) AS pt FROM reactions;

-- A: 同一レポート内で suspect薬 と 該当PT が共存
CREATE TEMP TABLE a_counts AS
SELECT s.drug, r.pt, COUNT(*) AS A
FROM suspect s
JOIN rxn r USING (safetyreportid)
GROUP BY s.drug, r.pt;

WITH
drug_tot AS (
  SELECT drug, COUNT(DISTINCT safetyreportid) AS Dtot
  FROM suspect GROUP BY 1
),
pt_tot AS (
  SELECT pt, COUNT(DISTINCT safetyreportid) AS Rtot
  FROM rxn GROUP BY 1
),
rep_tot AS (
  SELECT COUNT(DISTINCT safetyreportid) AS N FROM reports
)
SELECT
  a.drug, a.pt,
  a.A                                                    AS A,
  (d.Dtot - a.A)                                         AS B,
  (r.Rtot - a.A)                                         AS C,
  (rep_tot.N - d.Dtot - r.Rtot + a.A)                    AS D,
  d.Dtot                                                 AS drug_reports,
  r.Rtot                                                 AS pt_reports,
  rep_tot.N                                              AS total_reports
FROM a_counts a
JOIN drug_tot d USING (drug)
JOIN pt_tot r USING (pt)
CROSS JOIN rep_tot;
```

## 指標（`src/faers_signal/metrics.py`）

* 関数シグネチャ：

```python
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np

@dataclass
class ABCD:
    A: int; B: int; C: int; D: int; N: int

def prr(abcd: ABCD) -> float: ...
def chi_square_1df(abcd: ABCD) -> float: ...
def ror(abcd: ABCD) -> float: ...
def ror_ci95(abcd: ABCD) -> Tuple[float, float]: ...
def ic_simple(abcd: ABCD) -> float: ...
def ic_simple_ci95(abcd: ABCD) -> Tuple[float, float]: ...
```

* 数式（実装は数値安定に配慮、`max(x, eps)`でゼロ割回避）

  * `PRR = (A/(A+B)) / (C/(C+D))`
  * `χ² (1df) = (|AD - BC| - N/2)^2 * N / ((A+B)*(C+D)*(A+C)*(B+D))`（Haldane-Anscombe等の連続性補正はオプション）
  * `ROR = (A/B) / (C/D)`、`ln(ROR)`の分散 ≈ `1/A + 1/B + 1/C + 1/D` → 95%CI = `exp( lnROR ± 1.96*sqrt(var) )`
  * `IC = log2( A / E[A] )`, `E[A] = (A+B)*(A+C)/N`、CIは正規近似でOK（まずは入門版）

## CLI（`src/faers_signal/cli.py`）

`typer`で実装し、エントリポイントは `faers-signal`：

* `faers-signal etl --source [openfda|qfiles] --since YYYY-MM-DD --until YYYY-MM-DD --limit INT --db path/faers.duckdb`

  * `openfda`： download（zipped JSON or paging）→ 正規化→ `reports/drugs/reactions` へ `COPY`
  * `qfiles`： 最新四半期1セットを想定（簡易パーサでOK）
* `faers-signal build --db path/faers.duckdb --suspect-only [true|false] --min-a 3 --out metrics.parquet`

  * `abcd.sql`を実行 → 各行に PRR/ROR/IC/χ²/CI を付与 → Parquet/CSVに保存
* `faers-signal export --db path/faers.duckdb --csv out.csv`（任意のSELECTを固定エクスポート）
* `faers-signal ui --db path/faers.duckdb` → Streamlitを起動

## Streamlit（`app/streamlit_app.py`）

* 左サイドバー：

  * DBパス、期間フィルタ、`suspect-only`、`min A`、drug/pt 前方一致フィルタ
  * シグナル閾値のUI：既定 **PRR≥2 & χ²≥4 & A≥3**（変更可能）
* 本文：

  * メトリクス表（drug, pt, A,B,C,D, PRR, ROR, ROR\_CI\_L/U, IC, IC\_CI\_L/U, χ²）
  * 行クリックで該当レポートIDの数件サンプル（`reports`/`drugs`/`reactions`結合）を表示
  * CSVエクスポートボタン

## Ingest（概要）

* `ingest_openfda.py`

  * `/drug/event` の **download（zipped JSON）** 優先。無ければ `limit/skip` ページング。
  * 必要フィールド：`safetyreportid`, `receivedate`, `patient.drug[].medicinalproduct`, `patient.drug[].drugcharacterization`, `patient.reaction[].reactionmeddrapt`
  * 正規化：薬剤名/反応名とも `lower()`、空白・記号のトリム（過度な正規化はしない）
* `ingest_qfiles.py`

  * 最新四半期の小規模セットに対応（完全互換は後回し）

## テスト

* `tests/test_metrics.py`

  * 代表ケースでPRR/ROR/IC/CI/χ² が**計算式どおり**になること（相対誤差許容）
  * 0件や極端に小さいセルに対して、例外を出さずに`np.nan`またはロバスト処理
* `tests/test_abcd_sql.py`

  * 小さな合成テーブルをDuckDBに投入し、`abcd.sql`の出力が期待通り（手計算値と一致）

## README.md（最低限の内容）

* 目的と差別化ポイント（再現性・統計指標・ローカル）
* クイックスタート（インストール→ `etl` → `build` → `ui`）
* 指標の式と注意（**自発報告データは因果を示さない**、分母不明、重複・バイアス）
* スクショ（UI表・フィルタ例）
* ライセンス：MIT

## 受け入れ基準（Definition of Done）

1. `uv pip install -e .` 後に `faers-signal --help` が動く
2. サンプル取得（小規模）→ `faers.duckdb` 作成 → `build`でメトリクスParquet/CSVが生成される
3. Streamlit UIが立ち上がり、**フィルタ**と**CSV出力**が機能する
4. `pytest -q` がGREEN（基本メトリクスとSQLの単体テスト）
5. READMEの手順で**第三者が再現**できる

## エッジケース処理

* `A,B,C,D` のいずれかが0の場合：`eps=1e-12`で計算安定化（CIは`nan`許容可）
* `drug_name`/`meddra_pt` が空・None：取り込み時に除外
* レポート重複・フォローアップ：初期は`safetyreportid`単位で扱い、dedup高度化は将来課題
* suspect限定のON/OFFで結果が変わることをUIヘルプに明記

## 将来拡張（ラベルだけ用意）

* EBGM（MGPS）の追加、層別PRR、時系列監視（SPRT）、重複処理の高度化

---

### そのまま使える最初の指示（短縮版）

> 「上記“実装指示書（MVP）”に沿って、空のリポを初期化し、ディレクトリ・ファイルを生成。`faers-signal` CLI の4コマンド（etl/build/export/ui）と、`abcd.sql`・`metrics.py`（PRR/ROR/IC/χ²とCI）を実装。`streamlit_app.py`で表・フィルタ・CSV出力の最小UIを作成。pytestとCI、READMEも整備。依存は`pyproject.toml`にまとめ、ruff/black/mypy/pre-commitを設定。Done定義の5項目を満たすこと。」

---