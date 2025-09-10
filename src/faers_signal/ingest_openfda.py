from __future__ import annotations

import duckdb
import typer


def ingest_openfda(
    con: duckdb.DuckDBPyConnection,
    *,
    since: str | None = None,
    until: str | None = None,
    limit: int = 0,
) -> None:
    """Minimal placeholder for openFDA ingest.

    This function currently creates empty tables (via schema) and logs a note.
    Extend to download zipped JSON or page the API, normalize, and COPY into DuckDB.
    """
    typer.echo("openfda ingest placeholder: extend to load data.")

