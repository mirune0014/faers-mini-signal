from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np


EPS = 1e-12


@dataclass
class ABCD:
    A: int
    B: int
    C: int
    D: int
    N: int


def _as_float(x: int) -> float:
    return float(x)


def _counts(abcd: ABCD) -> Tuple[float, float, float, float, float]:
    A = max(_as_float(abcd.A), EPS)
    B = max(_as_float(abcd.B), EPS)
    C = max(_as_float(abcd.C), EPS)
    D = max(_as_float(abcd.D), EPS)
    N = max(_as_float(abcd.N), EPS)
    return A, B, C, D, N


def prr(abcd: ABCD) -> float:
    A, B, C, D, _ = _counts(abcd)
    denom1 = A + B
    denom2 = C + D
    if denom1 <= 0 or denom2 <= 0 or C <= 0:
        return np.nan
    return (A / denom1) / (C / denom2)


def chi_square_1df(abcd: ABCD) -> float:
    A, B, C, D, N = _counts(abcd)
    denom = (A + B) * (C + D) * (A + C) * (B + D)
    if denom <= 0:
        return np.nan
    num = (abs(A * D - B * C) - N / 2.0) ** 2 * N
    return num / denom


def ror(abcd: ABCD) -> float:
    A, B, C, D, _ = _counts(abcd)
    if B <= 0 or C <= 0 or D <= 0:
        return np.nan
    return (A / B) / (C / D)


def ror_ci95(abcd: ABCD) -> Tuple[float, float]:
    A, B, C, D, _ = _counts(abcd)
    if A <= 0 or B <= 0 or C <= 0 or D <= 0:
        return (np.nan, np.nan)
    ln_ror = np.log((A / B) / (C / D))
    var = 1.0 / A + 1.0 / B + 1.0 / C + 1.0 / D
    se = np.sqrt(max(var, 0.0))
    lo = np.exp(ln_ror - 1.96 * se)
    hi = np.exp(ln_ror + 1.96 * se)
    return (lo, hi)


def ic_simple(abcd: ABCD) -> float:
    A, B, C, D, N = _counts(abcd)
    EA = (A + B) * (A + C) / max(N, EPS)
    if EA <= 0 or A <= 0:
        return np.nan
    return np.log2(A / EA)


def ic_simple_ci95(abcd: ABCD) -> Tuple[float, float]:
    A, B, C, D, N = _counts(abcd)
    EA = (A + B) * (A + C) / max(N, EPS)
    if EA <= 0 or A <= 0:
        return (np.nan, np.nan)
    ic = np.log2(A / EA)
    # Approximate variance of ln(A/EA) using delta method
    # var_ln ≈ 1/A - 1/(A+B) - 1/(A+C) + 1/N
    var_ln = max(1.0 / A - 1.0 / (A + B) - 1.0 / (A + C) + 1.0 / N, 0.0)
    se_ic = np.sqrt(var_ln) / np.log(2.0)
    lo = ic - 1.96 * se_ic
    hi = ic + 1.96 * se_ic
    return (lo, hi)

