"""
Open-access PDF resolver.

This module asks legal sources whether a DOI is OA and where the PDF
lives. It NEVER returns a paywalled URL, and it has no knowledge of any
Sci-Hub mirror or unauthorized source.

Cascade order (rubric §D):
  1. Unpaywall (best_oa_location)
  2. OpenAlex (open_access.oa_url)
  3. Europe PMC (fullTextUrl)
  4. arXiv (if arxiv_id known)
  5. PubMed Central (if pmcid known)
  6. Publisher OA URL (only if upstream marked is_oa=True)
  7. CORE (if CORE_API_KEY env var is set; otherwise skipped)
  8. DOAJ (free; checks if the article's journal is OA-listed)
"""
from __future__ import annotations
import os
import time
from dataclasses import dataclass
from typing import Optional
from .base_http import http_get_json


@dataclass
class OALocation:
    pdf_url: str
    source: str  # 'unpaywall' | 'openalex' | 'europe_pmc' | 'arxiv' | 'pmc' | 'publisher_oa'
    license: Optional[str] = None
    version: Optional[str] = None  # 'publishedVersion' | 'acceptedVersion' | 'submittedVersion'
    legal_oa_proof: dict = None  # provenance for compliance


def resolve(record: dict, *, enable_network: bool = True) -> Optional[OALocation]:
    """Walk the cascade. Return the first OA location, or None."""
    if not enable_network:
        # Offline mode: only use what's already on the record.
        if record.get("is_oa") and record.get("pdf_url"):
            return OALocation(
                pdf_url=record["pdf_url"],
                source=record.get("abstract_source", "embedded"),
                license=None,
                legal_oa_proof={"reason": "is_oa=True on input record"},
            )
        return None

    doi = record.get("doi")
    # 1. Unpaywall
    if doi:
        loc = _unpaywall(doi)
        if loc:
            return loc

    # 2. OpenAlex (already on the record from search step)
    if record.get("is_oa") and record.get("pdf_url"):
        return OALocation(
            pdf_url=record["pdf_url"],
            source="openalex",
            license=record.get("oa_status"),
            legal_oa_proof={"openalex_open_access_is_oa": True},
        )

    # 3. Europe PMC
    if doi:
        loc = _europe_pmc(doi)
        if loc:
            return loc

    # 4. arXiv (if we have an arxiv_id from earlier)
    if record.get("arxiv_id"):
        return OALocation(
            pdf_url=f"https://arxiv.org/pdf/{record['arxiv_id']}.pdf",
            source="arxiv",
            license="arxiv",
            legal_oa_proof={"reason": "arXiv distribution license"},
        )

    # 5. PMC
    if record.get("pmcid"):
        return OALocation(
            pdf_url=f"https://www.ncbi.nlm.nih.gov/pmc/articles/{record['pmcid']}/pdf/",
            source="pmc",
            license="pmc",
            legal_oa_proof={"reason": "PMC open access"},
        )

    # 6. Publisher OA URL — only if upstream marked is_oa and we still have a URL
    if record.get("is_oa") and record.get("pdf_url"):
        return OALocation(
            pdf_url=record["pdf_url"],
            source="publisher_oa",
            license=record.get("oa_status"),
            legal_oa_proof={"reason": "upstream record marked is_oa with pdf_url"},
        )

    # 7. CORE (gated on API key)
    if doi:
        loc = _core(doi)
        if loc:
            return loc

    # 8. DOAJ (free; only fires when we have a DOI)
    if doi:
        loc = _doaj(doi)
        if loc:
            return loc

    return None


def _unpaywall(doi: str) -> Optional[OALocation]:
    email = os.environ.get("UNPAYWALL_EMAIL", "cogs160-track2@knowledge-atlas.local")
    try:
        data = http_get_json(f"https://api.unpaywall.org/v2/{doi}", params={"email": email})
    except Exception:
        return None
    if not data or not data.get("is_oa"):
        return None
    best = data.get("best_oa_location") or {}
    pdf = best.get("url_for_pdf") or best.get("url")
    if not pdf:
        return None
    return OALocation(
        pdf_url=pdf,
        source="unpaywall",
        license=best.get("license"),
        version=best.get("version"),
        legal_oa_proof={"unpaywall_is_oa": True,
                        "host_type": best.get("host_type"),
                        "license": best.get("license")},
    )


def _core(doi: str) -> Optional[OALocation]:
    """CORE — only fires if CORE_API_KEY is set. CORE returns OA full-text where
    aggregators have a license-clean copy of the manuscript."""
    key = os.environ.get("CORE_API_KEY")
    if not key:
        return None
    try:
        data = http_get_json(
            "https://api.core.ac.uk/v3/search/works",
            params={"q": f"doi:{doi}", "limit": 1},
            headers={"Authorization": f"Bearer {key}"},
        )
    except Exception:
        return None
    results = (data or {}).get("results") or []
    for r in results:
        pdf = r.get("downloadUrl") or r.get("fullTextLink")
        # CORE returns license metadata; only accept if it's an open license
        lic = (r.get("license") or "").lower()
        if pdf and ("cc-" in lic or "open" in lic or "public" in lic):
            return OALocation(
                pdf_url=pdf,
                source="core",
                license=r.get("license"),
                legal_oa_proof={"core_id": r.get("id"), "license": r.get("license")},
            )
    return None


def _doaj(doi: str) -> Optional[OALocation]:
    """DOAJ — Directory of Open Access Journals. Free, no key. We confirm the
    paper sits in a DOAJ-listed (= fully OA) journal; if it does, we still need
    a publisher OA URL (DOAJ stores article-level URLs when present)."""
    try:
        data = http_get_json(f"https://doaj.org/api/search/articles/doi:{doi}",
                              params={"pageSize": 1})
    except Exception:
        return None
    hits = (data or {}).get("results") or []
    for h in hits:
        bib = (h.get("bibjson") or {})
        links = bib.get("link") or []
        for link in links:
            if (link.get("type") in ("fulltext", "pdf")
                    and link.get("url", "").lower().endswith(".pdf")):
                return OALocation(
                    pdf_url=link["url"],
                    source="doaj",
                    license=(bib.get("journal") or {}).get("license", [{}])[0].get("type")
                            if bib.get("journal") else None,
                    legal_oa_proof={"doaj_id": h.get("id"),
                                    "in_doaj_journal": True},
                )
    return None


def _europe_pmc(doi: str) -> Optional[OALocation]:
    try:
        data = http_get_json(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            params={"query": f"DOI:{doi}", "format": "json", "resultType": "core"},
        )
    except Exception:
        return None
    hits = ((data or {}).get("resultList") or {}).get("result") or []
    for h in hits:
        if h.get("inPMC") == "Y" or (h.get("fullTextUrlList") or {}).get("fullTextUrl"):
            urls = (h.get("fullTextUrlList") or {}).get("fullTextUrl") or []
            for u in urls:
                if u.get("documentStyle") == "pdf" and u.get("availability") in ("Open access", "Free"):
                    return OALocation(
                        pdf_url=u.get("url"),
                        source="europe_pmc",
                        license=u.get("availability"),
                        legal_oa_proof={"europe_pmc_availability": u.get("availability")},
                    )
    return None
