# 結論（Go / No-Go と差別化の芯）

* **Go**：公式FAERS Public Dashboardは**件数ベースの記述統計**に特化し、結果の**再現可能なパイプライン**や**PRR/ROR/IC/EBGM 等の不均衡指標**は出しません。検索結果の**Excelエクスポートは限定的**で、柔軟な横断比較や再現性の担保は難しいです。ここに**ローカル完結・再現性・統計指標**を備えた軽量プロダクトを出す意義が十分あります。([U.S. Food and Drug Administration][1], [fis.fda.gov][2])
* **データ供給の現状**：FAERSはAPI（openFDA）と四半期ファイルの両方で公開。さらに**日次近傍の更新**が始まっており（zip一括DLもあり）、小規模ETL→DuckDBの設計が噛み合います。([open.fda.gov][3], [fis.fda.gov][4], [U.S. Food and Drug Administration][5])
* **指標の閾値の慣行**：PRR≥2 & χ²≥4 & 件数≥3 といった“よく使われる”基準は古典文献に根拠あり（実装の既定値に採用、UIで変更可能に）。([PubMed][6], [Frontiers][7])

---

# 仕様（MVP）

## プロダクト名

`faers-mini-signal`（DuckDB + Streamlit）

## 目的

* **ローカルで**FAERSデータを取り込み、**PRR/ROR/IC**（将来：EBGM）を**再現可能なコード**で計算・可視化。
* 面接で「**データの性質・限界を理解しつつ統計的に扱える**」ことを示す。

## スコープ（MVP）

* **データ取り込み（どちらか選択可）**

  1. **openFDA** Drug Adverse Event `/drug/event`：期間・件数を絞りページング取得（もしくは公式の**zipped JSON一括DL**）。([open.fda.gov][3])
  2. **FAERS 四半期生データ**（ASCII/XML）：最新四半期のみ取り込み（サイズ小さめ構成でサンプル同梱）。([fis.fda.gov][4], [U.S. Food and Drug Administration][8])
* **正規化スキーマ（DuckDB）**

  ```
  reports(safetyreportid, receivedate, primarysource_qualifier, ... )
  drugs(safetyreportid, drug_name, role)  -- role: suspect=1 他は含める/除外をUI切替
  reactions(safetyreportid, meddra_pt)
  ```
* **2×2集計（レポート単位）**

  * A: 同一レポート内で {suspect薬=対象薬} ∧ {反応集合にPTあり}
  * B: 対象薬あり ∧ PTなし
  * C: 対象薬なし ∧ PTあり
  * D: それ以外
    （suspect=1デフォ、UIで切替）
* **指標**

  * PRR と χ²、ROR（95%CI）、IC（簡易BCPNN近似; まずはO/Eのlog2）。
    既定の**シグナルハイライト**：PRR≥2 & χ²≥4 & A≥3（UIで可変）。([PubMed][6], [Frontiers][7])
* **UI（Streamlit）**

  * フィルタ：期間、最小A、最小レポート数、suspect限定ON/OFF、薬剤/反応の前方一致。
  * テーブル：drug, PT, A,B,C,D, PRR(±CI), ROR(±CI), IC(±CI)、**条件を満たす行を強調**。
  * 行クリックで**該当レポートサンプル**（IDと要約）を数件プレビュー。
  * **CSVエクスポート**（全列）。
* **ドキュメント**

  * README：FAERSの限界（因果ではない、報告バイアス、重複可能性、分母不明）を明示。([fis.fda.gov][9])
  * METHOD.md：2×2表の定義、数式、推定・近似、既知の落とし穴。

## 非スコープ（MVPではやらない）

* 重複症例の高度 dedup（初期は`safetyreportid`で扱い、発展でフォローアップ統合に挑戦）
* 高度な層別（年齢×性別×報告者…の同時分割）
* 時系列のシグナル監視（SPRT等）

---

# 実装方針

## リポ構成

```
faers-mini-signal/
  pyproject.toml        # ruff, black, mypy, pytest, streamlit, duckdb, polars
  src/faers_signal/
    ingest_openfda.py   # API/zip取得→JSON正規化→DuckDB
    ingest_qfiles.py    # 四半期ASCII/XML→DuckDB（最小対応）
    schema.sql          # テーブル作成
    abcd.sql            # 2×2カウント用SQL（A/B/C/D）
    metrics.py          # PRR/ROR/IC/CI/chi-square 実装
    cli.py              # etl / build / export のCLI
  app/streamlit_app.py  # UI
  tests/                # 指標の単体テスト（合成データ）
  docs/{README.md,METHOD.md}
  data/README.md        # 取得手順と注意
```

## データ取得（2経路）

* **openFDA**

  * 小規模デモ：`limit`＆`skip`でページング取得、または\*\*/download のzip JSON\*\*を落としてオフライン展開→DuckDBに`COPY`/`read_json_auto`。([open.fda.gov][3])
* **四半期ファイル**

  * FDAの**Quarterly Data Extract**（最新四半期ひとつ）を対象。将来、複数四半期のマージはオプション。([fis.fda.gov][4])

## 2×2表（DuckDB SQL骨子）

```sql
-- suspect薬集合
CREATE TEMP TABLE suspect AS
SELECT DISTINCT safetyreportid, lower(drug_name) AS drug
FROM drugs WHERE role = 1;

-- 反応集合
CREATE TEMP TABLE rxn AS
SELECT DISTINCT safetyreportid, lower(meddra_pt) AS pt FROM reactions;

-- A
CREATE TEMP TABLE a_counts AS
SELECT s.drug, r.pt, COUNT(*) AS A
FROM suspect s JOIN rxn r USING (safetyreportid)
GROUP BY s.drug, r.pt;

WITH
drug_tot AS (SELECT drug, COUNT(DISTINCT safetyreportid) AS Dtot FROM suspect GROUP BY 1),
pt_tot   AS (SELECT pt,   COUNT(DISTINCT safetyreportid) AS Rtot FROM rxn     GROUP BY 1),
rep_tot  AS (SELECT COUNT(DISTINCT safetyreportid) AS N FROM reports)
SELECT
  a.drug, a.pt, a.A,
  (d.Dtot - a.A)                       AS B,
  (r.Rtot - a.A)                       AS C,
  (rep_tot.N - d.Dtot - r.Rtot + a.A)  AS D
FROM a_counts a
JOIN drug_tot d USING (drug)
JOIN pt_tot   r USING (pt)
CROSS JOIN rep_tot;
```

## 指標（`metrics.py`のコア）

* **PRR** = (A/(A+B)) / (C/(C+D))
  **χ²**（1自由度）で補助。既定の表示閾値：**PRR≥2 & χ²≥4 & A≥3**（UIで変更可）。([PubMed][6], [Frontiers][7])
* **ROR** = (A/B) / (C/D)、\*\*ln(ROR)\*\*の分散 ≈ 1/A+1/B+1/C+1/D → 95%CI をexpで復元。([サイエンスダイレクト][10])
* **IC（簡易）**：IC = log2( A / E\[A] )、E\[A] = (A+B)\*(A+C)/N。まずは正規近似でIC95%CIを出す“入門版”。（将来：BCPNNの厳密計算に拡張）
* **（Stretch）EBGM**：MGPSの**EBGM/EB05/EB95**。まずは文献式に基づく簡易版→将来`openEBGM`相当へ。([cioms.ch][11])

## UI（`streamlit_app.py`）

* 左ペイン：**データ源選択**（openFDA / Quarterly）、期間、suspect限定、最小件数A/N、薬剤/反応フィルタ。
* メイン：**ランキング表**（並べ替え・検索）＋**条件に合致したレポート例**のプレビュー、**CSV出力**。
* ヘルプ：**「FAERSデータの限界」**と**用語集**（MedDRA, suspect, PRR/ROR/IC の解説）。([fis.fda.gov][9])

## 品質・再現性

* **テスト**：合成2×2でPRR/ROR/ICが既知値になるケースを`pytest`で網羅。
* **CI**：GitHub Actions（lint/format/type/test）
* **再現**：`make demo`（または `uv run`/`poetry run`）で**データ取得→DuckDB構築→UI起動**まで一発。

## ライセンス・倫理

* **MIT**。READMEに**免責**と**利用上の注意**（“シグナル=因果ではない”）を明記。([fis.fda.gov][9])

---

# README.md（ドラフト）

````markdown
# faers-mini-signal

FAERS（FDA Adverse Event Reporting System）のデータをローカルで取り込み、  
**PRR / ROR / IC**（将来：EBGM）を計算・可視化する軽量ツール。

> 公式の **FAERS Public Dashboard** は記述統計に特化（件数・割合）で、  
> 分析手順の再現・不均衡指標（PRR/ROR/IC/EBGM）の提供はありません。  
> 本ツールは **ローカル完結・再現可能・拡張可能** な分析を目的とします。  
> 参考: FDA 公開情報（ダッシュボード/FAQ、openFDA、四半期データ）  
> [[Dashboard]](https://www.fda.gov/drugs/fdas-adverse-event-reporting-system-faers/fda-adverse-event-reporting-system-faers-public-dashboard)  
> [[FAQ/Export]](https://fis.fda.gov/extensions/FPD-FAQ/FPD-FAQ.html)  
> [[openFDA API]](https://open.fda.gov/apis/drug/event/) [[zipped JSON]](https://open.fda.gov/apis/drug/event/download/)  
> [[Quarterly Files]](https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html)

## 🧭 できること（MVP）
- FAERSを **openFDA** または **四半期ファイル** から取り込み、DuckDB に正規化。
- レポート単位で 2×2 集計（A,B,C,D）→ **PRR / ROR(95%CI) / IC(95%CI)** を算出。
- 既定のシグナル基準（**PRR≥2 & χ²≥4 & A≥3**）でハイライト（変更可能）。
- Streamlit で検索/フィルタ、ランキング閲覧、CSVエクスポート。

## ⚠️ 重要な注意（FAERSの限界）
- FAERS は **自発報告** データです。**因果関係は証明されません**。  
- **分母（曝露）が不明**、**報告バイアス・重複** の可能性があります。  
- 本ツールの出力は **仮説生成** の補助に過ぎません。  
（FDAの注意喚起・ダッシュボード説明を参照）  

## 📦 クイックスタート
```bash
# 1) 環境
uv venv && uv pip install -e .

# 2) デモデータの取得（openFDA zipped JSON 小規模）
faers-signal etl --source openfda --since 2024-01-01 --limit 50000

# 3) 指標計算（DuckDB内でA/B/C/D→指標テーブル生成）
faers-signal build

# 4) UI
streamlit run app/streamlit_app.py
````

## 📐 指標（概要）

* **PRR** = (A/(A+B)) / (C/(C+D))、補助統計に **χ²**（1df）。
* **ROR** = (A/B)/(C/D)、**ln(ROR)** 分散 ≈ 1/A+1/B+1/C+1/D → 95%CI。
* **IC**  = log2( A / E\[A] ),  E\[A]=(A+B)\*(A+C)/N。
  （詳細・参考文献は `docs/METHOD.md` を参照）

## 🗂 データスキーマ（DuckDB）

* `reports(safetyreportid, receivedate, ...)`
* `drugs(safetyreportid, drug_name, role)`  # role: suspect=1
* `reactions(safetyreportid, meddra_pt)`

## 🧪 テスト

```bash
pytest -q
```

## 📄 ライセンス

MIT



[1]: https://www.fda.gov/drugs/fdas-adverse-event-reporting-system-faers/fda-adverse-event-reporting-system-faers-public-dashboard?utm_source=chatgpt.com "FDA Adverse Event Reporting System (FAERS)"
[2]: https://fis.fda.gov/extensions/FPD-FAQ/FPD-FAQ.html?utm_source=chatgpt.com "FAERS Public Dashboard - FAQ"
[3]: https://open.fda.gov/apis/drug/event/?utm_source=chatgpt.com "Drug Adverse Event Overview"
[4]: https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html?utm_source=chatgpt.com "FAERS Quarterly Data Extract Files"
[5]: https://www.fda.gov/news-events/press-announcements/fda-begins-real-time-reporting-adverse-event-data?utm_source=chatgpt.com "FDA Begins Real-Time Reporting of Adverse Event Data"
[6]: https://pubmed.ncbi.nlm.nih.gov/11828828/?utm_source=chatgpt.com "Use of proportional reporting ratios (PRRs) for signal ..."
[7]: https://www.frontiersin.org/journals/drug-safety-and-regulation/articles/10.3389/fdsfr.2023.1323057/full?utm_source=chatgpt.com "Conducting and interpreting disproportionality analyses ..."
[8]: https://www.fda.gov/drugs/fdas-adverse-event-reporting-system-faers/fda-adverse-event-reporting-system-faers-latest-quarterly-data-files?utm_source=chatgpt.com "FAERS: Latest Quarterly Data Files"
[9]: https://fis.fda.gov/extensions/fpdwidgets/2e01da82-13fe-40e0-8c38-4da505737e36.html?utm_source=chatgpt.com "FAERS Public Dashboard - About"
[10]: https://www.sciencedirect.com/science/article/am/pii/S004059571930023X?utm_source=chatgpt.com "Case–non-case studies: Principle, methods, bias and ..."
[11]: https://cioms.ch/wp-content/uploads/2018/03/WG8-Signal-Detection.pdf?utm_source=chatgpt.com "Practical Aspects of Signal Detection in Pharmacovigilance"
