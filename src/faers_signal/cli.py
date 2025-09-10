from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import typer

from . import __version__


app = typer.Typer(help="FAERS mini signal: ETL, build metrics, export, and UI")


def _ensure_db(db_path: Path) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    schema_sql = (Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")
    con.execute(schema_sql)
    return con


@app.command()
def etl(
    source: str = typer.Option("openfda", help="openfda|qfiles"),
    db: Path = typer.Option(Path("data/faers.duckdb"), help="DuckDB file path"),
    since: str | None = typer.Option(None, help="YYYY-MM-DD start date filter (optional)"),
    until: str | None = typer.Option(None, help="YYYY-MM-DD end date filter (optional)"),
    limit: int = typer.Option(0, help="Row limit for ingest (0 = no limit)"),
):
    """Ingest FAERS from openFDA (zipped JSON preferred) or quarterly files into DuckDB.

    This is a minimal scaffold. See docs for data acquisition details.
    """
    con = _ensure_db(db)
    if source.lower() == "openfda":
        from .ingest_openfda import ingest_openfda

        ingest_openfda(con, since=since, until=until, limit=limit)
    elif source.lower() == "qfiles":
        from .ingest_qfiles import ingest_qfiles

        ingest_qfiles(con, since=since, until=until, limit=limit)
    else:
        typer.echo("Unknown source. Use 'openfda' or 'qfiles'.", err=True)
        raise typer.Exit(code=2)


@app.command()
def build(
    db: Path = typer.Option(Path("data/faers.duckdb"), help="DuckDB file path"),
    suspect_only: bool = typer.Option(True, help="Use role=1 suspect drugs only"),
    min_a: int = typer.Option(3, help="Minimum A count to keep"),
    out: Path = typer.Option(Path("data/metrics.parquet"), help="Output Parquet/CSV path"),
):
    """Compute A/B/C/D and metrics (PRR/ROR/IC/chi-square) and write to Parquet/CSV."""
    con = _ensure_db(db)
    sql = (Path(__file__).with_name("abcd.sql")).read_text(encoding="utf-8")
    # Toggle suspect-only by adjusting a temp view
    if not suspect_only:
        # When not suspect-only, we treat all drugs as candidates (role in (1,2,3))
        sql = sql.replace("FROM drugs WHERE role = 1", "FROM drugs WHERE role in (1,2,3)")
    abcd_df = con.execute(sql).fetch_df()

    from .metrics import (
        ABCD,
        prr,
        chi_square_1df,
        ror,
        ror_ci95,
        ic_simple,
        ic_simple_ci95,
    )
    import numpy as np
    import pandas as pd

    def _metrics_row(row: pd.Series):
        ab = ABCD(int(row.A), int(row.B), int(row.C), int(row.D), int(row.total_reports))
        prr_v = prr(ab)
        chi = chi_square_1df(ab)
        ror_v = ror(ab)
        ror_l, ror_u = ror_ci95(ab)
        ic_v = ic_simple(ab)
        ic_l, ic_u = ic_simple_ci95(ab)
        return pd.Series(
            {
                "PRR": prr_v,
                "Chi2_1df": chi,
                "ROR": ror_v,
                "ROR_CI_L": ror_l,
                "ROR_CI_U": ror_u,
                "IC": ic_v,
                "IC_CI_L": ic_l,
                "IC_CI_U": ic_u,
            }
        )

    if not abcd_df.empty:
        mdf = abcd_df.join(abcd_df.apply(_metrics_row, axis=1))
        mdf = mdf[mdf["A"] >= min_a]
    else:
        mdf = abcd_df

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() == ".csv":
        mdf.to_csv(out, index=False)
    else:
        mdf.to_parquet(out, index=False)
    typer.echo(f"Wrote metrics to {out}")


@app.command()
def export(
    db: Path = typer.Option(Path("data/faers.duckdb")),
    sql: str = typer.Option("SELECT * FROM reports LIMIT 10", help="SQL to run"),
    out: Path = typer.Option(Path("data/export.csv")),
):
    """Run an arbitrary SELECT and export to CSV/Parquet."""
    con = duckdb.connect(str(db))
    df = con.execute(sql).fetch_df()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() == ".csv":
        df.to_csv(out, index=False)
    else:
        df.to_parquet(out, index=False)
    typer.echo(f"Wrote {len(df):,} rows to {out}")


@app.command()
def version():
    """Show version."""
    typer.echo(__version__)


@app.command()
def ui(
    db: Path = typer.Option(Path("data/faers.duckdb"), help="DuckDB file path"),
):
    """Launch Streamlit app."""
    import subprocess
    import os

    env = os.environ.copy()
    env["FAERS_DB"] = str(db)
    script = Path(__file__).parents[1] / "app" / "streamlit_app.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(script)], env=env, check=False)


def main(argv: list[str] | None = None) -> None:
    app(standalone_mode=True)


if __name__ == "__main__":
    main(sys.argv[1:])
