from __future__ import annotations

import duckdb
import typer


def ingest_qfiles(
    con: duckdb.DuckDBPyConnection,
    *,
    since: str | None = None,
    until: str | None = None,
    limit: int = 0,
) -> None:
    """Minimal placeholder for quarterly files ingest.

    Implement parsing of the latest small sample of ASCII/XML files and insert
    rows into reports/drugs/reactions. For EVP, this is deferred.
    """
    typer.echo("qfiles ingest placeholder: extend to load data.")

