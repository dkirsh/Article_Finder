"""Adapters from candidate discovery state into canonical AF records."""

from __future__ import annotations

from typing import Any


def candidate_to_paper(candidate: dict[str, Any]) -> dict[str, Any]:
    """Map one staged candidate into the canonical AF `papers` shape.

    This function does not write to the database. It makes the state mapping
    explicit so Track-2-style decisions do not leak into AF's vocabulary.
    """
    decision = candidate.get("triage_decision")
    doi = candidate.get("doi")
    if doi:
        paper_id = f"doi:{doi}"
    else:
        paper_id = f"candidate:{candidate['reference_id']}"

    if decision == "ACCEPT":
        triage_decision = "send_to_eater"
        status = "downloaded" if candidate.get("pdf_path") else "candidate"
    elif decision == "EDGE_CASE":
        triage_decision = "review"
        status = "candidate"
    elif decision == "REJECT":
        triage_decision = "reject"
        status = "rejected"
    elif decision == "MISSING_ABSTRACT":
        triage_decision = "pending"
        status = "candidate"
    else:
        triage_decision = "pending"
        status = "candidate"

    reasons = []
    if candidate.get("triage_reason"):
        reasons.append(candidate["triage_reason"])
    if candidate.get("target_id"):
        reasons.append(f"target:{candidate['target_type'] or 'unknown'}:{candidate['target_id']}")
    if candidate.get("discovered_via"):
        reasons.append(f"discovered_via:{candidate['discovered_via']}")

    tags = {
        "candidate_reference_id": candidate["reference_id"],
        "target_id": candidate.get("target_id"),
        "target_type": candidate.get("target_type"),
        "voi_breakdown": candidate.get("voi_breakdown_json"),
    }

    paper = {
        "paper_id": paper_id,
        "doi": doi,
        "title": candidate.get("title_raw") or "(untitled)",
        "authors": [],
        "year": candidate.get("publication_year"),
        "venue": candidate.get("venue"),
        "abstract": candidate.get("abstract"),
        "url": candidate.get("source_url"),
        "source": "candidate_discovery",
        "ingest_method": candidate.get("discovered_via") or "candidate_buffer",
        "finder_run_id": candidate.get("discovery_run_id"),
        "pdf_path": candidate.get("pdf_path"),
        "pdf_sha256": candidate.get("pdf_sha256"),
        "status": status,
        "triage_score": candidate.get("triage_confidence"),
        "triage_decision": triage_decision,
        "triage_reasons": reasons,
        "topic_score": candidate.get("local_heuristic_voi"),
        "topic_decision": "needs_abstract" if decision == "MISSING_ABSTRACT" else None,
        "topic_stage": "needs_abstract" if decision == "MISSING_ABSTRACT" else "candidate_discovery",
        "tags": tags,
        "human_notes": candidate.get("source_note"),
    }
    return {k: v for k, v in paper.items() if v is not None}


def promote_candidates_to_af(
    candidate_buffer,
    af_database,
    *,
    include_edge_cases: bool = False,
) -> list[str]:
    """Promote staged candidates into AF's canonical `papers` table.

    Returns promoted `paper_id` values. This deliberately uses AF's existing
    `Database.add_paper`, so AF dedupe fields and migrations remain canonical.
    """
    promoted: list[str] = []
    for row in candidate_buffer.rows_for_promotion(include_edge_cases=include_edge_cases):
        paper = candidate_to_paper(row)
        promoted.append(af_database.add_paper(paper))
    return promoted
