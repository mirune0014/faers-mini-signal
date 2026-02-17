import math

from faers_signal.metrics import (
    ABCD,
    benjamini_hochberg_fdr,
    chi_square_1df,
    chi_square_p_value,
    ic_simple,
    ic_simple_ci95,
    prr,
    ror,
    ror_ci95,
)


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
    """With Haldane–Anscombe correction, zero cells produce finite values."""
    ab = ABCD(A=0, B=5, C=20, D=100, N=125)

    # Haldane adds +0.5 to all cells → A=0.5, B=5.5, C=20.5, D=100.5
    # PRR should be finite and < 1 (rare event with this drug)
    p = prr(ab)
    assert not math.isnan(p)
    assert p < 1.0  # A=0 means under-reported

    # ROR should be finite and < 1
    r = ror(ab)
    assert not math.isnan(r)
    assert r < 1.0

    # CI should be finite with lo < hi
    lo, hi = ror_ci95(ab)
    assert not math.isnan(lo) and not math.isnan(hi)
    assert lo < hi

    # IC should be finite and negative (under-reported)
    ic = ic_simple(ab)
    assert not math.isnan(ic)
    assert ic < 0


def test_metrics_all_zeros():
    """Edge case: all cells zero should still produce finite values."""
    ab = ABCD(A=0, B=0, C=0, D=0, N=0)
    # After Haldane: A=B=C=D=0.5, N=2 → perfectly balanced → PRR ≈ 1
    p = prr(ab)
    assert not math.isnan(p)
    assert math.isclose(p, 1.0, rel_tol=0.01)


def test_benjamini_hochberg_fdr_known_values():
    pvals = [0.01, 0.04, 0.03, 0.002]
    qvals = benjamini_hochberg_fdr(pvals)

    # Expected BH-adjusted q-values in original order
    expected = [0.02, 0.04, 0.04, 0.008]
    for q, e in zip(qvals, expected):
        assert math.isclose(q, e, rel_tol=1e-9)


def test_benjamini_hochberg_fdr_empty():
    assert benjamini_hochberg_fdr([]) == []


def test_chi_square_p_value_monotonic():
    weak = ABCD(A=5, B=5, C=5, D=5, N=20)
    strong = ABCD(A=20, B=1, C=1, D=20, N=42)

    p_weak = chi_square_p_value(weak)
    p_strong = chi_square_p_value(strong)

    assert 0.0 <= p_weak <= 1.0
    assert 0.0 <= p_strong <= 1.0
    assert p_strong < p_weak

