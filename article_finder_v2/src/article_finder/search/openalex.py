"""
OpenAlex search backend — public API, no key required.
Docs: https://docs.openalex.org/
"""
from __future__ import annotations
import os
import time
from typing import Any, Dict, List
from ..metadata.doi import normalize_doi
from ..metadata.normalize import normalize_title, first_author_surname
from .base import QueryResult, http_get_json


class OpenAlexBackend:
    source_name = "openalex"
    base_url = "https://api.openalex.org/works"

    def __init__(self, mailto: str | None = None):
        self.mailto = mailto or os.environ.get("CROSSREF_MAILTO") or os.environ.get("UNPAYWALL_EMAIL")

    def search(self, query: str, max_results: int = 25) -> QueryResult:
        params = {
            "search": query,
            "per-page": min(max_results, 50),
            # NOTE: OpenAlex deprecated `host_venue` — use primary_location.source.
            "select": "id,doi,title,publication_year,primary_location,authorships,"
                      "abstract_inverted_index,open_access,cited_by_count",
        }
        if self.mailto:
            params["mailto"] = self.mailto

        t0 = time.time()
        try:
            data = http_get_json(self.base_url, params=params)
        except Exception as e:
            return QueryResult(self.source_name, query, [], 0, error=str(e),
                               elapsed_s=time.time() - t0)

        records = [self._normalize(w) for w in (data.get("results") or [])]
        return QueryResult(self.source_name, query, records, len(records),
                           elapsed_s=time.time() - t0)

    def _normalize(self, w: Dict[str, Any]) -> Dict[str, Any]:
        oa_id = (w.get("id") or "").rsplit("/", 1)[-1] or None
        doi = normalize_doi(w.get("doi"))
        authors = [a.get("author", {}).get("display_name", "")
                   for a in (w.get("authorships") or []) if a.get("author")]
        oa = w.get("open_access") or {}
        prim = w.get("primary_location") or {}
        # OpenAlex now nests venue under primary_location.source
        venue = ((prim.get("source") or {}).get("display_name")
                 or (w.get("host_venue") or {}).get("display_name"))
        abstract = self._reconstruct_abstract(w.get("abstract_inverted_index"))
        return {
            "canonical_id": f"openalex:{oa_id}" if oa_id else (f"doi:{doi}" if doi else None),
            "doi": doi,
            "title": w.get("title"),
            "title_normalized": normalize_title(w.get("title")),
            "authors": authors,
            "first_author_surname": first_author_surname(authors),
            "year": w.get("publication_year"),
            "venue": venue,
            "abstract": abstract,
            "abstract_source": "openalex" if abstract else None,
            "openalex_id": oa_id,
            "oa_status": oa.get("oa_status") or "unknown",
            "is_oa": bool(oa.get("is_oa")),
            "pdf_url": oa.get("oa_url") or (prim.get("pdf_url") if prim.get("is_oa") else None),
            "cited_by_count": w.get("cited_by_count"),
            "sources": ["openalex"],
            "provenance": {"openalex": {"id": oa_id, "url": w.get("id")}},
        }

    @staticmethod
    def _reconstruct_abstract(inv: dict | None) -> str | None:
        if not inv:
            return None
        positions: dict[int, str] = {}
        for word, idxs in inv.items():
            for i in idxs:
                positions[i] = word
        if not positions:
            return None
        return " ".join(positions[k] for k in sorted(positions))
