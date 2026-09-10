from __future__ import annotations

import sqlite3
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from topic_admission.models import CandidateIdentity, CollectorResult, EvidenceItem, RunState
from topic_admission.orchestrator import AdmissionOrchestrator
from topic_admission.store import AdmissionStore
from topic_admission.verification import monitor_snapshot, verify_run


@dataclass
class StubCollector:
    name: str
    identity_match: float = 0.99
    fail: bool = False
    version: str = "test-v1"

    def collect(self, candidate: CandidateIdentity) -> CollectorResult:
        if self.fail:
            raise RuntimeError("simulated source failure")
        return CollectorResult(
            source=self.name,
            source_version=self.version,
            identity_match=self.identity_match,
            status="ok",
            evidence=(EvidenceItem(
                scheme="test_taxonomy", label="field", value="Psychology",
                assignment_method="fixture", source_record_id=candidate.paper_id,
            ),),
            identity_assertion={
                "decision": "resolved", "score": self.identity_match,
                "candidate_paper_id": candidate.paper_id, "doi_match": True,
                "conflicts": [],
            },
        )


def adjudicate(candidate, evidence):
    return {
        "paper_id": candidate.paper_id, "intake_decision": "accept_candidate",
        "routing_target": "article_eater", "domain_relevance": "on_domain",
        "article_type": "journal_article", "confidence": 0.9,
        "needs_manual_review": False, "reasons": ["fixture"],
        "primary_topic": "spatial_memory", "primary_bundle_id": "B-1",
        "topic_candidates": ["spatial_memory"], "matched_question_ids": ["Q-1"],
        "edge_case_kind": "", "novelty_signal": 0.0,
        "topic_expansion_candidate": False, "new_topic_candidate": False,
        "proposed_topic_label": "", "adjacent_topics": [], "facts": [{"fixture": True}],
        "corpus_role": "core_neuroscience_mechanism",
        "bridge": {"question_id": "Q-1", "mechanism": "spatial memory"},
        "contradictions": [], "evidence_refs": [item["collector"] for item in evidence],
        "constitution_version": "fixture-v1",
    }


def test_success_is_persisted_and_independently_verified(tmp_path: Path) -> None:
    store = AdmissionStore(tmp_path / "admission.db")
    orchestrator = AdmissionOrchestrator(
        store, [StubCollector("pubmed"), StubCollector("openalex")], adjudicate,
        adjudicator_version="test-shared-v1",
    )
    result = orchestrator.run("run-1", CandidateIdentity("P-1", "Spatial memory", doi="10.1/x"))
    assert result["status"] == "verified"
    assert store.state("run-1") == RunState.VERIFIED
    assert verify_run(store, "run-1") == []
    assert monitor_snapshot(store)["status"] == "ok"


def test_identity_disagreement_holds_before_adjudication(tmp_path: Path) -> None:
    store = AdmissionStore(tmp_path / "admission.db")
    result = AdmissionOrchestrator(
        store, [StubCollector("openalex", identity_match=0.2)], adjudicate
    ).run("run-2", CandidateIdentity("P-2", "A title"))
    assert result["status"] == "hold"
    assert store.state("run-2") == RunState.HOLD
    with store.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM admission_decision").fetchone()[0] == 0


def test_collector_failure_is_visible_to_monitor(tmp_path: Path) -> None:
    store = AdmissionStore(tmp_path / "admission.db")
    result = AdmissionOrchestrator(store, [StubCollector("pubmed", fail=True)], adjudicate).run(
        "run-3", CandidateIdentity("P-3", "A title")
    )
    assert result["status"] == "hold"
    snapshot = monitor_snapshot(store)
    assert snapshot["status"] == "attention"
    assert snapshot["failed_collector_attempts"] == 1


def test_hash_tampering_is_detected(tmp_path: Path) -> None:
    store = AdmissionStore(tmp_path / "admission.db")
    AdmissionOrchestrator(store, [StubCollector("pubmed")], adjudicate).run(
        "run-4", CandidateIdentity("P-4", "A title")
    )
    con = sqlite3.connect(store.path)
    con.execute("UPDATE evidence_record SET evidence_json='{}' WHERE run_id='run-4'")
    con.commit()
    con.close()
    findings = verify_run(store, "run-4")
    assert any("evidence hash mismatch" in finding for finding in findings)
    assert "decision evidence-set hash mismatch" in findings


def test_illegal_transition_is_rejected(tmp_path: Path) -> None:
    store = AdmissionStore(tmp_path / "admission.db")
    store.create_run("run-5", CandidateIdentity("P-5", "A title"), "v1")
    with pytest.raises(ValueError, match="illegal admission transition"):
        store.transition("run-5", RunState.VERIFIED, "skip", "test")


def test_non_ok_collector_result_holds(tmp_path: Path) -> None:
    store = AdmissionStore(tmp_path / "admission.db")
    collector = StubCollector("pubmed")
    collector.collect = lambda candidate: CollectorResult(  # type: ignore[method-assign]
        source="pubmed", source_version="test-v1", identity_match=0.99, status="partial"
    )
    result = AdmissionOrchestrator(store, [collector], adjudicate).run(
        "run-6", CandidateIdentity("P-6", "A title")
    )
    assert result["status"] == "hold"
    assert "terminal status=partial" in result["failures"][0]


def test_verified_snapshot_binds_data_but_cannot_authorize_ae(tmp_path: Path) -> None:
    store = AdmissionStore(tmp_path / "admission.db")
    AdmissionOrchestrator(store, [StubCollector("pubmed")], adjudicate).run(
        "run-7", CandidateIdentity("P-7", "A title")
    )
    snapshot = store.verified_snapshot("run-7")
    assert snapshot["snapshot_version"] == "topic_admission_integrity_snapshot_v1"
    assert snapshot["article_eater_authorized"] is False
    assert "not_an_article_eater_authorization" in snapshot["purpose"]
    assert len(snapshot["candidate_sha256"]) == 64
    assert len(snapshot["evidence_set_sha256"]) == 64
    assert len(snapshot["decision_sha256"]) == 64


def test_cli_monitor_and_verify(tmp_path: Path) -> None:
    db_path = tmp_path / "admission.db"
    store = AdmissionStore(db_path)
    AdmissionOrchestrator(store, [StubCollector("pubmed")], adjudicate).run(
        "run-8", CandidateIdentity("P-8", "A title")
    )
    for command in (("monitor",), ("verify", "run-8"), ("snapshot", "run-8")):
        proc = subprocess.run(
            [sys.executable, "-m", "topic_admission.cli", "--db", str(db_path), *command],
            check=False, capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert json.loads(proc.stdout)


def test_receipt_reverifies_and_blocks_post_verification_tampering(tmp_path: Path) -> None:
    store = AdmissionStore(tmp_path / "admission.db")
    AdmissionOrchestrator(store, [StubCollector("pubmed")], adjudicate).run(
        "run-9", CandidateIdentity("P-9", "A title")
    )
    with store.connect() as conn:
        conn.execute("UPDATE admission_decision SET decision_json='{}' WHERE run_id='run-9'")
    with pytest.raises(ValueError, match="failed fresh verification"):
        store.verified_snapshot("run-9")


def test_incomplete_decision_cannot_verify_or_receive_receipt(tmp_path: Path) -> None:
    store = AdmissionStore(tmp_path / "admission.db")
    result = AdmissionOrchestrator(
        store, [StubCollector("pubmed")], lambda candidate, evidence: {"intake_decision": "accept_candidate"}
    ).run("run-10", CandidateIdentity("P-10", "A title"))
    assert result["status"] == "hold"
    with pytest.raises(ValueError):
        store.verified_snapshot("run-10")


def test_rejected_decision_snapshot_is_explicitly_non_authorizing(tmp_path: Path) -> None:
    store = AdmissionStore(tmp_path / "admission.db")
    def reject(candidate, evidence):
        payload = dict(adjudicate(candidate, evidence))
        payload.update(intake_decision="reject_clear_false_positive", routing_target="reject",
                       domain_relevance="clear_false_positive", corpus_role="off_topic")
        return payload
    result = AdmissionOrchestrator(store, [StubCollector("pubmed")], reject).run(
        "run-11", CandidateIdentity("P-11", "Chemistry")
    )
    assert result["status"] == "verified"
    snapshot = store.verified_snapshot("run-11")
    assert snapshot["article_eater_authorized"] is False
    assert snapshot["decision"]["intake_decision"] == "reject_clear_false_positive"


def test_adjudicator_exception_is_terminal(tmp_path: Path) -> None:
    store = AdmissionStore(tmp_path / "admission.db")
    def explode(candidate, evidence):
        raise RuntimeError("boom")
    result = AdmissionOrchestrator(store, [StubCollector("pubmed")], explode).run(
        "run-12", CandidateIdentity("P-12", "A title")
    )
    assert result["status"] == "failed"
    assert store.state("run-12") == RunState.FAILED


@pytest.mark.parametrize("identity_match", [float("nan"), float("inf"), -0.1, 1.1])
def test_invalid_identity_match_holds(tmp_path: Path, identity_match: float) -> None:
    store = AdmissionStore(tmp_path / "admission.db")
    result = AdmissionOrchestrator(
        store, [StubCollector("pubmed", identity_match=identity_match)], adjudicate
    ).run("run-bad-id", CandidateIdentity("P-X", "A title"))
    assert result["status"] == "hold"


def test_duplicate_collectors_are_rejected_before_run_creation(tmp_path: Path) -> None:
    store = AdmissionStore(tmp_path / "admission.db")
    with pytest.raises(ValueError, match="unique names"):
        AdmissionOrchestrator(
            store, [StubCollector("pubmed"), StubCollector("pubmed")], adjudicate
        ).run("run-dup", CandidateIdentity("P-X", "A title"))
    with store.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM admission_run").fetchone()[0] == 0


def test_empty_ok_evidence_and_version_mismatch_hold(tmp_path: Path) -> None:
    store = AdmissionStore(tmp_path / "admission.db")
    empty = StubCollector("pubmed")
    empty.collect = lambda candidate: CollectorResult(  # type: ignore[method-assign]
        source="pubmed", source_version="test-v1", identity_match=0.9, status="ok", evidence=()
    )
    assert AdmissionOrchestrator(store, [empty], adjudicate).run(
        "run-empty", CandidateIdentity("P-E", "A title")
    )["status"] == "hold"

    wrong_version = StubCollector("openalex")
    wrong_version.collect = lambda candidate: CollectorResult(  # type: ignore[method-assign]
        source="openalex", source_version="wrong", identity_match=0.9, status="ok",
        evidence=(EvidenceItem("test", "field", "Psychology", "fixture"),),
    )
    assert AdmissionOrchestrator(store, [wrong_version], adjudicate).run(
        "run-version", CandidateIdentity("P-V", "A title")
    )["status"] == "hold"


def test_out_of_range_evidence_confidence_blocks_verification(tmp_path: Path) -> None:
    store = AdmissionStore(tmp_path / "admission.db")
    bad = StubCollector("pubmed")
    bad.collect = lambda candidate: CollectorResult(  # type: ignore[method-assign]
        source="pubmed", source_version="test-v1", identity_match=0.9, status="ok",
        evidence=(EvidenceItem("test", "field", "Psychology", "fixture", confidence=8.5),),
        identity_assertion={"decision": "resolved", "score": 0.9,
                            "candidate_paper_id": candidate.paper_id, "doi_match": True,
                            "conflicts": []},
    )
    result = AdmissionOrchestrator(store, [bad], adjudicate).run(
        "run-confidence", CandidateIdentity("P-C", "A title")
    )
    assert result["status"] == "hold"
    assert any("evidence confidence out of range" in finding for finding in result["findings"])
