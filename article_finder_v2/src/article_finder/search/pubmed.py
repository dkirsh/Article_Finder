"""
PubMed search backend via NCBI E-utilities.

Two HTTP calls per search:
  1. esearch.fcgi  → returns a list of PMIDs
  2. esummary.fcgi → returns metadata for those PMIDs (batch)

Docs: https://www.ncbi.nlm.nih.gov/books/NBK25501/
- No API key required for ≤ 3 req/sec; we sleep 0.4 s between calls.
- An NCBI_API_KEY env var lifts the cap to 10 req/sec.
"""
from __future__ import annotations
import os
import time
from typing import Any, Dict

from ..metadata.doi import normalize_doi
from ..metadata.normalize import normalize_title, first_author_surname
from .base import QueryResult, http_get_json


class PubmedBackend:
    source_name = "pubmed"
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("NCBI_API_KEY")

    def _auth(self) -> dict:
        return {"api_key": self.api_key} if self.api_key else {}

    def search(self, query: str, max_results: int = 25) -> QueryResult:
        t0 = time.time()

        # 1. esearch -> PMIDs
        try:
            es_params = {
                "db": "pubmed", "term": query, "retmode": "json",
                "retmax": min(max_results, 50), **self._auth(),
            }
            es = http_get_json(f"{self.base}/esearch.fcgi", params=es_params)
        except Exception as e:
            return QueryResult(self.source_name, query, [], 0, error=str(e),
                               elapsed_s=time.time() - t0)

        ids = (es.get("esearchresult") or {}).get("idlist") or []
        if not ids:
            return QueryResult(self.source_name, query, [], 0,
                               elapsed_s=time.time() - t0)

        # NCBI politeness — small gap between esearch and esummary
        time.sleep(0.4)

        # 2. esummary -> metadata for those PMIDs
        try:
            sm_params = {
                "db": "pubmed", "id": ",".join(ids),
                "retmode": "json", **self._auth(),
            }
            sm = http_get_json(f"{self.base}/esummary.fcgi", params=sm_params)
        except Exception as e:
            return QueryResult(self.source_name, query, [], 0, error=str(e),
                               elapsed_s=time.time() - t0)

        result = sm.get("result") or {}
        uids = result.get("uids") or ids
        records = [self._normalize(result.get(uid) or {"uid": uid}) for uid in uids]
        records = [r for r in records if r]  # drop None
        return QueryResult(self.source_name, query, records, len(records),
                           elapsed_s=time.time() - t0)

    def _normalize(self, p: Dict[str, Any]) -> Dict[str, Any] | None:
        pmid = p.get("uid")
        if not pmid:
            return None

        # DOI extraction from articleids list
        doi = None
        pmcid = None
        for aid in (p.get("articleids") or []):
            kind = aid.get("idtype")
            val = aid.get("value")
            if kind == "doi":
                doi = normalize_doi(val)
            elif kind == "pmc":
                pmcid = val

        title = p.get("title")
        authors = [a.get("name") for a in (p.get("authors") or []) if a.get("name")]
        year = None
        pubdate = p.get("pubdate") or ""
        if pubdate[:4].isdigit():
            year = int(pubdate[:4])
        venue = p.get("fulljournalname") or p.get("source")

        return {
            "canonical_id": f"pmid:{pmid}",
            "doi": doi,
            "title": title,
            "title_normalized": normalize_title(title),
            "authors": authors,
            "first_author_surname": first_author_surname(authors),
            "year": year,
            "venue": venue,
            # esummary does NOT carry the abstract — collector will fetch it
            # via efetch if needed; we mark None here.
            "abstract": None,
            "abstract_source": None,
            "pubmed_id": pmid,
            "pmcid": pmcid,
            "oa_status": "unknown",
            "is_oa": bool(pmcid),  # PMC presence usually implies free full-text
            "pdf_url": None,
            "cited_by_count": None,
            "sources": ["pubmed"],
            "provenance": {"pubmed": {
                "id": pmid,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            }},
        }
