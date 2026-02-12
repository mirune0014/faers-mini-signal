"""Resource loading compatible with both normal Python and PyInstaller frozen environments."""
from __future__ import annotations

import sys
from pathlib import Path


def _base_dir() -> Path:
    """Return the base directory for packaged resources.

    In a PyInstaller bundle, files are extracted to ``sys._MEIPASS``.
    In a normal Python environment, resources live alongside this module.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    # Normal: resources are next to this file (src/faers_signal/)
    return Path(__file__).resolve().parent


def get_sql(name: str) -> str:
    """Read a ``.sql`` file bundled with the package.

    Args:
        name: Filename such as ``"schema.sql"`` or ``"abcd.sql"``.
    """
    base = _base_dir()
    # In PyInstaller, datas are placed in the destination specified in the spec
    # (e.g. "faers_signal/schema.sql"). In normal mode, files sit next to this module.
    candidates = [
        base / name,                 # Normal: next to this module
        base / "faers_signal" / name,  # PyInstaller: datas dest = "faers_signal"
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    tried = ", ".join(str(p) for p in candidates)
    raise FileNotFoundError(f"Could not find {name}. Tried: {tried}")


def get_streamlit_app() -> Path:
    """Return the absolute path to ``streamlit_app.py``.

    Searches in order:
    1. PyInstaller bundle (``_MEIPASS/app/streamlit_app.py``)
    2. Repository layout (``../../app/streamlit_app.py`` relative to this file)
    3. Current working directory (``app/streamlit_app.py``)
    """
    candidates = []

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "app" / "streamlit_app.py")  # type: ignore[attr-defined]

    # Repo editable / installed layout
    here = Path(__file__).resolve().parent
    candidates.append(here.parents[1] / "app" / "streamlit_app.py")  # repo root
    candidates.append(here.parents[0] / "app" / "streamlit_app.py")  # site-packages
    candidates.append(Path.cwd() / "app" / "streamlit_app.py")

    for c in candidates:
        if c.exists():
            return c

    tried = ", ".join(str(c) for c in candidates)
    raise FileNotFoundError(f"Could not locate streamlit_app.py. Tried: {tried}")
