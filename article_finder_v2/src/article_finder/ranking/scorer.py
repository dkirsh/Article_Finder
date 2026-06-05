"""
Transparent, explainable ranking.

Score = sum of weighted components. Components are all in [0, 1] and the
weights are tuned so the maximum possible score is 1.00. Every record
carries a `score_breakdown` showing which components contributed.

Ranking is deterministic: ties are broken by (year desc, cited_by desc,
canonical_id asc).
"""
from __future__ import annotations
import datetime as dt
from typing import Any, Dict, List
from ..metadata.normalize import normalize_title

WEIGHTS = {
    "topic_match":      0.30,
    "doi_present":      0.10,
    "abstract_present": 0.10,
    "pdf_available":    0.15,
    "citation_signal":  0.10,
    "recency":          0.10,
    "source_agreement": 0.05,
    "ai_triage":        0.10,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "weights must sum to 1.0"


def _topic_match(record: dict, topic_terms: set[str]) -> float:
    if not topic_terms:
        return 0.5  # neutral when caller did not supply terms
    hay = " ".join([
        (record.get("title") or ""),
        (record.get("abstract") or ""),
    ]).lower()
    if not hay.strip():
        return 0.0
    hits = sum(1 for t in topic_terms if t.lower() in hay)
    return min(hits / max(1, len(topic_terms)), 1.0)


def _citation_signal(c: int | None) -> float:
    if not c or c < 0:
        return 0.0
    # Log-scaled: 0 → 0, 10 → ~0.3, 100 → ~0.6, 1000 → ~0.9, 10000+ → ~1.0
    import math
    return min(math.log10(c + 1) / 4, 1.0)


def _recency(year: int | None) -> float:
    if not year:
        return 0.0
    now = dt.datetime.now(dt.timezone.utc).year
    age = max(0, now - int(year))
    # Anything ≤ 1 year old → 1.0; linear decay to 0 at 25 years.
    return max(0.0, 1.0 - (age / 25))


def _source_agreement(record: dict) -> float:
    n = len(record.get("sources") or [])
    if n <= 1:
        return 0.0
    if n == 2:
        return 0.5
    return 1.0


def score_record(record: dict, *, topic_terms: set[str],
                 ai_triage_score: float | None = None) -> dict:
    bd = {
        "topic_match":      _topic_match(record, topic_terms) * WEIGHTS["topic_match"],
        "doi_present":      WEIGHTS["doi_present"] if record.get("doi") else 0.0,
        "abstract_present": WEIGHTS["abstract_present"] if record.get("abstract") else 0.0,
        "pdf_available":    WEIGHTS["pdf_available"] if record.get("pdf_url") and record.get("is_oa") else 0.0,
        "citation_signal":  _citation_signal(record.get("cited_by_count")) * WEIGHTS["citation_signal"],
        "recency":          _recency(record.get("year")) * WEIGHTS["recency"],
        "source_agreement": _source_agreement(record) * WEIGHTS["source_agreement"],
        "ai_triage":        (ai_triage_score or 0.0) * WEIGHTS["ai_triage"],
    }
    total = round(sum(bd.values()), 4)
    return {"score": total, "score_breakdown": {k: round(v, 4) for k, v in bd.items()}}


def rank_records(records: List[Dict[str, Any]], *,
                 topic_terms: set[str]) -> List[Dict[str, Any]]:
    """
    Score every record (preserves any existing ai_triage_score on the record),
    sort by (score desc, year desc, cited_by desc, canonical_id asc), and
    assign `rank` 1..N.
    """
    scored = []
    for r in records:
        s = score_record(r, topic_terms=topic_terms,
                          ai_triage_score=r.get("ai_triage_score"))
        scored.append({**r, **s})
    scored.sort(
        key=lambda r: (
            -r.get("score", 0.0),
            -(r.get("year") or 0),
            -(r.get("cited_by_count") or 0),
            r.get("canonical_id") or "",
        )
    )
    for i, r in enumerate(scored, 1):
        r["rank"] = i
    return scored
