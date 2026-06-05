"""
Europe PMC REST search backend.

Docs: https://europepmc.org/RestfulWebService
- No API key required; CC-licensed.
- Full-text URLs come back inline in `fullTextUrlList`, so this backend can
  both surface candidates AND pre-fill the OA cascade hint.
"""
from __future__ import annotations
import time
from typing import Any, Dict, List

from ..metadata.doi import normalize_doi
from ..metadata.normalize import normalize_title, first_author_surname
from .base import QueryResult, http_get_json


class EuropePmcBackend:
    source_name = "europe_pmc"
    base_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    def search(self, query: str, max_results: int = 25) -> QueryResult:
        params = {
            "query": query,
            "format": "json",
            "resultType": "core",
            "pageSize": min(max_results, 100),
        }
        t0 = time.time()
        try:
            data = http_get_json(self.base_url, params=params)
        except Exception as e:
            return QueryResult(self.source_name, query, [], 0, error=str(e),
                               elapsed_s=time.time() - t0)

        hits = ((data.get("resultList") or {}).get("result")) or []
        records = [self._normalize(h) for h in hits]
        return QueryResult(self.source_name, query, records, len(records),
                           elapsed_s=time.time() - t0)

    def _normalize(self, h: Dict[str, Any]) -> Dict[str, Any]:
        doi = normalize_doi(h.get("doi"))
        pmid = h.get("pmid")
        pmcid = h.get("pmcid")
        title = h.get("title")
        # authorList → authors[] of {fullName, ...}; authorString is the cite form
        if isinstance(h.get("authorList"), dict):
            authors = [a.get("fullName") for a in h["authorList"].get("author") or []
                       if a.get("fullName")]
        else:
            authors = [a.strip() for a in (h.get("authorString") or "").split(",") if a.strip()]

        year = None
        for k in ("pubYear", "firstPublicationDate"):
            v = h.get(k)
            if v and str(v)[:4].isdigit():
                year = int(str(v)[:4]); break

        # OA hint: pick the first PDF marked Open access / Free
        pdf_url, oa_status = None, "unknown"
        is_oa = h.get("isOpenAccess") == "Y"
        urls = ((h.get("fullTextUrlList") or {}).get("fullTextUrl")) or []
        for u in urls:
            if u.get("documentStyle") == "pdf" and u.get("availability") in ("Open access", "Free"):
                pdf_url = u.get("url")
                oa_status = u.get("availability").lower().replace(" ", "_")
                is_oa = True
                break

        return {
            "canonical_id": (f"pmid:{pmid}" if pmid
                              else f"doi:{doi}" if doi
                              else f"epmcid:{h.get('id')}" if h.get("id") else None),
            "doi": doi,
            "title": title,
            "title_normalized": normalize_title(title),
            "authors": authors,
            "first_author_surname": first_author_surname(authors),
            "year": year,
            "venue": h.get("journalTitle") or h.get("bookOrReportDetails"),
            "abstract": h.get("abstractText"),
            "abstract_source": "europe_pmc" if h.get("abstractText") else None,
            "pubmed_id": pmid,
            "pmcid": pmcid,
            "oa_status": oa_status,
            "is_oa": is_oa,
            "pdf_url": pdf_url,
            "cited_by_count": h.get("citedByCount"),
            "sources": ["europe_pmc"],
            "provenance": {"europe_pmc": {
                "id": h.get("id"),
                "source": h.get("source"),
                "pmid": pmid,
                "pmcid": pmcid,
            }},
        }
