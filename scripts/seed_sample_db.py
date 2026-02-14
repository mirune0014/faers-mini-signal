"""Fetch sample FAERS data from openFDA API and save as DuckDB file.

Run this once to generate ``data/sample.duckdb`` for bundling with the exe.

Usage:
    python scripts/seed_sample_db.py          # default: 5000 records
    python scripts/seed_sample_db.py 10000    # custom count
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import duckdb
from faers_signal._resources import get_sql
from faers_signal.download_openfda import fetch_and_ingest


def main() -> None:
    max_records = int(sys.argv[1]) if len(sys.argv) > 1 else 5000

    out_dir = ROOT / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    db_path = out_dir / "sample.duckdb"

    # Remove old file if exists to start fresh
    if db_path.exists():
        db_path.unlink()

    print(f"Creating sample DB at {db_path}")
    print(f"Target: {max_records} records from openFDA API")
    print()

    con = duckdb.connect(str(db_path))
    con.execute(get_sql("schema.sql"))

    def on_progress(fetched: int, target: int) -> None:
        pct = min(100, int(fetched / target * 100))
        bar = "█" * (pct // 2) + "░" * (50 - pct // 2)
        print(f"\r  [{bar}] {fetched:,}/{target:,} ({pct}%)", end="", flush=True)

    total = fetch_and_ingest(
        con,
        max_records=max_records,
        progress_callback=on_progress,
    )

    con.close()
    print()
    print(f"\nDone! Ingested {total:,} reports.")
    print(f"DB file: {db_path} ({db_path.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
