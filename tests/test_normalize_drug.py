"""Tests for drug name normalization (mocking RxNorm API)."""
import json
from unittest.mock import patch, MagicMock

from faers_signal.normalize_drug import (
    normalize_drug_name,
    _normalize_from_openfda,
    _rxnorm_cache,
)


def test_openfda_harmonized_extraction():
    """Should extract substance_name from openfda dict."""
    drug_dict = {
        "medicinalproduct": "ASPIRIN TABLET 325MG",
        "openfda": {
            "substance_name": ["ASPIRIN"],
            "generic_name": ["ASPIRIN"],
        },
    }
    name = _normalize_from_openfda(drug_dict)
    assert name == "aspirin"


def test_openfda_harmonized_generic_fallback():
    """Should fall back to generic_name if substance_name is missing."""
    drug_dict = {
        "medicinalproduct": "METFORMIN HCL 500MG",
        "openfda": {
            "generic_name": ["METFORMIN HYDROCHLORIDE"],
        },
    }
    name = _normalize_from_openfda(drug_dict)
    assert name == "metformin hydrochloride"


def test_openfda_harmonized_missing():
    """Should return None if openfda dict is missing."""
    drug_dict = {"medicinalproduct": "UNKNOWN DRUG"}
    name = _normalize_from_openfda(drug_dict)
    assert name is None


def test_normalize_with_openfda():
    """Full normalize should use openfda harmonized first."""
    drug_dict = {
        "medicinalproduct": "ASPIRIN ENTERIC COATED 81MG",
        "openfda": {
            "substance_name": ["ASPIRIN"],
        },
    }
    name, source = normalize_drug_name("ASPIRIN ENTERIC COATED 81MG", drug_dict=drug_dict)
    assert name == "aspirin"
    assert source == "openfda_harmonized"


def test_normalize_fallback_no_api():
    """Without openfda and with API disabled, should fall back to lower(raw)."""
    name, source = normalize_drug_name("ZYRTEC TABS", drug_dict=None, use_rxnorm_api=False)
    assert name == "zyrtec tabs"
    assert source == "unmapped"


def test_normalize_rxnorm_api_mock():
    """Mock RxNorm API call to verify the flow."""
    _rxnorm_cache.clear()  # Clear cache for test isolation

    # Mock the approximate match response
    approx_resp = json.dumps({
        "approximateGroup": {
            "candidate": [
                {"rxcui": "12345", "score": "100"}
            ]
        }
    }).encode()

    # Mock the ingredient lookup response
    ingredient_resp = json.dumps({
        "relatedGroup": {
            "conceptGroup": [
                {
                    "tty": "IN",
                    "conceptProperties": [
                        {"rxcui": "67890", "name": "cetirizine"}
                    ]
                }
            ]
        }
    }).encode()

    def fake_urlopen(req, timeout=10):
        url = req.full_url if hasattr(req, 'full_url') else str(req)
        mock_resp = MagicMock()
        if "approximateTerm" in url:
            mock_resp.read.return_value = approx_resp
        elif "related" in url:
            mock_resp.read.return_value = ingredient_resp
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    with patch("faers_signal.normalize_drug.urllib.request.urlopen", side_effect=fake_urlopen):
        name, source = normalize_drug_name("ZYRTEC", drug_dict=None, use_rxnorm_api=True)

    assert name == "cetirizine"
    assert source == "rxnorm_api"

    _rxnorm_cache.clear()  # Clean up
