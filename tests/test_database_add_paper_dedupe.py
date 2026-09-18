from __future__ import annotations

import sqlite3
from pathlib import Path

import core.database as database_module
from core.database import Database


def test_add_paper_materializes_ae_corpus_dedupe(monkeypatch, tmp_path: Path) -> None:
    def _stub_build_fields(paper, *, deduped_at):
        assert paper["title"] == "Known paper"
        return {
            "ae_corpus_match_status": "matched",
            "ae_corpus_match_basis": "exact_title",
            "ae_corpus_match_paper_id": "PDF-0009",
            "ae_corpus_match_confidence": 0.95,
            "ae_corpus_match_candidates_json": '["PDF-0009"]',
            "ae_corpus_deduped_at": deduped_at,
        }

    monkeypatch.setattr(database_module, "build_paper_dedupe_fields", _stub_build_fields)

    db_path = tmp_path / "article_finder.db"
    db = Database(db_path)
    paper_id = db.add_paper(
        {
            "doi": "10.1234/test",
            "title": "Known paper",
            "authors": ["A. Author"],
            "status": "candidate",
        }
    )

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    row = con.execute(
        """
        SELECT paper_id, ae_corpus_match_status, ae_corpus_match_basis,
               ae_corpus_match_paper_id, ae_corpus_match_confidence,
               ae_corpus_match_candidates_json, ae_corpus_deduped_at
        FROM papers
        WHERE paper_id = ?
        """,
        (paper_id,),
    ).fetchone()
    con.close()

    assert row["paper_id"] == "doi:10.1234/test"
    assert row["ae_corpus_match_status"] == "matched"
    assert row["ae_corpus_match_basis"] == "exact_title"
    assert row["ae_corpus_match_paper_id"] == "PDF-0009"
    assert row["ae_corpus_match_confidence"] == 0.95
    assert row["ae_corpus_match_candidates_json"] == '["PDF-0009"]'
    assert row["ae_corpus_deduped_at"]


def test_sparse_readd_preserves_unspecified_paper_fields(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        database_module,
        "build_paper_dedupe_fields",
        lambda _paper, *, deduped_at: {
            "ae_corpus_match_status": "unmatched",
            "ae_corpus_match_candidates_json": "[]",
            "ae_corpus_deduped_at": deduped_at,
        },
    )
    db = Database(tmp_path / "article_finder.db")
    original = {
        "paper_id": "paper-1",
        "title": "Complete record",
        "abstract": "Evidence-bearing abstract",
        "venue": "Environment and Behavior",
        "pdf_path": "/corpus/paper-1.pdf",
        "status": "candidate",
        "triage_decision": "review",
    }
    sparse_update = {
        "paper_id": "paper-1",
        "title": "Complete record",
        "status": "rejected",
        "triage_decision": "reject",
    }

    db.add_paper(dict(original))
    db.add_paper(dict(sparse_update))
    first = db.get_paper("paper-1")
    db.add_paper(dict(sparse_update))
    second = db.get_paper("paper-1")

    assert first is not None
    assert second is not None
    assert first["abstract"] == original["abstract"]
    assert first["venue"] == original["venue"]
    assert first["pdf_path"] == original["pdf_path"]
    assert first["status"] == "rejected"
    assert first["triage_decision"] == "reject"
    assert second["abstract"] == first["abstract"]
    assert second["venue"] == first["venue"]
    assert second["pdf_path"] == first["pdf_path"]
    assert second["status"] == first["status"]
    assert second["triage_decision"] == first["triage_decision"]
