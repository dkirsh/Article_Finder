"""
arXiv search backend — public Atom-XML feed. All arXiv PDFs are legally
free under arXiv's distribution license.
Docs: https://info.arxiv.org/help/api/user-manual.html
"""
from __future__ import annotations
import re
import time
from typing import Any, Dict
from xml.etree import ElementTree as ET
from ..metadata.doi import normalize_doi
from ..metadata.normalize import normalize_title, first_author_surname
from .base import QueryResult, HTTP_TIMEOUT

try:
    import requests
except ImportError:
    requests = None

NS = {"atom": "http://www.w3.org/2005/Atom",
      "arxiv": "http://arxiv.org/schemas/atom"}


class ArxivBackend:
    source_name = "arxiv"
    base_url = "https://export.arxiv.org/api/query"

    def search(self, query: str, max_results: int = 25) -> QueryResult:
        if requests is None:
            return QueryResult(self.source_name, query, [], 0,
                               error="requests not installed")
        params = {
            "search_query": f"all:{query}",
            "max_results": min(max_results, 50),
            "sortBy": "relevance",
        }
        t0 = time.time()
        try:
            r = requests.get(self.base_url, params=params, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            root = ET.fromstring(r.text)
        except Exception as e:
            return QueryResult(self.source_name, query, [], 0, error=str(e),
                               elapsed_s=time.time() - t0)

        records = [self._normalize(entry) for entry in root.findall("atom:entry", NS)]
        return QueryResult(self.source_name, query, records, len(records),
                           elapsed_s=time.time() - t0)

    def _normalize(self, entry) -> Dict[str, Any]:
        def t(path, ns=NS):
            el = entry.find(path, ns)
            return (el.text or "").strip() if el is not None else None

        title = re.sub(r"\s+", " ", t("atom:title") or "").strip() or None
        abstract = re.sub(r"\s+", " ", t("atom:summary") or "").strip() or None
        arxiv_url = t("atom:id")  # http://arxiv.org/abs/2103.01234v1
        arxiv_id = arxiv_url.rsplit("/", 1)[-1] if arxiv_url else None
        published = t("atom:published")
        year = int(published[:4]) if published and published[:4].isdigit() else None

        authors = []
        for a in entry.findall("atom:author", NS):
            n = a.find("atom:name", NS)
            if n is not None and n.text:
                authors.append(n.text.strip())

        # PDF link
        pdf_url = None
        for link in entry.findall("atom:link", NS):
            if link.get("type") == "application/pdf":
                pdf_url = link.get("href"); break
        if not pdf_url and arxiv_id:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        # DOI: some arXiv records carry one via arxiv:doi
        doi_el = entry.find("arxiv:doi", NS)
        doi = normalize_doi(doi_el.text) if doi_el is not None else None

        return {
            "canonical_id": f"arxiv:{arxiv_id}" if arxiv_id else (f"doi:{doi}" if doi else None),
            "doi": doi,
            "title": title,
            "title_normalized": normalize_title(title),
            "authors": authors,
            "first_author_surname": first_author_surname(authors),
            "year": year,
            "venue": "arXiv",
            "abstract": abstract,
            "abstract_source": "arxiv" if abstract else None,
            "arxiv_id": arxiv_id,
            # arXiv content is openly distributable under arXiv's license terms.
            "is_oa": True,
            "oa_status": "gold",
            "pdf_url": pdf_url,
            "cited_by_count": None,
            "sources": ["arxiv"],
            "provenance": {"arxiv": {"id": arxiv_id, "url": arxiv_url}},
        }
