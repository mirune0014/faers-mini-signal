"""Fetch drug adverse event reports from the openFDA API and insert into DuckDB.

This module handles pagination, rate-limit retries, and search-query construction.
It reuses the normalisation logic from ``ingest_openfda`` for consistency.
"""
from __future__ import annotations

import time
import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Callable, Optional

import duckdb

from .ingest_openfda import _normalize_and_insert


_BASE_URL = "https://api.fda.gov/drug/event.json"

# openFDA hard limits
_MAX_LIMIT = 1000
_MAX_SKIP = 25000


def _build_search_query(
    *,
    drug: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> str | None:
    """Build an openFDA search query string from optional filters."""
    parts: list[str] = []
    if drug:
        # Quote the drug name for exact-ish matching
        safe = drug.strip().replace('"', "")
        parts.append(f'patient.drug.medicinalproduct:"{safe}"')
    if since and until:
        parts.append(f"receivedate:[{since.replace('-', '')} TO {until.replace('-', '')}]")
    elif since:
        parts.append(f"receivedate:[{since.replace('-', '')} TO 20991231]")
    elif until:
        parts.append(f"receivedate:[20040101 TO {until.replace('-', '')}]")

    return " AND ".join(parts) if parts else None


def _fetch_page(url: str, *, retries: int = 3, backoff: float = 2.0) -> dict[str, Any]:
    """Fetch a single API page with retry on 429 / 5xx."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                return json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                wait = backoff * (attempt + 1)
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, OSError):
            if attempt < retries - 1:
                time.sleep(backoff)
                continue
            raise
    raise RuntimeError(f"Failed to fetch {url} after {retries} retries")


def fetch_and_ingest(
    con: duckdb.DuckDBPyConnection,
    *,
    drug: str | None = None,
    since: str | None = None,
    until: str | None = None,
    max_records: int = 5000,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> int:
    """Fetch reports from openFDA API and insert into DuckDB.

    Args:
        con: DuckDB connection with schema already created.
        drug: Optional drug name filter (e.g. ``"aspirin"``).
        since: Optional start date ``YYYY-MM-DD``.
        until: Optional end date ``YYYY-MM-DD``.
        max_records: Maximum number of reports to fetch.
            Capped at (_MAX_SKIP + _MAX_LIMIT) = 26,000.
        progress_callback: ``callback(fetched_so_far, total_target)`` called after
            each page for progress reporting.

    Returns:
        Total number of reports ingested.
    """
    max_records = min(max_records, _MAX_SKIP + _MAX_LIMIT)

    search_q = _build_search_query(drug=drug, since=since, until=until)

    total_ingested = 0
    skip = 0

    while total_ingested < max_records and skip <= _MAX_SKIP:
        page_limit = min(_MAX_LIMIT, max_records - total_ingested)

        # Build URL
        params: dict[str, str] = {"limit": str(page_limit), "skip": str(skip)}
        if search_q:
            params["search"] = search_q

        url = _BASE_URL + "?" + urllib.parse.urlencode(
            params, quote_via=urllib.parse.quote
        )

        try:
            data = _fetch_page(url)
        except Exception:
            # API error, stop gracefully
            break

        results = data.get("results", [])
        if not results:
            break

        # Insert into DB
        count = _normalize_and_insert(
            con, results, since=since, until=until, limit=0
        )
        total_ingested += count

        if progress_callback:
            progress_callback(total_ingested, max_records)

        # If we got fewer than requested, no more pages
        if len(results) < page_limit:
            break

        skip += page_limit
        # Small delay to be polite to the API
        time.sleep(0.3)

    return total_ingested
