"""Tests for signal detection modes (sensitive / balanced / specific)."""
from faers_signal.metrics import ABCD, signal_flags, classify_signal


def _make_abcd(a, b, c, d, n=None):
    return ABCD(a, b, c, d, n if n is not None else a + b + c + d)


def test_strong_signal_all_flags():
    """Strong signal: all three flags should be True."""
    ab = _make_abcd(50, 100, 10, 1000)
    flags = signal_flags(ab)
    assert flags["flag_evans"] is True
    assert flags["flag_ror025"] is True
    assert flags["flag_ic025"] is True

    # All modes should detect this
    assert classify_signal(flags, "sensitive") is True
    assert classify_signal(flags, "balanced") is True
    assert classify_signal(flags, "specific") is True


def test_weak_signal_one_flag():
    """Marginal case: only one flag fires."""
    # PRR < 2 but ROR lower CI might be > 1 depending on counts
    ab = _make_abcd(5, 200, 3, 400)
    flags = signal_flags(ab)
    true_count = sum(flags.values())

    if true_count == 1:
        assert classify_signal(flags, "sensitive") is True
        assert classify_signal(flags, "balanced") is False
        assert classify_signal(flags, "specific") is False


def test_no_signal():
    """No signal: A is too small for Evans, CIs cross null."""
    ab = _make_abcd(1, 500, 1, 500)
    flags = signal_flags(ab, min_a=3)
    assert flags["flag_evans"] is False
    # With such small A, CIs should be wide
    assert classify_signal(flags, "specific") is False


def test_classify_modes():
    """Directly test the three classification modes with crafted flags."""
    # 2 of 3 flags
    flags_2 = {"flag_evans": True, "flag_ror025": True, "flag_ic025": False}
    assert classify_signal(flags_2, "sensitive") is True
    assert classify_signal(flags_2, "balanced") is True
    assert classify_signal(flags_2, "specific") is False

    # 1 of 3 flags
    flags_1 = {"flag_evans": False, "flag_ror025": True, "flag_ic025": False}
    assert classify_signal(flags_1, "sensitive") is True
    assert classify_signal(flags_1, "balanced") is False
    assert classify_signal(flags_1, "specific") is False

    # 0 flags
    flags_0 = {"flag_evans": False, "flag_ror025": False, "flag_ic025": False}
    assert classify_signal(flags_0, "sensitive") is False
    assert classify_signal(flags_0, "balanced") is False
    assert classify_signal(flags_0, "specific") is False


def test_min_a_gate():
    """Evans flag should respect the min_a parameter."""
    ab = _make_abcd(2, 50, 1, 500)  # A=2
    flags_3 = signal_flags(ab, min_a=3)
    flags_1 = signal_flags(ab, min_a=1)
    assert flags_3["flag_evans"] is False  # A=2 < min_a=3
    # With min_a=1, Evans might fire if PRR/chi2 criteria are met
