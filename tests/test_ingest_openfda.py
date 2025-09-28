from pathlib import Path
import io
import json
import zipfile

import duckdb

from faers_signal.ingest_openfda import ingest_openfda


def _make_openfda_zip(path: Path) -> Path:
    data = {
        "results": [
            {
                "safetyreportid": "r101",
                "receivedate": "20240101",
                "primarysource": {"qualifier": 1},
                "patient": {
                    "drug": [
                        {"medicinalproduct": "Aspirin", "drugcharacterization": 1},
                        {"medicinalproduct": "Metformin", "drugcharacterization": 2},
                    ],
                    "reaction": [
                        {"reactionmeddrapt": "nausea"}
                    ],
                },
            },
            {
                "safetyreportid": "r102",
                "receivedate": "20240102",
                "primarysource": {"qualifier": 1},
                "patient": {
                    "drug": [
                        {"medicinalproduct": "Ibuprofen", "drugcharacterization": 1}
                    ],
                    "reaction": [
                        {"reactionmeddrapt": "headache"}
                    ],
                },
            },
        ]
    }
    json_bytes = json.dumps(data).encode("utf-8")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("events.json", json_bytes)
    return path


def test_openfda_zip_ingest_and_abcd(tmp_path: Path):
    db = tmp_path / "openfda.duckdb"
    con = duckdb.connect(str(db))

    # Create schema
    con.execute(
        """
        CREATE TABLE reports(safetyreportid VARCHAR PRIMARY KEY, receivedate DATE, primarysource_qualifier INTEGER);
        CREATE TABLE drugs(safetyreportid VARCHAR, drug_name VARCHAR, role INTEGER);
        CREATE TABLE reactions(safetyreportid VARCHAR, meddra_pt VARCHAR);
        """
    )

    zip_path = _make_openfda_zip(tmp_path / "openfda_events.zip")
    ingest_openfda(con, input=zip_path, since=None, until=None, limit=0)

    # Run ABCD SQL
    sql = (Path(__file__).parents[1] / "src" / "faers_signal" / "abcd.sql").read_text(encoding="utf-8")
    df = con.execute(sql).fetch_df()

    # Two reports total
    assert int(df["total_reports"].iloc[0]) == 2

    # Check aspirin+nausea A=1
    row = df[(df["drug"].str.lower() == "aspirin") & (df["pt"].str.lower() == "nausea")]
    assert not row.empty
    assert int(row.iloc[0].A) == 1

    # Re-running ingest should remain idempotent (no double counts)
    ingest_openfda(con, input=zip_path, since=None, until=None, limit=0)
    df2 = con.execute(sql).fetch_df()
    row2 = df2[(df2["drug"].str.lower() == "aspirin") & (df2["pt"].str.lower() == "nausea")]
    assert int(row2.iloc[0].A) == 1

