# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for FAERS Mini Signal.

Build with:
    pyinstaller faers_signal.spec

Output: dist/FaersMiniSignal/ (one-directory mode)
"""
import os
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata, collect_data_files, collect_submodules

block_cipher = None

# Paths relative to this spec file
HERE = Path(SPECPATH)
SRC = HERE / "src" / "faers_signal"
APP = HERE / "app"

# Collect package metadata required by importlib.metadata at runtime
extra_datas = []
for pkg in [
    "streamlit",
    "altair",
    "pandas",
    "numpy",
    "pyarrow",
    "duckdb",
    "click",
    "jinja2",
    "markupsafe",
    "packaging",
    "toml",
    "rich",
    "typer",
    "scipy",
    "importlib_metadata",
]:
    try:
        extra_datas += copy_metadata(pkg)
    except Exception:
        pass  # Package not installed or no metadata; skip

# Collect streamlit data files (templates, static assets, etc.)
try:
    extra_datas += collect_data_files("streamlit")
except Exception:
    pass

# Collect altair data files (schema JSON, vegalite)
try:
    extra_datas += collect_data_files("altair")
except Exception:
    pass

a = Analysis(
    [str(HERE / "launcher.py")],
    pathex=[str(HERE / "src")],
    binaries=[],
    datas=[
        # SQL files used by faers_signal
        (str(SRC / "schema.sql"), "faers_signal"),
        (str(SRC / "abcd.sql"), "faers_signal"),
        # Python source of faers_signal package (needed for Streamlit subprocess)
        (str(SRC), "faers_signal"),
        # Streamlit app script
        (str(APP / "streamlit_app.py"), "app"),
    ] + extra_datas,
    hiddenimports=[
        # Core
        "duckdb",
        "numpy",
        "scipy",
        "scipy.special",
        "scipy.stats",
        "pandas",
        "pyarrow",
        "pyarrow.lib",
        "pyarrow.pandas_compat",
        "pyarrow.vendored.version",
        # Streamlit and its deps
        "streamlit",
        "streamlit.web",
        "streamlit.web.cli",
        "streamlit.web.bootstrap",
        "streamlit.runtime",
        "streamlit.runtime.scriptrunner",
        "altair",
        "jinja2",
        "markupsafe",
        "toml",
        "click",
        "rich",
        "packaging",
        "importlib_metadata",
        # CLI
        "typer",
        "typer.main",
        # faers_signal package
        "faers_signal",
        "faers_signal.__init__",
        "faers_signal._resources",
        "faers_signal.cli",
        "faers_signal.metrics",
        "faers_signal.ingest_demo",
        "faers_signal.ingest_openfda",
        "faers_signal.ingest_qfiles",
    ] + collect_submodules("streamlit"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "PIL",
        "IPython",
        "notebook",
        "pytest",
        "ruff",
        "black",
        "mypy",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FaersMiniSignal",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Show console for status messages
    icon=None,     # Add an .ico file here if desired
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FaersMiniSignal",
)
