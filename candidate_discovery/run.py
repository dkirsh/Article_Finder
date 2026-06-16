"""One-target candidate discovery orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.database import Database

from .adapters import promote_candidates_to_af
from .buffer import CandidateBuffer
from .oa_acquisition import download_pdf_url
from .sources import OpenAlexCandidateSource, TargetSearch
from .triage import KeywordCandidateTriage


def acquire_accepted_oa_pdfs(
    buffer: CandidateBuffer,
    *,
    out_dir: str | Path,
    fetch=None,
) -> list[dict[str, Any]]:
    acquired = []
    for row in buffer.rows_for_promotion(include_edge_cases=False):
        result = download_pdf_url(
            row.get("oa_pdf_url"),
            row["reference_id"],
            Path(out_dir),
            fetch=fetch,
        )
        if result is None:
            continue
        path, sha = result
        buffer.record_pdf(
            row["reference_id"],
            pdf_path=path,
            pdf_sha256=sha,
            source="openalex_oa_url",
        )
        acquired.append(
            {
                "reference_id": row["reference_id"],
                "pdf_path": str(path),
                "sha256": sha,
            }
        )
    return acquired


def run_target_discovery(
    *,
    target: TargetSearch,
    candidate_db: str | Path,
    af_db: str | Path,
    accept_terms: set[str],
    reject_terms: set[str] | None = None,
    limit: int = 10,
    source: OpenAlexCandidateSource | None = None,
    acquire_pdfs: bool = False,
    pdf_dir: str | Path | None = None,
    pdf_fetch=None,
    promote: bool = True,
) -> dict[str, Any]:
    buffer = CandidateBuffer(candidate_db)
    af_database = Database(Path(af_db))
    source = source or OpenAlexCandidateSource()

    harvested = source.harvest(buffer, target, limit=limit)
    triage = KeywordCandidateTriage(
        accept_terms=accept_terms,
        reject_terms=reject_terms or set(),
    ).apply_to_buffer(buffer)

    acquired = []
    if acquire_pdfs:
        acquired = acquire_accepted_oa_pdfs(
            buffer,
            out_dir=pdf_dir or Path(candidate_db).parent / "candidate_pdfs",
            fetch=pdf_fetch,
        )

    promoted = promote_candidates_to_af(buffer, af_database) if promote else []

    return {
        "target_id": target.target_id,
        "query": target.query,
        "harvested": harvested,
        "triage": triage,
        "acquired_pdfs": acquired,
        "promoted": promoted,
    }
