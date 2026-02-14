# Specification (faers-mini-signal)

This document summarizes the data model, ingest mapping, ABCD aggregation, metrics, and CLI options.

## Data Model (DuckDB)

Tables (see `src/faers_signal/schema.sql`):

- `reports(safetyreportid VARCHAR PRIMARY KEY, receivedate DATE, primarysource_qualifier INTEGER)`
- `drugs(safetyreportid VARCHAR, drug_name VARCHAR, role INTEGER)`
  - `role`: 1=suspect, 2=concomitant, 3=interacting (openFDA drugcharacterization)
- `reactions(safetyreportid VARCHAR, meddra_pt VARCHAR)`

Constraints: Foreign keys reference `reports(safetyreportid)`.

## Ingest Mapping (openFDA `/drug/event`)

- `reports.safetyreportid` ← `safetyreportid`
- `reports.receivedate` ← `receivedate` (or `receiptdate`), normalized to `YYYY-MM-DD`
- `reports.primarysource_qualifier` ← `primarysource.qualifier` (int if present)
- `drugs.drug_name` ← `patient.drug[].medicinalproduct`
- `drugs.role` ← `patient.drug[].drugcharacterization`
- `reactions.meddra_pt` ← `patient.reaction[].reactionmeddrapt`

Idempotency: for each `safetyreportid`, existing rows are deleted and replaced.

Supported inputs for `etl --source openfda --input`:
- `.json`, `.jsonl`, `.ndjson` (optionally `.gz`)
- `.zip` archives containing the above
- Directories (recursive)

Filters:
- `--since` / `--until` (inclusive) apply to `receivedate`
- `--limit` caps total number of ingested reports

## Ingest Mapping (FAERS Quarterly Files)

Minimal support accepts DEMO/DRUG/REAC tables from a zip, directory, or single files.

- DEMO: `PRIMARYID` -> `reports.safetyreportid`; `FDA_DT` (YYYYMMDD) -> `reports.receivedate`
- DRUG: `PRIMARYID`, `DRUGNAME` -> `drugs.drug_name`; `ROLE_COD` -> `drugs.role`
  - role map: `PS|SS` -> 1 (suspect), `C` -> 2 (concomitant), `I` -> 3 (interacting)
- REAC: `PRIMARYID`, `PT` -> `reactions.meddra_pt`

Notes:
- Delimiters `|`, tab, or comma are auto-detected.
- Unknown fields (e.g., reporter qualifiers) are set to NULL in `reports.primarysource_qualifier`.
- Filters: `--since/--until` apply to `FDA_DT` after normalization to `YYYY-MM-DD`.

## ABCD Aggregation

Implemented in `src/faers_signal/abcd.sql` with report-level counts:

- A: suspect drug present AND PT present in the same report
- B: suspect drug present AND PT absent
- C: suspect drug absent AND PT present
- D: neither

Defaults use `role = 1` (suspect). CLI/UI can include `role in (1,2,3)` by toggling suspect-only off.

Outputs include per-pair totals: `drug_reports`, `pt_reports`, `total_reports`.

## Metrics

Defined in `src/faers_signal/metrics.py`. Given `ABCD(A,B,C,D,N)`:

- PRR = (A/(A+B)) / (C/(C+D))
- χ² (1df, Yates) = ((|AD-BC| - N/2)^2 * N) / ((A+B)(C+D)(A+C)(B+D))
- ROR = (A/B) / (C/D)
  - 95% CI: ln(ROR) variance ≈ 1/A + 1/B + 1/C + 1/D → exp( lnROR ± 1.96·SE )
- IC (simple) = log2( A / E[A] ), E[A] = (A+B)(A+C)/N
  - 95% CI: normal approximation via delta method

Numerical stability: zero or invalid cases return `NaN`.

## CLI Interface

Entrypoint: `faers-signal`

- `etl` — initialize schema and ingest data
  - `--source`: `demo|openfda|qfiles`
  - `--db`: DuckDB file path (default `data/faers.duckdb`)
  - `--input`: required for `openfda` (file/dir)
  - `--since`, `--until`: `YYYY-MM-DD`
  - `--limit`: int (0 = no limit)

- `build` — compute metrics and write Parquet/CSV
  - `--db`: DuckDB path
  - `--suspect-only`: bool (default true)
  - `--min-a`: int (default 3)
  - `--out`: output path (`.parquet` or `.csv`)

- `export` — run arbitrary SELECT and export to file
  - `--db`, `--sql`, `--out`

- `ui` — launch Streamlit app (uses `FAERS_DB` env internally)
  - `--db`: DuckDB path

## Packaging & Resources

- `.sql` files and `app/streamlit_app.py` are bundled; loaded via `importlib.resources`.
- Source layout under `src/faers_signal/` with tests in `tests/`.

## Limitations & Notes

- Network download of openFDA data is not implemented; use local files.
- FAERS is a spontaneous reporting system; signals are for hypothesis generation, not causality.
- Consider de-duplication and stratification in future iterations.
