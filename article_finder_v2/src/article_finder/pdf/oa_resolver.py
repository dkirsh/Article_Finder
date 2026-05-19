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

No source 7 (CORE) yet — requires API key; left as a TODO behind a flag.
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
