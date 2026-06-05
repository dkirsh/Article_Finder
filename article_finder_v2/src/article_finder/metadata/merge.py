"""
Merge two candidate records describing the same paper without losing metadata.
"""
from __future__ import annotations
from typing import Any, Dict


def _prefer_longer(a, b):
    sa = (a or "").strip() if isinstance(a, str) else a
    sb = (b or "").strip() if isinstance(b, str) else b
    if not sa: return sb
    if not sb: return sa
    return sa if len(str(sa)) >= len(str(sb)) else sb


def merge_records(canonical: Dict[str, Any], other: Dict[str, Any]) -> Dict[str, Any]:
    """Merge `other` into `canonical`. Never silently drops metadata."""
    out = dict(canonical)
    for k in ("doi", "title", "year", "venue", "openalex_id", "semantic_scholar_id",
              "crossref_url", "pubmed_id", "pmcid", "arxiv_id", "oa_status",
              "pdf_url", "abstract_source"):
        if not out.get(k) and other.get(k):
            out[k] = other[k]
    out["abstract"] = _prefer_longer(out.get("abstract"), other.get("abstract"))
    if other.get("is_oa") and not out.get("is_oa"):
        out["is_oa"] = True
    if (other.get("authors") or []) and len(other.get("authors") or []) > len(out.get("authors") or []):
        out["authors"] = other["authors"]
        out["first_author_surname"] = other.get("first_author_surname") or out.get("first_author_surname")
    prov = dict(out.get("provenance") or {})
    for src, info in (other.get("provenance") or {}).items():
        prov.setdefault(src, info)
    out["provenance"] = prov
    out["sources"] = sorted(set(out.get("sources") or []) | set(other.get("sources") or []))
    return out
