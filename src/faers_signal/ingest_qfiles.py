from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd
import typer


def _parse_date_yyyymmdd(s: str | None) -> Optional[str]:
    if not s:
        return None
    s = str(s)
    s = s.strip().replace("/", "").replace("-", "")
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    # try first 10 chars like YYYY-MM-DD
    t = s[:10]
    if len(t) == 10 and t[4] == "-" and t[7] == "-":
        return t
    return None


def _read_table_from_bytes(name: str, data: bytes) -> pd.DataFrame:
    """Read a small FAERS quarterly table from bytes.

    Supports common delimiters: '|', tab, or comma. Assumes UTF-8.
    Returns a DataFrame with uppercased column names for consistent access.
    """
    text = data.decode("utf-8")
    # detect delimiter
    if "|" in text.splitlines()[0]:
        sep = "|"
    elif "\t" in text.splitlines()[0]:
        sep = "\t"
    else:
        sep = ","
    df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str)
    df.columns = [c.upper() for c in df.columns]
    return df


def _iter_qfiles(input_path: Path):
    """Yield (logical_name, DataFrame) for DEMO/DRUG/REAC tables.

    - If `input_path` is a zip, extracts matching members.
    - If a directory, recursively loads matching files.
    - If a single file, tries to classify by filename.
    """
    patterns = {
        "DEMO": ("DEMO", "DEMO"),
        "DRUG": ("DRUG", "DRUG"),
        "REAC": ("REAC", "REAC"),
    }

    def classify(p: str) -> str | None:
        up = p.upper()
        for key in patterns:
            if key in up:
                return key
        return None

    if input_path.is_dir():
        for p in input_path.rglob("*"):
            if not p.is_file():
                continue
            kind = classify(p.name)
            if not kind:
                continue
            yield kind, _read_table_from_bytes(p.name, p.read_bytes())
        return

    if input_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(input_path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                kind = classify(info.filename)
                if not kind:
                    continue
                with zf.open(info, "r") as f:
                    data = f.read()
                yield kind, _read_table_from_bytes(info.filename, data)
        return

    # single file
    kind = classify(input_path.name)
    if kind:
        yield kind, _read_table_from_bytes(input_path.name, input_path.read_bytes())


def _role_to_int(role_cod: str | None) -> Optional[int]:
    if not role_cod:
        return None
    r = role_cod.strip().upper()
    # Map FAERS role codes to integers: PS/SS -> 1 (suspect), C -> 2, I -> 3
    if r in ("PS", "SS"):
        return 1
    if r == "C":
        return 2
    if r == "I":
        return 3
    return None


def ingest_qfiles(
    con: duckdb.DuckDBPyConnection,
    *,
    input: Path | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 0,
) -> None:
    """Ingest minimal FAERS quarterly files into DuckDB.

    Supported inputs:
      - Zip archive or directory containing DEMO/DRUG/REAC files (any delimiter among '|', tab, comma).
      - Single DEMO/DRUG/REAC file.

    Minimal column expectations (case-insensitive):
      - DEMO: PRIMARYID, FDA_DT (YYYYMMDD)
      - DRUG: PRIMARYID, DRUGNAME, ROLE_COD (PS/SS/C/I)
      - REAC: PRIMARYID, PT

    Mapping to schema:
      - reports.safetyreportid = PRIMARYID (as string)
      - reports.receivedate   = parse(FDA_DT)
      - drugs.drug_name       = DRUGNAME
      - drugs.role            = map ROLE_COD -> {PS/SS:1, C:2, I:3}
      - reactions.meddra_pt   = PT
    """
    if input is None:
        typer.echo("--input is required for qfiles ingest (path to dir/zip/file)", err=True)
        raise typer.Exit(code=2)
    input = Path(input)
    if not input.exists():
        typer.echo(f"Input not found: {input}", err=True)
        raise typer.Exit(code=2)

    demo_df = pd.DataFrame()
    drug_df = pd.DataFrame()
    reac_df = pd.DataFrame()
    for kind, df in _iter_qfiles(input):
        if kind == "DEMO":
            demo_df = pd.concat([demo_df, df], ignore_index=True)
        elif kind == "DRUG":
            drug_df = pd.concat([drug_df, df], ignore_index=True)
        elif kind == "REAC":
            reac_df = pd.concat([reac_df, df], ignore_index=True)

    if demo_df.empty or drug_df.empty or reac_df.empty:
        typer.echo("Expected DEMO/DRUG/REAC files were not all found.", err=True)
        raise typer.Exit(code=2)

    # Normalize column names (robust to small naming variants)
    def col(df: pd.DataFrame, *cands: str) -> str:
        up = set(df.columns)
        for c in cands:
            cu = c.upper()
            if cu in up:
                return cu
        raise KeyError(f"Missing columns among: {cands}")

    DEMO_ID = col(demo_df, "PRIMARYID", "PRIMARY_ID", "SAFETYREPORTID")
    DEMO_DT = col(demo_df, "FDA_DT", "RECEIPTDATE", "RECEIVEDATE")
    DRUG_ID = col(drug_df, "PRIMARYID", "PRIMARY_ID", "SAFETYREPORTID")
    DRUG_NM = col(drug_df, "DRUGNAME", "MEDICINALPRODUCT", "DRUG_NAME")
    DRUG_RO = col(drug_df, "ROLE_COD", "DRUGCHARACTERIZATION", "ROLE")
    REAC_ID = col(reac_df, "PRIMARYID", "PRIMARY_ID", "SAFETYREPORTID")
    REAC_PT = col(reac_df, "PT", "REACTIONMEDDRAPT", "MEDDRA_PT")

    # Build reports dict with date filters
    reports = {}
    for _, row in demo_df.iterrows():
        sid = str(row[DEMO_ID]).strip()
        if not sid:
            continue
        rcv = _parse_date_yyyymmdd(str(row.get(DEMO_DT, "") or ""))
        if since and rcv and rcv < since:
            continue
        if until and rcv and rcv > until:
            continue
        reports[sid] = (sid, rcv, None)  # primarysource_qualifier unknown in quarterly -> None

    # Early exit if nothing passes the filter
    if not reports:
        typer.echo("No reports matched filters.")
        return

    # Prepare drug and reaction rows limited to selected reports
    drugs_rows = []
    for _, row in drug_df.iterrows():
        sid = str(row[DRUG_ID]).strip()
        if sid not in reports:
            continue
        name = str(row[DRUG_NM]).strip()
        role = _role_to_int(str(row.get(DRUG_RO, "") or ""))
        if not name:
            continue
        drugs_rows.append((sid, name, role))

    reac_rows = []
    for _, row in reac_df.iterrows():
        sid = str(row[REAC_ID]).strip()
        if sid not in reports:
            continue
        pt = str(row[REAC_PT]).strip()
        if not pt:
            continue
        reac_rows.append((sid, pt))

    # Apply limit on unique reports
    keep_ids = list(reports.keys())
    if limit and len(keep_ids) > limit:
        keep_ids = keep_ids[:limit]
    keep_set = set(keep_ids)

    # Do not manage/close the caller-owned connection here.
    # Idempotent upsert per safetyreportid
    for sid in keep_ids:
        con.execute("DELETE FROM reactions WHERE safetyreportid = ?", [sid])
        con.execute("DELETE FROM drugs WHERE safetyreportid = ?", [sid])
        con.execute("DELETE FROM reports WHERE safetyreportid = ?", [sid])

    # Insert reports
    con.executemany(
        "INSERT INTO reports (safetyreportid, receivedate, primarysource_qualifier) VALUES (?, ?, ?)",
        [reports[sid] for sid in keep_ids],
    )

    # Insert drugs and reactions filtered by keep_set
    con.executemany(
        "INSERT INTO drugs (safetyreportid, drug_name, role) VALUES (?, ?, ?)",
        [row for row in drugs_rows if row[0] in keep_set],
    )
    con.executemany(
        "INSERT INTO reactions (safetyreportid, meddra_pt) VALUES (?, ?)",
        [row for row in reac_rows if row[0] in keep_set],
    )

    typer.echo(f"Ingested {len(keep_ids)} reports from {input}")
