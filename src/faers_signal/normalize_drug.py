"""Drug name normalization via openFDA harmonized fields and RxNorm API.

Strategy (in order of preference):
  1. openFDA harmonized ``openfda.substance_name`` — exact, high quality
  2. RxNorm ``getApproximateMatch`` API — fuzzy match to ingredient
  3. Fallback: ``lower(raw_name)``

The RxNorm REST API is free and requires no API key for public RxNorm data.
Rate limit: ~20 requests/second — we add a small sleep between calls.
"""
from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from typing import Optional, Tuple

# In-memory cache to avoid repeated API calls for the same raw name
_rxnorm_cache: dict[str, Tuple[Optional[str], str]] = {}

_RXNAV_BASE = "https://rxnav.nlm.nih.gov/REST"


def _normalize_from_openfda(drug_dict: dict) -> Optional[str]:
    """Extract ingredient name from openFDA harmonized fields.

    openFDA annotates drugs with ``openfda.substance_name`` (ingredient level)
    when it can match the ``medicinalproduct`` string exactly. This is the
    most reliable source but coverage is incomplete.
    """
    openfda = drug_dict.get("openfda")
    if not openfda or not isinstance(openfda, dict):
        return None

    # Prefer substance_name (ingredient), then generic_name
    for field in ("substance_name", "generic_name"):
        names = openfda.get(field)
        if names and isinstance(names, list) and len(names) > 0:
            name = str(names[0]).strip()
            if name:
                return name.lower()
    return None


def _normalize_via_rxnorm(raw_name: str) -> Tuple[Optional[str], str]:
    """Look up ingredient name via RxNorm approximate match API.

    Returns (normalized_name, source) where source is 'rxnorm_api' or 'unmapped'.
    """
    key = raw_name.lower().strip()
    if key in _rxnorm_cache:
        return _rxnorm_cache[key]

    try:
        encoded = urllib.parse.quote(key)
        url = f"{_RXNAV_BASE}/approximateTerm.json?term={encoded}&maxEntries=1"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        candidates = (
            data.get("approximateGroup", {})
            .get("candidate", [])
        )
        if candidates:
            rxcui = candidates[0].get("rxcui")
            if rxcui:
                # Get ingredient name from RxCUI
                name = _rxcui_to_ingredient(rxcui)
                if name:
                    result = (name.lower(), "rxnorm_api")
                    _rxnorm_cache[key] = result
                    time.sleep(0.05)  # rate limiting
                    return result

    except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError):
        pass

    result = (None, "unmapped")
    _rxnorm_cache[key] = result
    return result


def _rxcui_to_ingredient(rxcui: str) -> Optional[str]:
    """Resolve an RxCUI to its ingredient-level name."""
    try:
        url = f"{_RXNAV_BASE}/rxcui/{rxcui}/related.json?tty=IN"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        groups = data.get("relatedGroup", {}).get("conceptGroup", [])
        for group in groups:
            props = group.get("conceptProperties", [])
            if props:
                return props[0].get("name")

        # If no ingredient relation, use the original concept name
        url2 = f"{_RXNAV_BASE}/rxcui/{rxcui}/properties.json"
        req2 = urllib.request.Request(url2, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req2, timeout=10) as resp2:
            data2 = json.loads(resp2.read())
        props = data2.get("properties", {})
        return props.get("name")

    except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError):
        return None


def normalize_drug_name(
    raw_name: str,
    drug_dict: Optional[dict] = None,
    use_rxnorm_api: bool = True,
) -> Tuple[str, str]:
    """Normalize a drug name to ingredient level.

    Args:
        raw_name: Original drug name from the report.
        drug_dict: The full drug dict from openFDA (contains ``openfda`` sub-dict).
        use_rxnorm_api: Whether to call the RxNorm API for unmatched names.

    Returns:
        (normalized_name, source) where source is one of:
        'openfda_harmonized', 'rxnorm_api', or 'unmapped'.
    """
    # Step 1: Try openFDA harmonized
    if drug_dict:
        harmonized = _normalize_from_openfda(drug_dict)
        if harmonized:
            return (harmonized, "openfda_harmonized")

    # Step 2: Try RxNorm API
    if use_rxnorm_api and raw_name.strip():
        rx_name, rx_source = _normalize_via_rxnorm(raw_name)
        if rx_name:
            return (rx_name, rx_source)

    # Step 3: Fallback
    return (raw_name.lower().strip(), "unmapped")
