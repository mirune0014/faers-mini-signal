"""Launcher for the PyInstaller-bundled FAERS Mini Signal application.

Starts Streamlit directly (no subprocess) to avoid infinite loop in frozen .exe.
"""
from __future__ import annotations

import multiprocessing
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _get_base_dir() -> Path:
    """Return the base directory (PyInstaller _MEIPASS or script directory)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def _get_data_dir() -> Path:
    """Return the data directory next to the exe (or in the repo)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "data"
    return Path(__file__).resolve().parent / "data"


def _init_demo_db(db_path: Path) -> None:
    """If the DB does not exist, initialise schema and seed demo data."""
    if db_path.exists():
        return

    print(f"Initialising demo database at {db_path} ...")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    base = _get_base_dir()
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    src_dir = base / "src"
    if src_dir.exists() and str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    import duckdb
    from faers_signal._resources import get_sql
    from faers_signal.ingest_demo import ingest_demo

    con = duckdb.connect(str(db_path))
    con.execute(get_sql("schema.sql"))
    ingest_demo(con, reset=True)
    con.close()
    print("Demo database ready.")


def _open_browser_delayed(port: int, delay: float = 3.0) -> None:
    """Open browser after a short delay (runs in a background thread)."""
    time.sleep(delay)
    webbrowser.open(f"http://localhost:{port}")


def main() -> None:
    # Required for PyInstaller on Windows to prevent multiprocessing issues
    multiprocessing.freeze_support()

    PORT = 8501
    data_dir = _get_data_dir()
    db_path = data_dir / "faers.duckdb"

    # Initialise demo DB if needed
    _init_demo_db(db_path)

    # Set environment so streamlit_app.py knows the DB path
    os.environ["FAERS_DB"] = str(db_path)

    # Locate streamlit_app.py
    base = _get_base_dir()
    candidates = [
        base / "app" / "streamlit_app.py",
        Path(__file__).resolve().parent / "app" / "streamlit_app.py",
    ]
    app_script = None
    for c in candidates:
        if c.exists():
            app_script = str(c)
            break

    if app_script is None:
        print("ERROR: Could not locate streamlit_app.py")
        input("Press Enter to exit...")
        sys.exit(1)

    # Ensure faers_signal package is importable by the Streamlit script
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    src_dir = base / "src"
    if src_dir.exists() and str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    print(f"Starting FAERS Mini Signal on http://localhost:{PORT}")
    print("Close this window to stop the application.\n")

    # Open browser in background thread after a short delay
    browser_thread = threading.Thread(
        target=_open_browser_delayed, args=(PORT,), daemon=True
    )
    browser_thread.start()

    # Run Streamlit directly in-process (NOT via subprocess).
    # Using subprocess with sys.executable would re-run FaersMiniSignal.exe
    # causing an infinite loop.
    sys.argv = [
        "streamlit",
        "run",
        app_script,
        "--global.developmentMode", "false",
        "--server.port", str(PORT),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]

    from streamlit.web import cli as stcli
    stcli.main()


if __name__ == "__main__":
    main()
