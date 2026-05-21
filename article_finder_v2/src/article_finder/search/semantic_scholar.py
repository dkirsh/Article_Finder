"""
Semantic Scholar Graph API search backend.

Docs: https://api.semanticscholar.org/api-docs/graph
- No API key required for basic search; an `S2_API_KEY` env var raises the
  rate-limit ceiling (≤ 100 req/min vs. ≤ 20 anon).
- We request a small `fields` projection so each row is ~1 KB.
"""
from __future__ import annotations
import os
import time
from typing import Any, Dict, List

from ..metadata.doi import normalize_doi
from ..metadata.normalize import normalize_title, first_author_surname
from .base import QueryResult, http_get_json


class SemanticScholarBackend:
    source_name = "semantic_scholar"
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search"

    DEFAULT_FIELDS = (
        "paperId,externalIds,title,abstract,authors,year,venue,"
        "openAccessPdf,citationCount,publicationTypes"
    )

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("S2_API_KEY")

    def search(self, query: str, max_results: int = 25) -> QueryResult:
        params = {
            "query": query,
            "limit": min(max_results, 100),
            "fields": self.DEFAULT_FIELDS,
        }
        headers = {"x-api-key": self.api_key} if self.api_key else None

        t0 = time.time()
        try:
            data = http_get_json(self.base_url, params=params, headers=headers)
        except Exception as e:
            return QueryResult(self.source_name, query, [], 0, error=str(e),
                               elapsed_s=time.time() - t0)

        records = [self._normalize(p) for p in (data.get("data") or [])]
        return QueryResult(self.source_name, query, records, len(records),
                           elapsed_s=time.time() - t0)

    def _normalize(self, p: Dict[str, Any]) -> Dict[str, Any]:
        ext = p.get("externalIds") or {}
        doi = normalize_doi(ext.get("DOI"))
        pmid = ext.get("PubMed")
        pmcid = ext.get("PubMedCentral")
        arxiv_id = ext.get("ArXiv")

        authors = [a.get("name") for a in (p.get("authors") or []) if a.get("name")]
        oa = p.get("openAccessPdf") or {}
        pdf_url = oa.get("url")
        is_oa = bool(pdf_url)
        title = p.get("title")

        return {
            "canonical_id": f"s2:{p.get('paperId')}" if p.get("paperId")
                              else (f"doi:{doi}" if doi else None),
            "doi": doi,
            "title": title,
            "title_normalized": normalize_title(title),
            "authors": authors,
            "first_author_surname": first_author_surname(authors),
            "year": p.get("year"),
            "venue": p.get("venue"),
            "abstract": p.get("abstract"),
            "abstract_source": "semantic_scholar" if p.get("abstract") else None,
            "openalex_id": None,
            "semantic_scholar_id": p.get("paperId"),
            "pubmed_id": pmid,
            "pmcid": pmcid,
            "arxiv_id": arxiv_id,
            "oa_status": "open" if is_oa else "unknown",
            "is_oa": is_oa,
            "pdf_url": pdf_url,
            "cited_by_count": p.get("citationCount"),
            "sources": ["semantic_scholar"],
            "provenance": {"semantic_scholar": {
                "id": p.get("paperId"),
                "url": f"https://www.semanticscholar.org/paper/{p.get('paperId')}",
            }},
        }
