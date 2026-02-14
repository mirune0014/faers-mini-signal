# FAERS Mini Signal — 将来設計ノート

## 3. 時系列トレンド分析（優先度: 高）

### 概要
`receivedate` を使って薬剤-PT ペアのシグナル強度の時間推移を分析する。

### 設計課題（要検討）
- 集計期間: 四半期 / 半年 / 年？ユーザー選択式？
- 指標: PRR の推移？ IC の推移？両方？
- 表示: 折れ線グラフ（特定の薬剤-PTペアを選択して表示）
- 新興シグナル検出: 直近期間にシグナル基準を初めて超えたペアをハイライト
- データ量の制約: 期間別に ABCD を再計算するためクエリが重い可能性

---

## 4. 重篤度フィルタ＋比較分析（優先度: 高）

### 概要
openFDA の `serious`, `seriousnessdeath`, `seriousnesshospitalization` 等を取り込み、
重篤 vs 非重篤の比較分析を可能にする。

### スキーマ拡張案
```sql
ALTER TABLE reports ADD COLUMN serious INTEGER;          -- 1=重篤, 2=非重篤
ALTER TABLE reports ADD COLUMN seriousness_death INTEGER; -- 1=死亡
ALTER TABLE reports ADD COLUMN seriousness_hosp INTEGER;  -- 1=入院
```

### 実装ステップ
1. `ingest_openfda.py` の `_normalize_and_insert` を拡張（新カラム取り込み）
2. `schema.sql` にカラム追加
3. UI にフィルタ追加（重篤のみ / 非重篤のみ / 全て）
4. 比較分析: 同じ薬剤-PTペアの重篤時PRR vs 非重篤時PRRを並べて表示

---

## 5. 患者背景の取り込み（別ページ）

### 概要
年齢・性別・体重を取り込み、層別化分析を可能にする。
現在の薬剤-副作用のみの分析ページは維持。

### スキーマ拡張案
```sql
ALTER TABLE reports ADD COLUMN patient_age REAL;     -- 年齢（年単位に正規化）
ALTER TABLE reports ADD COLUMN patient_sex INTEGER;   -- 0=不明, 1=男, 2=女
ALTER TABLE reports ADD COLUMN patient_weight REAL;   -- 体重(kg)
```

### UI設計
- `pages/demographics.py` を新規作成（Streamlit マルチページ）
- 年齢層別（0-17 / 18-64 / 65+）のシグナル比較
- 性別のシグナル比較

---

## 6. SOC 階層対応（選択式グルーピング）

### 概要
MedDRA の PT → SOC マッピングを追加し、SOC レベルでのグルーピング分析を可能にする。

### 実装案
- `meddra_soc.csv` (PT → SOC マッピング) をリソースとして同梱
- UI にトグル: 「SOCでグルーピング」ON/OFF
- ON の場合、PT の代わりに SOC でABCD集計
- MedDRA ライセンスの制約に注意（フリー版の範囲で実装）
