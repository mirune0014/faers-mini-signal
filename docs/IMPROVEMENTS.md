# 改善計画と課題整理（faers-mini-signal）

本ドキュメントは、現状の課題と、それに対する改善方針・実装案をまとめたものです。

## 概要
- 課題1: drug / pt 入力 UI の検索性（サジェスト、複数選択、部分一致）
- 課題2: データ容量と保管戦略（複数年の大容量データをどう扱うか）

---

## 課題1: drug / pt 入力 UI の検索性向上

### 現状
- サイドバーで前方一致のテキスト入力によるフィルタを提供。
- 候補の絞り込みや複数選択は不可。大規模データでは目的の値に辿り着きづらい。

### 期待する振る舞い
- 文字を2文字以上入力した時点で、上位N件の候補がサジェストされる（Typeahead）。
- 複数の drug / pt を選択してフィルタできる。
- 前方一致だけでなく、部分一致（contains）や正規表現/ワイルドカードに切替可能。

### 改善案（実装方針）
- サジェスト（Typeahead）
  - 入力値 `q`（2文字以上）で DuckDB に対してオンデマンドに候補を問い合わせる。
  - 例: `SELECT lower(name) AS name, COUNT(*) AS n FROM <dict> WHERE name LIKE '%q%' GROUP BY 1 ORDER BY n DESC LIMIT 50;`
- 候補の供給元
  - 辞書テーブルを導入（正規化済み）:
    - `drug_dict(drug TEXT PRIMARY KEY, n INT)` = `drugs` から `LOWER(drug_name)` の distinct と件数を事前計算
    - `pt_dict(pt TEXT PRIMARY KEY, n INT)` = `reactions` から `LOWER(meddra_pt)` の distinct と件数を事前計算
  - もしくはオンザフライで `drugs` / `reactions` を直接集計（パフォーマンス要確認）。
- 複数選択（Multi-select）
  - `st.multiselect` で候補リストから複数選択 → 選択結果を `st.session_state` に保持。
  - 適用ボタンで ABCD 集計結果に対して `drug IN (...)` / `pt IN (...)` で絞り込み。
- 一致方法トグル
  - UI で `Startswith / Contains / Regex` を切替（最初は `Startswith / Contains`）。
  - DuckDB では `LIKE` / `ILIKE` を利用（正規表現は `REGEXP_MATCHES` の活用を検討）。

### スケッチ（UI 側の擬似コード）
```python
q_drug = st.text_input("Drug 検索", value="")
if len(q_drug) >= 2:
    df = con.execute(
        """
        SELECT drug, n FROM drug_dict
        WHERE drug LIKE ?
        ORDER BY n DESC
        LIMIT 50
        """,
        [f"%{q_drug.lower()}%"],
    ).fetch_df()
    chosen = st.multiselect("候補", options=df["drug"].tolist(), default=[])
    # chosen（複数）を最終フィルタに適用
```

### タスク（UI/ETL）
- UI: `st.text_input` + サジェスト結果 + `st.multiselect` + フィルタ適用
- ETL/Build: `drug_dict` / `pt_dict` 生成（初回/更新時に再計算）
- 受け入れ条件
  - 2文字以上入力で100ms〜数百ms程度で候補が返る（50件程度）。
  - 複数選択が反映され、ABCD/指標表が所期の行数に減る。
  - Contains/Startswith の切替で結果が直感に合う。

---

## 課題2: データ容量と保管戦略

### 背景
- 2025年の一部だけでもそこそこのサイズ。複数年分を扱うとローカルPCの容量が不足しやすい。

### 要件
- 大容量データを現実的なコスト・スピードで保存/参照できること。
- 再現可能性（手順/スクリプトで環境再構築可能）。
- UI/分析は軽快に動作（必要データだけを読み込む）。

### アーキテクチャ案
- A) Parquet 分割（ローカル or 外付け）
  - 原始データ/正規化済みテーブルを Parquet に年・四半期などでパーティション化して保存。
  - DuckDB から `read_parquet('data/raw/year=2024/*.parquet')` のように遅延読み込み。
  - メリット: 単純・安価・ローカルで完結。必要部分のみ読み込み可。
- B) オブジェクトストレージ（S3/Azure/GCS）+ DuckDB `httpfs`
  - データは S3 等へ。DuckDB の `httpfs` を `INSTALL/LOAD` して直接参照。
  - 例（Python）:
    ```python
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET s3_region='ap-northeast-1';")
    con.execute("SET s3_access_key_id='...'; SET s3_secret_access_key='...';")
    df = con.execute("SELECT COUNT(*) FROM read_parquet('s3://bucket/faers/year=2024/*.parquet')").fetchdf()
    ```
  - メリット: 容量制限の解消、複数端末/チームで共有可能。
- C) メトリクスのみ保存（Rawを保持しない/別保管）
  - `build` で ABCD + 指標を年/四半期ごとに計算 → Parquet に保存。
  - UI はメトリクス Parquet をマージして表示（Raw は都度取得/別媒体に退避）。
  - メリット: 容量を大幅削減。多くの用途で十分。
- D) 外付けSSD/NAS をデータ置き場に
  - DuckDB/Parquet の保存先を外付けドライブ/社内NASに変更。

### 推奨段階的プラン
1) 小規模/試行: ローカル DuckDB 単一ファイル + メトリクス出力（現状）
2) 中規模: Parquet へパーティション保存（年/四半期）+ UI はメトリクスのみ参照
3) 大規模/共有: S3 等に Parquet を配置し、DuckDB httpfs で直接参照

### 運用メモ
- Parquet 化の際は、`lower(drug_name)`/`lower(meddra_pt)` をカラムとして持たせると検索が速い。
- 年/四半期単位で `drug_dict` / `pt_dict` を別途出力しておくと、サジェスト生成が高速化。
- 圧縮は `zstd` 推奨（サイズ/速度のバランス）。

---

## 付録: コードスケッチ

### DuckDB で S3 を使う（Python）
```python
import duckdb
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")
con.execute("SET s3_region='ap-northeast-1';")
con.execute("SET s3_access_key_id='YOUR_KEY';")
con.execute("SET s3_secret_access_key='YOUR_SECRET';")
con.execute("SELECT COUNT(*) FROM read_parquet('s3://your-bucket/faers/year=2024/*.parquet')").fetchall()
```

### Streamlit サジェスト（簡易案）
```python
q = st.text_input("Drug 検索 (2文字以上)", value="")
if len(q) >= 2:
    df = con.execute(
        "SELECT drug, n FROM drug_dict WHERE drug LIKE ? ORDER BY n DESC LIMIT 50",
        [f"%{q.lower()}%"],
    ).fetch_df()
    chosen = st.multiselect("候補", options=df["drug"].tolist(), default=[])
    if chosen:
        mdf = mdf[mdf["drug"].isin(chosen)]
```

---

## ToDo（実装単位）
- [ ] `drug_dict` / `pt_dict` を `etl` / `build` フローに追加（初回・更新）
- [ ] UI のサジェスト + 複数選択の導入（2文字以上で候補50件）
- [ ] Contains/Startswith の切替（まずは Contains を既定）
- [ ] メトリクスのみ保存モード（Raw を保持しない運用のガイド）
- [ ] Parquet パーティション設計（年/四半期）と運用ドキュメント化
- [ ] S3 等リモートストレージ利用手順（認証とベストプラクティス）
