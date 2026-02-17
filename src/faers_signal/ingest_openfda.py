from __future__ import annotations

import json
import gzip
import zipfile
from pathlib import Path
from typing import Iterable, Iterator, Any, Optional

import duckdb
import typer


def _parse_date_yyyymmdd(s: str | None) -> Optional[str]:
    if not s:
        return None
    s = str(s)
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    # Fallback: try first 10 chars like YYYY-MM-DD
    t = s[:10]
    if len(t) == 10 and t[4] == "-" and t[7] == "-":
        return t
    return None


def _iter_events_from_json_bytes(data: bytes) -> Iterator[dict[str, Any]]:
    # Decode robustly (handle UTF-8 and UTF-8 with BOM). JSON spec mandates UTF-8.
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as e:
            raise ValueError(f"Failed to decode JSON as UTF-8: {e}") from e
    # Try parse as one JSON value
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "results" in obj and isinstance(obj["results"], list):
            for ev in obj["results"]:
                if isinstance(ev, dict):
                    yield ev
        elif isinstance(obj, list):
            for ev in obj:
                if isinstance(ev, dict):
                    yield ev
        elif isinstance(obj, dict):
            yield obj
        return
    except json.JSONDecodeError:
        pass
    # Fallback: NDJSON / JSONL
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "results" in obj and isinstance(obj["results"], list):
            for ev in obj["results"]:
                if isinstance(ev, dict):
                    yield ev
        elif isinstance(obj, dict):
            yield obj


_JSON_EXTS = {".json", ".jsonl", ".ndjson"}
_GZ_EXTS = {".gz"}


def _iter_files(input_path: Path) -> Iterator[tuple[str, bytes]]:
    """Yield (name, bytes) for JSON/NDJSON files inside a file or directory.

    - Supports plain `.json`/`.jsonl`/`.ndjson`
    - Supports gzip variants `*.json.gz`, `*.jsonl.gz`, `*.ndjson.gz`
    - Supports `.zip` containing the above
    - If `input_path` is a directory, walks recursively
    """
    if input_path.is_dir():
        for p in input_path.rglob("*"):
            if p.is_file():
                yield from _iter_files(p)
        return

    suffixes = [s.lower() for s in input_path.suffixes]
    name = input_path.name

    has_jsonlike = any(s in _JSON_EXTS for s in suffixes)
    has_gz = any(s in _GZ_EXTS for s in suffixes)
    has_zip = ".zip" in suffixes or input_path.suffix.lower() == ".zip"

    # Handle .zip archives first (including *.json.zip)
    if has_zip:
        with zipfile.ZipFile(input_path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                inner_name = info.filename
                inner_suffixes = [s.lower() for s in Path(inner_name).suffixes]
                if not any(s in _JSON_EXTS for s in inner_suffixes):
                    continue
                with zf.open(info, "r") as f:
                    raw = f.read()
                # Handle gz members if present
                if any(s in _GZ_EXTS for s in inner_suffixes):
                    try:
                        raw = gzip.decompress(raw)
                    except OSError:
                        # Not a valid gzip member despite extension; fall back to raw
                        pass
                yield inner_name, raw
        return

    # Handle gzip-compressed JSON (e.g., *.json.gz)
    if has_jsonlike and has_gz:
        with gzip.open(input_path, "rb") as f:
            data = f.read()
        yield name, data
        return

    # Handle plain JSON/NDJSON
    if has_jsonlike:
        data = input_path.read_bytes()
        yield name, data
        return


def _normalize_and_insert(
    con: duckdb.DuckDBPyConnection,
    events: Iterable[dict[str, Any]],
    *,
    since: Optional[str],
    until: Optional[str],
    limit: int,
) -> int:
    count = 0
    for ev in events:
        sid = str(ev.get("safetyreportid") or ev.get("safetyreportid_s", "")).strip()
        if not sid:
            continue
        # Dates: prefer receivedate, fallback to receiptdate
        rcv = _parse_date_yyyymmdd(ev.get("receivedate") or ev.get("receiptdate"))
        if since and rcv and rcv < since:
            continue
        if until and rcv and rcv > until:
            continue

        primary_qual = None
        ps = ev.get("primarysource") or {}
        if isinstance(ps, dict):
            pq = ps.get("qualifier")
            try:
                primary_qual = int(pq) if pq is not None else None
            except (TypeError, ValueError):
                primary_qual = None

        # Idempotent upsert: delete existing rows for this report ID
        con.execute("DELETE FROM reactions WHERE safetyreportid = ?", [sid])
        con.execute("DELETE FROM drugs WHERE safetyreportid = ?", [sid])
        con.execute("DELETE FROM reports WHERE safetyreportid = ?", [sid])

        con.execute(
            "INSERT INTO reports (safetyreportid, receivedate, primarysource_qualifier) VALUES (?, ?, ?)",
            [sid, rcv, primary_qual],
        )

        patient = ev.get("patient") or {}
        # drugs
        for d in patient.get("drug", []) or []:
            if not isinstance(d, dict):
                continue
            name = d.get("medicinalproduct")
            if not name:
                continue
            name = str(name).strip()
            role = d.get("drugcharacterization")
            try:
                role_i = int(role) if role is not None else None
            except (TypeError, ValueError):
                role_i = None

            # Drug name normalization
            from .normalize_drug import normalize_drug_name
            norm_name, norm_source = normalize_drug_name(
                name, drug_dict=d, use_rxnorm_api=True,
            )

            con.execute(
                "INSERT INTO drugs (safetyreportid, drug_name, drug_name_normalized, drug_norm_source, role) "
                "VALUES (?, ?, ?, ?, ?)",
                [sid, name, norm_name, norm_source, role_i],
            )

        # reactions
        for rx in patient.get("reaction", []) or []:
            if not isinstance(rx, dict):
                continue
            pt = rx.get("reactionmeddrapt")
            if not pt:
                continue
            pt = str(pt).strip()
            con.execute(
                "INSERT INTO reactions (safetyreportid, meddra_pt) VALUES (?, ?)",
                [sid, pt],
            )

        count += 1
        if limit and count >= limit:
            break

    return count


def ingest_openfda(
    con: duckdb.DuckDBPyConnection,
    *,
    input: Path | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 0,
) -> None:
    """Ingest openFDA drug event JSON (local files) into DuckDB.

    Best practice for local runs is to download a zipped JSON dump from openFDA
    and pass the path (file or directory) via ``--input``. Supports:
    - .json, .jsonl, .ndjson (optionally .gz)
    - .zip archives containing the above

    Args:
      con: DuckDB connection (schema must exist).
      input: Path to a file or directory with JSON.
      since: Inclusive lower bound on receivedate (YYYY-MM-DD).
      until: Inclusive upper bound on receivedate (YYYY-MM-DD).
      limit: Optional max number of reports to ingest (0 = no limit).
    """
    if input is None:
        typer.echo("--input is required for openfda ingest (path to json/zip)", err=True)
        raise typer.Exit(code=2)
    input = Path(input)
    if not input.exists():
        typer.echo(f"Input not found: {input}", err=True)
        raise typer.Exit(code=2)

    total = 0
    with con:
        for name, raw in _iter_files(input):
            events = _iter_events_from_json_bytes(raw)
            total += _normalize_and_insert(con, events, since=since, until=until, limit=0 if not limit else max(0, limit - total))
            if limit and total >= limit:
                break

    typer.echo(f"Ingested {total} reports from {input}")
