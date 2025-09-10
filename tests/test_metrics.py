import math

from faers_signal.metrics import ABCD, prr, chi_square_1df, ror, ror_ci95, ic_simple, ic_simple_ci95


def test_metrics_basic_values():
    ab = ABCD(A=10, B=5, C=20, D=100, N=135)

    assert math.isclose(prr(ab), 4.0, rel_tol=1e-6)

    chi = chi_square_1df(ab)
    # Rough expected value around 16.5 given Yates correction formula
    assert chi > 10 and chi < 25

    assert math.isclose(ror(ab), 10.0, rel_tol=1e-6)
    lo, hi = ror_ci95(ab)
    assert lo < 10 < hi
    assert math.isclose(lo, 3.085, rel_tol=0.05)
    assert math.isclose(hi, 32.36, rel_tol=0.05)

    ic = ic_simple(ab)
    assert math.isclose(ic, math.log2(3.0), rel_tol=1e-6)
    ic_lo, ic_hi = ic_simple_ci95(ab)
    assert ic_lo < ic < ic_hi


def test_metrics_zero_handling():
    ab = ABCD(A=0, B=5, C=20, D=100, N=125)
    assert math.isnan(prr(ab))
    assert math.isnan(ror(ab))
    lo, hi = ror_ci95(ab)
    assert math.isnan(lo) and math.isnan(hi)
    ic = ic_simple(ab)
    assert math.isnan(ic)

