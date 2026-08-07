from __future__ import annotations

from pathlib import Path

import pytest

import core.database as database_module
from core.contract_fsm_runtime import ContractFSMViolation
from core.database import Database


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
    result = Database(tmp_path / "article_finder.db")
    result.add_paper({"paper_id": "p1", "title": "Paper"})
    return result


def test_database_rejects_readmission_after_rejection(db: Database) -> None:
    assert db.update_paper_status("p1", "rejected") is True
    with pytest.raises(ContractFSMViolation):
        db.update_paper_status("p1", "queued_for_eater")
    assert db.get_paper("p1")["status"] == "rejected"

    with pytest.raises(ContractFSMViolation):
        db.add_paper(
            {"paper_id": "p1", "title": "Paper", "status": "queued_for_eater"}
        )
    assert db.get_paper("p1")["status"] == "rejected"


def test_database_rejects_triage_decision_as_status(db: Database) -> None:
    with pytest.raises(ContractFSMViolation):
        db.update_paper_status("p1", "send_to_eater")
    assert db.get_paper("p1")["status"] == "candidate"


def test_set_ae_job_requires_existing_bundle_directory(db: Database, tmp_path: Path) -> None:
    missing = tmp_path / "missing-bundle"
    with pytest.raises(ContractFSMViolation):
        db.set_ae_job("p1", missing)
    assert db.get_paper("p1")["ae_status"] is None

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    assert db.set_ae_job("p1", bundle) is True
    paper = db.get_paper("p1")
    assert paper["ae_status"] == "pending"
    assert paper["ae_job_path"] == str(bundle.resolve())


def test_add_paper_cannot_manufacture_pending_without_job(db: Database) -> None:
    with pytest.raises(ContractFSMViolation):
        db.add_paper(
            {"paper_id": "p1", "title": "Paper", "ae_status": "pending"}
        )
    assert db.get_paper("p1")["ae_status"] is None
