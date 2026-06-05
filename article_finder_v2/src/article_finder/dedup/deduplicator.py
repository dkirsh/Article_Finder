"""
Multi-key deduplicator with provenance merge.

Match rules, applied in order:
1. Normalized DOI exact match
2. OpenAlex / Semantic Scholar / PubMed ID exact match
3. Token-Jaccard title similarity ≥ 0.85 AND same first-author surname AND year within 1
4. Token-Jaccard title similarity ≥ 0.95 (title alone, for DOI-less records)
"""
from __future__ import annotations
from typing import Any, Dict, List, Tuple
from ..metadata.normalize import title_similarity, title_overlap
from ..metadata.merge import merge_records


TITLE_PLUS_AUTHOR_THRESHOLD = 0.85
TITLE_ALONE_THRESHOLD = 0.95


def _same_id(a: Dict[str, Any], b: Dict[str, Any]) -> str | None:
    """Return the field name where a and b share an exact id, or None."""
    if a.get("doi") and a.get("doi") == b.get("doi"):
        return "doi"
    for f in ("openalex_id", "semantic_scholar_id", "pubmed_id", "arxiv_id"):
        if a.get(f) and a.get(f) == b.get(f):
            return f
    return None


def _title_author_year_match(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    sa, sb = a.get("first_author_surname"), b.get("first_author_surname")
    if not sa or not sb or sa != sb:
        return False
    ya, yb = a.get("year"), b.get("year")
    if ya is None or yb is None or abs(int(ya) - int(yb)) > 1:
        return False
    # Two paths: high Jaccard similarity OR very high overlap (one is a
    # longer phrasing of the other). Both require surname + year match
    # (already checked above), so the false-positive risk is low.
    sim = title_similarity(a.get("title"), b.get("title"))
    over = title_overlap(a.get("title"), b.get("title"))
    return sim >= TITLE_PLUS_AUTHOR_THRESHOLD or over >= 0.85


def _title_only_match(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return title_similarity(a.get("title"), b.get("title")) >= TITLE_ALONE_THRESHOLD


def deduplicate(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Returns (canonical_records, dedup_report).

    canonical_records: list of merged records, each with a stable duplicate_group_id.
    dedup_report: per-group {group_id, canonical_id, members, match_reasons}.
    """
    groups: List[Dict[str, Any]] = []  # each: {"canonical": dict, "members": [dict], "reasons": [str]}

    for rec in records:
        matched = None
        match_reason = None
        for g in groups:
            c = g["canonical"]
            shared = _same_id(c, rec)
            if shared:
                matched, match_reason = g, f"{shared}_exact"
                break
            if _title_author_year_match(c, rec):
                matched, match_reason = g, "title+author+year"
                break
            if _title_only_match(c, rec):
                matched, match_reason = g, "title_high_sim"
                break
        if matched:
            matched["canonical"] = merge_records(matched["canonical"], rec)
            matched["members"].append(rec)
            matched["reasons"].append(match_reason)
        else:
            groups.append({"canonical": dict(rec), "members": [rec], "reasons": []})

    canonical_records, report = [], []
    for i, g in enumerate(groups, 1):
        gid = f"grp-{i:04d}"
        c = g["canonical"]
        c["duplicate_group_id"] = gid
        canonical_records.append(c)
        report.append({
            "group_id": gid,
            "canonical_id": c.get("canonical_id"),
            "canonical_doi": c.get("doi"),
            "member_count": len(g["members"]),
            "sources": c.get("sources", []),
            "match_reasons": g["reasons"],
        })
    return canonical_records, report
