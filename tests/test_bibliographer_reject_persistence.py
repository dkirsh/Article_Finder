from __future__ import annotations

from pathlib import Path

import pytest

import core.database as database_module
from core.database import Database
from search.bibliographer import Bibliographer


class FixedScorer:
    def __init__(self, result: dict) -> None:
        self.result = result

    def score_paper(self, paper: dict) -> dict:
        return dict(self.result)


def _bibliographer(db: Database, scorer_result: dict, threshold: float) -> Bibliographer:
    bibliographer = Bibliographer.__new__(Bibliographer)
    bibliographer.db = db
    bibliographer.threshold = threshold
    bibliographer._scorer = FixedScorer(scorer_result)
    bibliographer._seen_signatures = set()
    bibliographer._existing_dois = set()
    return bibliographer


@pytest.fixture
def db(monkeypatch, tmp_path: Path) -> Database:
    monkeypatch.setattr(
        database_module,
        "build_paper_dedupe_fields",
        lambda _paper, *, deduped_at: {
            "ae_corpus_match_status": "unmatched",
            "ae_corpus_match_candidates_json": "[]",
            "ae_corpus_deduped_at": deduped_at,
        },
    )
    return Database(tmp_path / "article_finder.db")


@pytest.mark.parametrize(
    ("scorer_result", "threshold", "expected_reason"),
    [
        (
            {
                "triage_score": 0.05,
                "triage_decision": "reject",
                "triage_reasons": ["off-topic outcome"],
            },
            0.40,
            "bibliographer:scorer_reject",
        ),
        (
            {"triage_score": 0.25, "triage_decision": "review"},
            0.40,
            "bibliographer:below_threshold:0.25<0.4",
        ),
    ],
)
def test_relevance_exclusion_is_persisted_without_clobbering_existing_fields(
    db: Database,
    scorer_result: dict,
    threshold: float,
    expected_reason: str,
) -> None:
    db.add_paper(
        {
            "paper_id": "doi:10.1234/reject-me",
            "doi": "10.1234/reject-me",
            "title": "Complete source record",
            "abstract": "Evidence-bearing abstract",
            "venue": "Environment and Behavior",
            "pdf_path": "/corpus/reject-me.pdf",
            "status": "candidate",
            "triage_decision": "review",
        }
    )
    paper = {
        "doi": "10.1234/reject-me",
        "title": "Complete source record",
        "source": "openalex",
    }

    result = _bibliographer(db, scorer_result, threshold)._evaluate_and_import(
        paper, "env.light_out.attention"
    )
    stored = db.get_paper("doi:10.1234/reject-me")

    assert result == "rejected"
    assert stored is not None
    assert stored["status"] == "rejected"
    assert stored["triage_decision"] == "reject"
    assert expected_reason in stored["triage_reasons"]
    assert stored["abstract"] == "Evidence-bearing abstract"
    assert stored["venue"] == "Environment and Behavior"
    assert stored["pdf_path"] == "/corpus/reject-me.pdf"


def test_reject_persistence_failure_is_not_counted_as_rejection() -> None:
    class FailingDatabase:
        def add_paper(self, paper: dict) -> str:
            raise RuntimeError("write failed")

    bibliographer = _bibliographer(
        FailingDatabase(),
        {"triage_score": 0.0, "triage_decision": "reject"},
        0.40,
    )

    with pytest.raises(RuntimeError, match="write failed"):
        bibliographer._evaluate_and_import(
            {"title": "Cannot persist", "doi": "10.1234/failure"},
            "env.light_out.attention",
        )
