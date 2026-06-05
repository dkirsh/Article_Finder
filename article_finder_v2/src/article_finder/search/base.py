"""
Base interfaces for legal scholarly search backends.

Every backend returns records in the canonical schema documented in
docs/contracts/article_finder_contract.md §2.

Network access is centralised here: every HTTP call uses a single
session with a 15 s timeout, single-try retry on 5xx, and exponential
backoff on 429. Each call is logged to query_log.json by the caller.
"""
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

try:
    import requests
except ImportError:
    requests = None  # only required for live network calls


HTTP_TIMEOUT = 15
MAX_RETRIES = 1


@dataclass
class QueryResult:
    source: str
    query: str
    records: List[Dict[str, Any]]
    n_results: int
    error: Optional[str] = None
    elapsed_s: Optional[float] = None


class SearchBackend(Protocol):
    """Every search client implements .search(query, max_results)."""
    source_name: str
    def search(self, query: str, max_results: int = 25) -> QueryResult: ...


def http_get_json(url: str, *, params: dict | None = None,
                  headers: dict | None = None) -> dict:
    """Single-try-with-backoff GET that returns parsed JSON or raises."""
    if requests is None:
        raise RuntimeError("requests not installed; cannot make live calls")
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=HTTP_TIMEOUT)
            if r.status_code == 429:
                time.sleep(5 + attempt * 5)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(2)
    raise RuntimeError(f"HTTP GET failed: {url} ({last_err})")
