from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import typer

from . import __version__
from . import _resources


app = typer.Typer(help="FAERS mini signal: ETL, build metrics, export, and UI")


def _ensure_db(db_path: Path) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    # Load packaged schema.sql
    schema_sql = _resources.get_sql("schema.sql")
    con.execute(schema_sql)
    return con


@app.command()
def etl(
    source: str = typer.Option("openfda", help="openfda|qfiles|demo"),
    db: Path = typer.Option(Path("data/faers.duckdb"), help="DuckDB file path"),
    input: Path | None = typer.Option(None, help="Path to openFDA JSON/ZIP or directory (for source=openfda)"),
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

        ingest_openfda(con, input=input, since=since, until=until, limit=limit)
    elif source.lower() == "qfiles":
        from .ingest_qfiles import ingest_qfiles

        ingest_qfiles(con, input=input, since=since, until=until, limit=limit)
    elif source.lower() == "demo":
        from .ingest_demo import ingest_demo

        ingest_demo(con, reset=True)
    else:
        typer.echo("Unknown source. Use 'openfda' or 'qfiles'.", err=True)
        raise typer.Exit(code=2)


@app.command()
def build(
    db: Path = typer.Option(Path("data/faers.duckdb"), help="DuckDB file path"),
    suspect_only: bool = typer.Option(True, help="Use role=1 suspect drugs only"),
    min_a: int = typer.Option(3, help="Minimum A count to keep"),
    signal_mode: str = typer.Option("balanced", help="Signal mode: sensitive|balanced|specific"),
    out: Path = typer.Option(Path("data/metrics.parquet"), help="Output Parquet/CSV path"),
):
    """Compute A/B/C/D and metrics (PRR/ROR/IC/chi-square) and write to Parquet/CSV."""
    con = _ensure_db(db)
    # Load packaged abcd.sql
    sql = _resources.get_sql("abcd.sql")
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
        signal_flags,
        classify_signal,
    )
    from .analysis_spec import AnalysisSpec, Manifest
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

        flags = signal_flags(ab, min_a=min_a)
        is_signal = classify_signal(flags, mode=signal_mode)

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
                "flag_evans": flags["flag_evans"],
                "flag_ror025": flags["flag_ror025"],
                "flag_ic025": flags["flag_ic025"],
                "Signal": is_signal,
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

    # Write manifest
    spec = AnalysisSpec(
        suspect_only=suspect_only,
        min_a=min_a,
        drug_normalization="rxnorm_ingredient",
        signal_mode=signal_mode,
    )
    manifest = Manifest(spec=spec)
    manifest.populate_env()
    manifest.populate_db_stats(con)
    manifest.total_pairs = len(mdf)
    manifest.signal_count = int(mdf["Signal"].sum()) if not mdf.empty else 0

    manifest_path = out.with_suffix(".manifest.json")
    manifest.save(manifest_path)
    typer.echo(f"Wrote manifest to {manifest_path}")


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

    try:
        script = _resources.get_streamlit_app()
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=2)

    subprocess.run([sys.executable, "-m", "streamlit", "run", str(script)], env=env, check=False)


def main(argv: list[str] | None = None) -> None:
    app(standalone_mode=True)


if __name__ == "__main__":
    main(sys.argv[1:])
