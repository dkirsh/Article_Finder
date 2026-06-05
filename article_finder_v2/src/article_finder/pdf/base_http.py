"""Tiny shared HTTP helper used by oa_resolver and downloader."""
from __future__ import annotations
import time
try:
    import requests
except ImportError:
    requests = None

HTTP_TIMEOUT = 15


def http_get_json(url: str, *, params: dict | None = None,
                  headers: dict | None = None) -> dict:
    if requests is None:
        raise RuntimeError("requests not installed")
    r = requests.get(url, params=params, headers=headers, timeout=HTTP_TIMEOUT)
    if r.status_code == 429:
        time.sleep(5)
        r = requests.get(url, params=params, headers=headers, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json()
