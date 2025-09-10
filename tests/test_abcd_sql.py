from pathlib import Path

import duckdb


def test_abcd_sql_counts(tmp_path: Path):
    db = tmp_path / "test.duckdb"
    con = duckdb.connect(str(db))

    # Create schema
    con.execute(
        """
        CREATE TABLE reports(safetyreportid VARCHAR PRIMARY KEY, receivedate DATE, primarysource_qualifier INTEGER);
        CREATE TABLE drugs(safetyreportid VARCHAR, drug_name VARCHAR, role INTEGER);
        CREATE TABLE reactions(safetyreportid VARCHAR, meddra_pt VARCHAR);
        """
    )

    # Insert small dataset
    con.execute("INSERT INTO reports VALUES ('r1', DATE '2024-01-01', 1), ('r2', DATE '2024-01-02', 1), ('r3', DATE '2024-01-03', 1)")
    con.execute(
        "INSERT INTO drugs VALUES ('r1','aspirin',1), ('r2','aspirin',1), ('r3','ibuprofen',1)"
    )
    con.execute(
        "INSERT INTO reactions VALUES ('r1','nausea'), ('r2','headache'), ('r3','nausea')"
    )

    sql = (Path(__file__).parents[1] / "src" / "faers_signal" / "abcd.sql").read_text(encoding="utf-8")
    df = con.execute(sql).fetch_df()

    # Find aspirin+nausea row
    row = df[(df["drug"] == "aspirin") & (df["pt"] == "nausea")].iloc[0]
    assert int(row.A) == 1
    assert int(row.B) == 1
    assert int(row.C) == 1
    assert int(row.D) == 0

