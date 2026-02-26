# Specification (faers-mini-signal)

## Data Model (DuckDB)

Tables are defined in `src/faers_signal/schema.sql`:

- `reports(safetyreportid VARCHAR PRIMARY KEY, receivedate DATE, primarysource_qualifier INTEGER)`
- `drugs(safetyreportid VARCHAR, drug_name VARCHAR, drug_name_normalized VARCHAR, drug_norm_source VARCHAR, role INTEGER)`
  - `role`: 1 = suspect, 2 = concomitant, 3 = interacting (`patient.drug[].drugcharacterization`)
- `reactions(safetyreportid VARCHAR, meddra_pt VARCHAR)`

Foreign keys reference `reports(safetyreportid)`.

## Ingest Mapping (openFDA `/drug/event`)

### `etl --source openfda` (CLI)

- Implemented as **local file ingestion** handled by `src/faers_signal/ingest_openfda.py`.
- Supported formats for `--input`:
  - `.json`, `.jsonl`, `.ndjson` (optionally `.gz`)
  - `.zip` archives containing the above
  - directories (recursive walk)
- JSON examples:
  - `safetyreportid` -> `reports.safetyreportid`
  - `receivedate` or `receiptdate` -> `reports.receivedate` (normalized to `YYYY-MM-DD`)
  - `primarysource.qualifier` -> `reports.primarysource_qualifier`
  - `patient.drug[].medicinalproduct` -> `drugs.drug_name`
  - `patient.drug[].drugcharacterization` -> `drugs.role`
  - `patient.reaction[].reactionmeddrapt` -> `reactions.meddra_pt`
- For each `safetyreportid`, existing rows are deleted before insert (idempotent upsert behavior).
- `--since` / `--until` and `--limit` filters are applied during ingestion.

### Streamlit UI openFDA API fetch

- The UI uses `src/faers_signal/download_openfda.py` and `fetch_and_ingest()`.
- It builds a `/drug/event` API query and pages through results, ingesting directly into DuckDB.
- Download source is not `etl --source openfda`; this path is separate from local-file ETL.

## Ingest Mapping (FAERS Quarterly Files)

### `etl --source qfiles`

- Minimal support for DEMO/DRUG/REAC tables from a zip, directory, or single files.
- Mapping:
  - DEMO: `PRIMARYID` -> `reports.safetyreportid`, `FDA_DT` -> `reports.receivedate`
  - DRUG: `PRIMARYID`, `DRUGNAME`, `ROLE_COD` -> `drugs.safetyreportid`, `drugs.drug_name`, `drugs.role`
  - REAC: `PRIMARYID`, `PT` -> `reactions.safetyreportid`, `reactions.meddra_pt`
- Field delimiters (`|`, `\t`, `,`) are auto-detected.
- Unknown fields are stored as `NULL` where expected.
- `--since` / `--until` apply to normalized `FDA_DT` (`YYYY-MM-DD`).

## ABCD Aggregation

Defined by report-level SQL in `src/faers_signal/abcd.sql`:

- `A`: suspect drug present AND target PT present
- `B`: suspect drug present AND target PT absent
- `C`: suspect drug absent AND target PT present
- `D`: neither suspect+PT

## Metrics

Defined in `src/faers_signal/metrics.py`.

- PRR = `(A/(A+B)) / (C/(C+D))`
- Chi-square (1 df, Yates): `((|AD-BC| - N/2)^2 * N) / ((A+B)(C+D)(A+C)(B+D))`
- ROR = `(A/B) / (C/D)`
  - 95% CI: `ln(ROR) ± 1.96*SE`, `SE = sqrt(1/A + 1/B + 1/C + 1/D)`
- IC = `log2(A / E[A])`, `E[A] = (A+B)(A+C)/N`
  - 95% CI via delta approximation

Zero-cell handling:
- When any of `A,B,C,D` is zero, **Haldane-Anscombe correction** is applied (`+0.5` to all four cells) before metric computation.
- With this correction, many zero-cell edge cases are finite rather than returning `NaN`.

## CLI Interface

Entrypoint: `faers-signal`

- `etl` — initialize schema and ingest
  - `--source`: `openfda|qfiles|demo`
  - `--db`: DuckDB path (default `data/faers.duckdb`)
  - `--input`: required for `openfda` and `qfiles`
  - `--since`, `--until`: `YYYY-MM-DD`
  - `--limit`: int (0 = no limit)
- `build` — compute metrics and write CSV/Parquet
  - `--db`, `--suspect-only`, `--min-a`, `--signal-mode`, `--out`
- `export` — run arbitrary `SELECT` and export
  - `--db`, `--sql`, `--out`
- `ui` — launch Streamlit app
  - `--db`

## Limitations & Notes

- openFDA API retrieval is possible from the Streamlit UI via `download_openfda.py`.
- openFDA paging constraint must be respected: `limit <= 1000`, `skip <= 25000`, therefore maximum retrievable records are **26,000** in one run.
- For larger windows, use openFDA bulk Downloads or `search_after` pagination.
- FAERS is spontaneous reporting data; findings are hypothesis-generating, not causal.

