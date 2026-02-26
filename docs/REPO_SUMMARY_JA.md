# faers-mini-signal Summary

更新日: 2026-02-26

---

## TL;DR
`faers-mini-signal` は、FAERS データを取り込んで ABCD 集計・指標計算・表示まで実行できる実装です。  
`etl --source openfda`（ローカル JSON/ZIP）と `etl --source qfiles` はどちらも実装済みです。  
Streamlit UI からは openFDA API を直接取得して取り込むこともできます。

## Current Working Structure

- `src/faers_signal/`
  - `cli.py`  
    Entrypoints: `etl`, `build`, `export`, `ui`, `version`
  - `schema.sql`  
    `reports`, `drugs`, `reactions`（`drug_name_normalized`, `drug_norm_source` を含む）
  - `ingest_openfda.py`  
    openFDA のローカルファイル取り込み
  - `ingest_qfiles.py`  
    FAERS 四半期ファイル取り込み（DEMO/DRUG/REAC）
  - `download_openfda.py`  
    Streamlit UI からの openFDA API 直接取得
  - `normalize_drug.py`  
    薬剤名の正規化
  - `metrics.py`  
    PRR, ROR, IC, χ²(1df) と関連補助統計
  - `abcd.sql`  
    A/B/C/D 集計 SQL
  - `analysis_spec.py`  
    manifest 作成
  - `ingest_demo.py`  
    デモデータ生成
- `app/streamlit_app.py`  
  フィルタ、可視化、指標表示、openFDA API 取得
- `scripts/seed_sample_db.py`  
  サンプル DB 作成支援
- `tests/`  
  ingest / metric の既存テスト
- `README.md`, `docs/SPEC.md`, `docs/METHOD.md`  
  利用者向けの実行方法と仕様
- `AGENTS.md`, `siyou.md`, `READ.md`  
  プロジェクト運用情報

## Known Notes

- openFDA API 取得は Streamlit UI から可能。
- openFDA のページング制約: `limit <= 1000`, `skip <= 25000` のため、1回の実行で最大 26,000 件まで取得可能。
- より大規模な取得が必要な場合は、openFDA の Download / `search_after` 利用が必要。
- ETL が未実装である、という記載は削除しました（実装済み）。
- FAERS は自発報告データのため、因果推論ではなく信号探索用途で扱うべきです。

