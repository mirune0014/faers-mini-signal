from __future__ import annotations

from datetime import date

import duckdb
import typer


def ingest_demo(
    con: duckdb.DuckDBPyConnection,
    *,
    reset: bool = True,
) -> None:
    """Load a tiny, self-contained demo dataset into the schema.

    This seeds a few reports/drugs/reactions so users can immediately try
    `faers-signal build` and `faers-signal ui` without implementing real ingest.

    Args:
        con: DuckDB connection with tables created by schema.sql.
        reset: If True, clears existing tables before inserting demo rows.
    """
    if reset:
        con.execute("DELETE FROM reactions;")
        con.execute("DELETE FROM drugs;")
        con.execute("DELETE FROM reports;")

    # Insert a small synthetic dataset.
    # reports: r1..r4
    con.execute(
        """
        INSERT INTO reports (safetyreportid, receivedate, primarysource_qualifier) VALUES
        ('r1', DATE '2024-01-01', 1),
        ('r2', DATE '2024-01-02', 1),
        ('r3', DATE '2024-01-03', 1),
        ('r4', DATE '2024-01-04', 2);
        """
    )

    # drugs: aspirin (suspect in r1,r2; concomitant in r4), ibuprofen (suspect in r3)
    con.execute(
        """
        INSERT INTO drugs (safetyreportid, drug_name, role) VALUES
        ('r1','aspirin',1),
        ('r2','aspirin',1),
        ('r3','ibuprofen',1),
        ('r4','aspirin',2);
        """
    )

    # reactions
    con.execute(
        """
        INSERT INTO reactions (safetyreportid, meddra_pt) VALUES
        ('r1','nausea'),
        ('r2','headache'),
        ('r3','nausea'),
        ('r4','nausea');
        """
    )

    typer.echo("Seeded demo dataset into reports/drugs/reactions.")

