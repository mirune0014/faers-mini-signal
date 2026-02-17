from pathlib import Path

import duckdb

from faers_signal.ingest_demo import ingest_demo


def test_ingest_demo_and_abcd_sql(tmp_path: Path):
    db = tmp_path / "demo.duckdb"
    con = duckdb.connect(str(db))

    # Create schema from packaged definition
    schema_sql = (Path(__file__).parents[1] / "src" / "faers_signal" / "schema.sql").read_text(encoding="utf-8")
    con.execute(schema_sql)

    # Seed demo data
    ingest_demo(con, reset=True)

    # Run ABCD SQL from repo
    sql = (Path(__file__).parents[1] / "src" / "faers_signal" / "abcd.sql").read_text(encoding="utf-8")
    df = con.execute(sql).fetch_df()

    # Should contain at least aspirin+nausea with A>=1
    row = df[(df["drug"] == "aspirin") & (df["pt"] == "nausea")].iloc[0]
    assert int(row.A) >= 1
    # Totals should be consistent with 4 reports
    assert int(row.total_reports) == 4
