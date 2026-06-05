"""
Crossref search backend — public API, polite-pool with mailto.
Docs: https://api.crossref.org/swagger-ui/index.html
"""
from __future__ import annotations
import os
import re
import time
from typing import Any, Dict
from ..metadata.doi import normalize_doi
from ..metadata.normalize import normalize_title, first_author_surname
from .base import QueryResult, http_get_json


class CrossrefBackend:
    source_name = "crossref"
    base_url = "https://api.crossref.org/works"

    def __init__(self, mailto: str | None = None):
        self.mailto = mailto or os.environ.get("CROSSREF_MAILTO", "cogs160-track2@knowledge-atlas.local")

    def search(self, query: str, max_results: int = 25) -> QueryResult:
        params = {"query": query, "rows": min(max_results, 50), "mailto": self.mailto}
        t0 = time.time()
        try:
            data = http_get_json(self.base_url, params=params)
        except Exception as e:
            return QueryResult(self.source_name, query, [], 0, error=str(e),
                               elapsed_s=time.time() - t0)

        items = (data.get("message") or {}).get("items") or []
        records = [self._normalize(it) for it in items]
        return QueryResult(self.source_name, query, records, len(records),
                           elapsed_s=time.time() - t0)

    def _normalize(self, it: Dict[str, Any]) -> Dict[str, Any]:
        doi = normalize_doi(it.get("DOI"))
        title = (it.get("title") or [None])[0]
        authors = [f"{a.get('given','')} {a.get('family','')}".strip()
                   for a in (it.get("author") or [])]
        year = None
        date_parts = ((it.get("issued") or {}).get("date-parts") or [[None]])[0]
        if date_parts and date_parts[0]:
            year = int(date_parts[0])
        venue = (it.get("container-title") or [None])[0]
        # CrossRef abstracts are wrapped in JATS-XML
        abstract_raw = it.get("abstract") or ""
        abstract = re.sub(r"<[^>]+>", " ", abstract_raw).strip() if abstract_raw else None

        return {
            "canonical_id": f"doi:{doi}" if doi else None,
            "doi": doi,
            "title": title,
            "title_normalized": normalize_title(title),
            "authors": authors,
            "first_author_surname": first_author_surname(authors),
            "year": year,
            "venue": venue,
            "abstract": abstract,
            "abstract_source": "crossref" if abstract else None,
            "crossref_url": f"https://api.crossref.org/works/{doi}" if doi else None,
            "is_oa": False,  # CrossRef does not tell us OA status; Unpaywall will
            "oa_status": "unknown",
            "pdf_url": None,
            "cited_by_count": it.get("is-referenced-by-count"),
            "sources": ["crossref"],
            "provenance": {"crossref": {"doi": doi, "url": it.get("URL")}},
        }
