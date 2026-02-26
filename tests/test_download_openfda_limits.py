from faers_signal import download_openfda


def test_download_openfda_limits_constants():
    assert download_openfda._MAX_LIMIT == 1000
    assert download_openfda._MAX_SKIP == 25000
    assert download_openfda._MAX_SKIP + download_openfda._MAX_LIMIT == 26000

