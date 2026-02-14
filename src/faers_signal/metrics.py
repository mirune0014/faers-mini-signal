"""Disproportionality metrics for pharmacovigilance signal detection.

Zero-cell handling
------------------
When any cell in the 2×2 table (A, B, C, D) is zero, the Haldane–Anscombe
correction is applied: **+0.5 is added to all four cells**.  This is the
standard approach in pharmacoepidemiology and avoids division-by-zero or
log(0) while introducing minimal bias.

Reference:
  Haldane JBS (1956). "The estimation and significance of the logarithm
  of a ratio of frequencies."  Ann Hum Genet 20(4):309–311.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np


_HALDANE = 0.5  # Haldane–Anscombe correction constant


@dataclass
class ABCD:
    A: int
    B: int
    C: int
    D: int
    N: int


def _counts(abcd: ABCD) -> Tuple[float, float, float, float, float]:
    """Return (A, B, C, D, N) as floats, applying Haldane correction if needed."""
    a, b, c, d = float(abcd.A), float(abcd.B), float(abcd.C), float(abcd.D)
    n = float(abcd.N)

    # Apply Haldane–Anscombe correction when any cell is zero
    if a == 0 or b == 0 or c == 0 or d == 0:
        a += _HALDANE
        b += _HALDANE
        c += _HALDANE
        d += _HALDANE
        n += 2.0  # total increases by 4 × 0.5 = 2

    return a, b, c, d, n


def prr(abcd: ABCD) -> float:
    """Proportional Reporting Ratio = [A/(A+B)] / [C/(C+D)]."""
    A, B, C, D, _ = _counts(abcd)
    denom1 = A + B
    denom2 = C + D
    if denom1 <= 0 or denom2 <= 0 or C <= 0:
        return np.nan
    return (A / denom1) / (C / denom2)


def chi_square_1df(abcd: ABCD) -> float:
    """Yates-corrected chi-square (1 df) statistic."""
    A, B, C, D, N = _counts(abcd)
    denom = (A + B) * (C + D) * (A + C) * (B + D)
    if denom <= 0:
        return np.nan
    num = (abs(A * D - B * C) - N / 2.0) ** 2 * N
    return num / denom


def ror(abcd: ABCD) -> float:
    """Reporting Odds Ratio = (A*D) / (B*C)."""
    A, B, C, D, _ = _counts(abcd)
    bc = B * C
    if bc <= 0:
        return np.nan
    return (A * D) / bc


def ror_ci95(abcd: ABCD) -> Tuple[float, float]:
    """95 % confidence interval for the ROR (Wald method on log scale)."""
    A, B, C, D, _ = _counts(abcd)
    if A <= 0 or B <= 0 or C <= 0 or D <= 0:
        return (np.nan, np.nan)
    ln_ror = np.log((A * D) / (B * C))
    var = 1.0 / A + 1.0 / B + 1.0 / C + 1.0 / D
    se = np.sqrt(var)
    lo = np.exp(ln_ror - 1.96 * se)
    hi = np.exp(ln_ror + 1.96 * se)
    return (lo, hi)


def ic_simple(abcd: ABCD) -> float:
    """Information Component IC = log₂(A / E_A)."""
    A, B, C, D, N = _counts(abcd)
    EA = (A + B) * (A + C) / N
    if EA <= 0 or A <= 0:
        return np.nan
    return np.log2(A / EA)


def ic_simple_ci95(abcd: ABCD) -> Tuple[float, float]:
    """Approximate 95 % CI for the IC (delta-method variance)."""
    A, B, C, D, N = _counts(abcd)
    EA = (A + B) * (A + C) / N
    if EA <= 0 or A <= 0:
        return (np.nan, np.nan)
    ic = np.log2(A / EA)
    # var(ln(A/EA)) ≈ 1/A − 1/(A+B) − 1/(A+C) + 1/N
    var_ln = max(1.0 / A - 1.0 / (A + B) - 1.0 / (A + C) + 1.0 / N, 0.0)
    se_ic = np.sqrt(var_ln) / np.log(2.0)
    lo = ic - 1.96 * se_ic
    hi = ic + 1.96 * se_ic
    return (lo, hi)
