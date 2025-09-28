from pathlib import Path
import io
import zipfile

import duckdb

from faers_signal.ingest_qfiles import ingest_qfiles


def _make_qfiles_zip(path: Path) -> Path:
    # Minimal pipe-delimited DEMO/DRUG/REAC with uppercase headers
    demo = "PRIMARYID|FDA_DT\n201|20240101\n202|20240102\n"
    drug = "PRIMARYID|DRUGNAME|ROLE_COD\n201|ASPIRIN|PS\n202|IBUPROFEN|PS\n"
    reac = "PRIMARYID|PT\n201|NAUSEA\n202|HEADACHE\n"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("DEMO2024Q1.txt", demo)
        zf.writestr("DRUG2024Q1.txt", drug)
        zf.writestr("REAC2024Q1.txt", reac)
    return path


def test_qfiles_zip_ingest_and_abcd(tmp_path: Path):
    db = tmp_path / "q.duckdb"
    con = duckdb.connect(str(db))

    # Create schema
    con.execute(
        """
        CREATE TABLE reports(safetyreportid VARCHAR PRIMARY KEY, receivedate DATE, primarysource_qualifier INTEGER);
        CREATE TABLE drugs(safetyreportid VARCHAR, drug_name VARCHAR, role INTEGER);
        CREATE TABLE reactions(safetyreportid VARCHAR, meddra_pt VARCHAR);
        """
    )

    zip_path = _make_qfiles_zip(tmp_path / "faers_qfiles.zip")
    ingest_qfiles(con, input=zip_path, since=None, until=None, limit=0)

    # Run ABCD SQL
    sql = (Path(__file__).parents[1] / "src" / "faers_signal" / "abcd.sql").read_text(encoding="utf-8")
    df = con.execute(sql).fetch_df()

    # Two reports total
    assert int(df["total_reports"].iloc[0]) == 2

    # Check aspirin+nausea A=1
    row = df[(df["drug"].str.lower() == "aspirin") & (df["pt"].str.lower() == "nausea")]
    assert not row.empty
    assert int(row.iloc[0].A) == 1

    # Idempotency: re-run
    ingest_qfiles(con, input=zip_path, since=None, until=None, limit=0)
    df2 = con.execute(sql).fetch_df()
    row2 = df2[(df2["drug"].str.lower() == "aspirin") & (df2["pt"].str.lower() == "nausea")]
    assert int(row2.iloc[0].A) == 1

