"""Analysis specification and execution manifest for reproducible research.

Every analysis run produces:
  1. An ``AnalysisSpec`` — the *settings* used (filters, modes, thresholds).
  2. A ``Manifest`` — the *record* of the run (spec + data fingerprint + env).

Together they let a reader reconstruct **exactly** which conditions produced
the output file, satisfying the "explainability" requirement for research use.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import platform
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import duckdb


# ── Analysis Spec ────────────────────────────────────────────────

@dataclass
class AnalysisSpec:
    """Captures every user-controllable parameter of an analysis run."""

    # Data source
    source: str = "openfda"
    since: Optional[str] = None
    until: Optional[str] = None
    input_path: Optional[str] = None

    # Population filters
    suspect_only: bool = True
    min_a: int = 3
    drug_filter: Optional[str] = None
    pt_filter: Optional[str] = None

    # Drug normalisation
    drug_normalization: str = "raw"  # raw | rxnorm_ingredient

    # Volcano / FDR
    volcano_y_axis: str = "ic025"  # ic025 | fdr_bh
    fdr_test_set: Optional[str] = None  # e.g. "A>=3, N=1234 pairs"

    # Metric calculation
    haldane_correction: bool = True
    yates_correction: bool = True

    # Signal detection
    signal_mode: str = "balanced"  # sensitive | balanced | specific
    min_a_gate: int = 3

    # Ranking / TopN
    ranking_criterion: str = "ic025"  # ic025 | a_desc | balance_score
    top_n: int = 15
    tie_breaker: str = "a_desc,drug,pt"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, **kwargs: Any) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, **kwargs)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AnalysisSpec:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})


# ── Manifest ─────────────────────────────────────────────────────

@dataclass
class Manifest:
    """Execution record that accompanies every output file."""

    spec: AnalysisSpec = field(default_factory=AnalysisSpec)

    # Data fingerprint
    total_reports: int = 0
    total_drugs: int = 0
    total_reactions: int = 0
    total_pairs: int = 0
    normalization_stats: dict[str, int] = field(default_factory=dict)
    unmapped_top_20: list[dict[str, Any]] = field(default_factory=list)
    signal_count: int = 0

    # Environment
    python_version: str = ""
    os_info: str = ""
    package_versions: dict[str, str] = field(default_factory=dict)
    timestamp: str = ""

    def populate_env(self) -> None:
        """Fill environment fields automatically."""
        self.python_version = sys.version
        self.os_info = f"{platform.system()} {platform.release()}"
        self.timestamp = datetime.datetime.now().isoformat()

        # Core package versions
        for pkg in ("duckdb", "numpy", "pandas", "streamlit", "scipy"):
            try:
                mod = __import__(pkg)
                self.package_versions[pkg] = getattr(mod, "__version__", "unknown")
            except ImportError:
                pass

    def populate_db_stats(self, con: duckdb.DuckDBPyConnection) -> None:
        """Read row-count summary from the DB."""
        for table, attr in [
            ("reports", "total_reports"),
            ("drugs", "total_drugs"),
            ("reactions", "total_reactions"),
        ]:
            try:
                row = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                setattr(self, attr, row[0] if row else 0)
            except Exception:
                pass

        # Drug normalization stats
        try:
            rows = con.execute(
                "SELECT COALESCE(drug_norm_source, 'unknown') AS src, COUNT(*) AS cnt "
                "FROM drugs GROUP BY 1"
            ).fetchall()
            self.normalization_stats = {r[0]: r[1] for r in rows}
        except Exception:
            pass

        # Unmapped top-20 drug names (audit log)
        try:
            top_rows = con.execute(
                "SELECT drug_name, COUNT(*) AS cnt "
                "FROM drugs "
                "WHERE COALESCE(drug_norm_source, 'unmapped') = 'unmapped' "
                "GROUP BY 1 ORDER BY cnt DESC LIMIT 20"
            ).fetchall()
            self.unmapped_top_20 = [
                {"drug_name": r[0], "count": r[1]} for r in top_rows
            ]
        except Exception:
            pass

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    def to_json(self, **kwargs: Any) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, **kwargs)

    def save(self, path: Path) -> None:
        """Write manifest as JSON to *path*."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
