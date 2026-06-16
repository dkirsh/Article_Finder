"""Deterministic candidate triage gates.

This is intentionally modest. It gives the candidate stage a reviewable default
gate while leaving AF's richer taxonomy/embedding triage as the canonical
downstream classifier.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


def _tokens(text: str | None) -> set[str]:
    if not text:
        return set()
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}


@dataclass
class KeywordCandidateTriage:
    accept_terms: set[str] = field(default_factory=set)
    reject_terms: set[str] = field(default_factory=set)
    min_accept_hits: int = 2
    min_edge_hits: int = 1

    def classify(self, candidate: dict[str, Any]) -> dict[str, Any]:
        title = candidate.get("title_raw") or candidate.get("title") or ""
        abstract = candidate.get("abstract") or ""
        text_tokens = _tokens(f"{title} {abstract}")

        if not abstract.strip():
            return {
                "decision": "MISSING_ABSTRACT",
                "reason": "missing abstract",
                "confidence": 0.2,
            }

        reject_hits = sorted(self.reject_terms & text_tokens)
        if reject_hits:
            return {
                "decision": "REJECT",
                "reason": f"reject terms matched: {', '.join(reject_hits[:5])}",
                "confidence": min(0.95, 0.55 + 0.1 * len(reject_hits)),
            }

        accept_hits = sorted(self.accept_terms & text_tokens)
        if len(accept_hits) >= self.min_accept_hits:
            return {
                "decision": "ACCEPT",
                "reason": f"accept terms matched: {', '.join(accept_hits[:8])}",
                "confidence": min(0.95, 0.5 + 0.1 * len(accept_hits)),
            }
        if len(accept_hits) >= self.min_edge_hits:
            return {
                "decision": "EDGE_CASE",
                "reason": f"partial accept terms matched: {', '.join(accept_hits[:8])}",
                "confidence": 0.55,
            }
        return {
            "decision": "REJECT",
            "reason": "no target terms matched",
            "confidence": 0.45,
        }

    def apply_to_buffer(
        self,
        buffer,
        *,
        include_unset_only: bool = True,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        rows = buffer.rows_for_triage(include_unset_only=include_unset_only, limit=limit)
        results = []
        for row in rows:
            outcome = self.classify(row)
            buffer.set_triage(
                row["reference_id"],
                decision=outcome["decision"],
                reason=outcome["reason"],
                confidence=outcome["confidence"],
                stage="abstract_collected" if outcome["decision"] != "MISSING_ABSTRACT" else "needs_abstract",
            )
            results.append({"reference_id": row["reference_id"], **outcome})
        return results
