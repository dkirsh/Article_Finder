"""Candidate discovery sources.

These wrappers write source results into `CandidateBuffer`; they do not insert
directly into AF's canonical `papers` table.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol


class WorkSearchClient(Protocol):
    def search_works(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        ...


@dataclass(frozen=True)
class TargetSearch:
    query: str
    target_id: str
    target_type: str = "question"
    local_heuristic_voi: float | None = None
    voi_breakdown: dict[str, Any] | None = None
    discovery_run_id: str | None = None


class OpenAlexCandidateSource:
    """Harvest OpenAlex works into the candidate buffer."""

    def __init__(
        self,
        *,
        email: str | None = None,
        api_key: str | None = None,
        client: WorkSearchClient | None = None,
    ):
        if client is not None:
            self.client = client
        else:
            from ingest.doi_resolver import OpenAlexClient

            self.client = OpenAlexClient(email=email, api_key=api_key)

    def search(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        return [work for work in self.client.search_works(query, limit=limit) if work]

    def harvest(
        self,
        buffer,
        target: TargetSearch,
        *,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for work in self.search(target.query, limit=limit):
            source_note = {
                "openalex_url": work.get("url"),
                "oa_url": work.get("oa_url"),
                "open_access": work.get("open_access"),
                "cited_by_count": work.get("cited_by_count"),
                "source": work.get("source", "openalex"),
            }
            reference_id, action = buffer.add_candidate(
                {
                    **work,
                    "source_note": json.dumps(source_note, sort_keys=True),
                },
                discovered_via="openalex_search",
                discovered_query=target.query,
                discovery_run_id=target.discovery_run_id,
                target_id=target.target_id,
                target_type=target.target_type,
                local_heuristic_voi=target.local_heuristic_voi,
                voi_breakdown_json=(
                    json.dumps(target.voi_breakdown, sort_keys=True)
                    if target.voi_breakdown is not None
                    else None
                ),
            )
            results.append(
                {
                    "reference_id": reference_id,
                    "action": action,
                    "title": work.get("title"),
                    "doi": work.get("doi"),
                }
            )
        return results
