from __future__ import annotations

import json
from pathlib import Path

from topic_admission.artifacts import RawArtifactStore
from topic_admission.collectors.openalex import OpenAlexCollector
from topic_admission.identity import normalize_doi, resolve_identity, token_similarity, valid_doi
from topic_admission.models import CandidateIdentity, RunState
from topic_admission.orchestrator import AdmissionOrchestrator
from topic_admission.store import AdmissionStore
from topic_admission.verification import monitor_snapshot, verify_run


def openalex_record() -> dict:
    return {
        "id": "https://openalex.org/W123",
        "doi": "https://doi.org/10.1021/ja02261a002",
        "title": "The Atom and the Molecule",
        "publication_year": 1916,
        "type": "article",
        "authorships": [{"author": {"display_name": "Gilbert N. Lewis"}}],
        "primary_topic": {
            "id": "https://openalex.org/T100",
            "display_name": "Chemical bonding and molecular structure",
            "score": 0.998,
            "domain": {"id": "https://openalex.org/domains/3", "display_name": "Physical Sciences"},
            "field": {"id": "https://openalex.org/fields/16", "display_name": "Chemistry"},
            "subfield": {"id": "https://openalex.org/subfields/1604", "display_name": "Physical Chemistry"},
        },
        "topics": [],
        "keywords": [],
        "cited_by_count": 1000,
        "referenced_works": [],
        "ids": {"doi": "https://doi.org/10.1021/ja02261a002"},
        "updated_date": "2026-08-01T00:00:00",
    }


def transport_for(record: dict, *, status: int = 200, capture: dict | None = None):
    body = json.dumps(record, sort_keys=True).encode()
    def transport(url, headers, timeout):
        if capture is not None:
            capture.update(url=url, headers=headers, timeout=timeout)
        return status, {"content-type": "application/json"}, body
    return transport


def full_decision(candidate, evidence):
    return {
        "paper_id": candidate.paper_id, "intake_decision": "accept_candidate",
        "routing_target": "article_eater", "domain_relevance": "on_domain",
        "article_type": "journal_article", "confidence": 0.9,
        "needs_manual_review": False, "reasons": ["fixture"],
        "primary_topic": "chemistry", "primary_bundle_id": "B-1",
        "topic_candidates": ["chemistry"], "matched_question_ids": ["Q-1"],
        "edge_case_kind": "", "novelty_signal": 0.0,
        "topic_expansion_candidate": False, "new_topic_candidate": False,
        "proposed_topic_label": "", "adjacent_topics": [], "facts": [{"fixture": True}],
        "corpus_role": "off_topic", "bridge": {}, "contradictions": [],
        "evidence_refs": [item["collector"] for item in evidence],
        "constitution_version": "fixture-v1",
    }


def test_doi_and_text_normalization() -> None:
    assert normalize_doi("https://doi.org/10.1021/JA02261A002.") == "10.1021/ja02261a002"
    assert valid_doi("10.1021/ja02261a002")
    assert not valid_doi("not-a-doi")
    assert token_similarity("The Atom & Molecule", "The molecule and the atom") > 0.8


def test_identity_resolution_detects_cross_domain_title_conflict() -> None:
    candidate = CandidateIdentity("PDF-0180", "Environmental psychology and human wellbeing",
                                  doi="10.1021/ja02261a002", year=1916)
    observed = {"id": "W123", "doi": "10.1021/ja02261a002",
                "title": "The Atom and the Molecule", "authors": ["Gilbert Lewis"], "year": 1916}
    result = resolve_identity(candidate, observed)
    assert result.decision == "conflict"
    assert "title_mismatch" in result.conflicts


def test_openalex_collector_records_raw_provenance_and_hierarchy(tmp_path: Path) -> None:
    capture = {}
    collector = OpenAlexCollector(
        RawArtifactStore(tmp_path / "raw"), api_key="SECRET", email="test@example.org",
        transport=transport_for(openalex_record(), capture=capture),
    )
    candidate = CandidateIdentity("PDF-0180", "The Atom and the Molecule",
                                  doi="10.1021/ja02261a002", authors=("Gilbert N. Lewis",), year=1916)
    result = collector.collect(candidate)
    assert result.status == "ok"
    assert result.identity_assertion["decision"] == "resolved"
    assert result.evidence[0].value["hierarchy"]["field"]["name"] == "Chemistry"
    assert Path(result.raw_response_locator).read_bytes() == json.dumps(openalex_record(), sort_keys=True).encode()
    assert "SECRET" not in capture["url"]
    assert capture["headers"]["Authorization"] == "Bearer SECRET"
    assert "api_key=" not in result.request_url


def test_orchestrator_persists_plan_observation_identity_and_raw_artifact(tmp_path: Path) -> None:
    store = AdmissionStore(tmp_path / "admission.db")
    collector = OpenAlexCollector(RawArtifactStore(tmp_path / "raw"), transport=transport_for(openalex_record()))
    candidate = CandidateIdentity("PDF-0180", "The Atom and the Molecule",
                                  doi="10.1021/ja02261a002", authors=("Gilbert N. Lewis",), year=1916)
    result = AdmissionOrchestrator(store, [collector], full_decision).run("run-live-fixture", candidate)
    assert result["status"] == "verified"
    assert verify_run(store, "run-live-fixture") == []
    with store.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM collector_plan").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM collector_observation").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM identity_resolution").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM raw_artifact").fetchone()[0] == 1


def test_bad_candidate_identity_holds_before_adjudication(tmp_path: Path) -> None:
    store = AdmissionStore(tmp_path / "admission.db")
    collector = OpenAlexCollector(RawArtifactStore(tmp_path / "raw"), transport=transport_for(openalex_record()))
    candidate = CandidateIdentity("PDF-0180", "California environmental psychology",
                                  doi="10.1021/ja02261a002", year=1916)
    called = False
    def adjudicator(candidate, evidence):
        nonlocal called
        called = True
        return full_decision(candidate, evidence)
    result = AdmissionOrchestrator(store, [collector], adjudicator).run("run-conflict", candidate)
    assert result["status"] == "hold"
    assert not called
    assert store.state("run-conflict") == RunState.HOLD


def test_missing_or_invalid_doi_is_planned_then_held_without_network(tmp_path: Path) -> None:
    called = False
    def transport(url, headers, timeout):
        nonlocal called
        called = True
        raise AssertionError("network must not be called")
    store = AdmissionStore(tmp_path / "admission.db")
    collector = OpenAlexCollector(RawArtifactStore(tmp_path / "raw"), transport=transport)
    result = AdmissionOrchestrator(store, [collector], full_decision).run(
        "run-no-doi", CandidateIdentity("P-1", "A plausible title", doi="bad")
    )
    assert result["status"] == "hold"
    assert not called
    with store.connect() as conn:
        plan = json.loads(conn.execute("SELECT plan_json FROM collector_plan").fetchone()[0])
    assert plan["applicability"] == "not_applicable"


def test_not_found_and_malformed_json_are_provenance_bearing_holds(tmp_path: Path) -> None:
    candidate = CandidateIdentity("P-1", "A title", doi="10.1234/missing")
    for suffix, transport in (
        ("404", lambda url, headers, timeout: (404, {}, b'{"error":"not found"}')),
        ("bad-json", lambda url, headers, timeout: (200, {}, b"not json")),
    ):
        store = AdmissionStore(tmp_path / f"{suffix}.db")
        collector = OpenAlexCollector(RawArtifactStore(tmp_path / f"raw-{suffix}"), transport=transport)
        result = AdmissionOrchestrator(store, [collector], full_decision).run(f"run-{suffix}", candidate)
        assert result["status"] == "hold"
        with store.connect() as conn:
            assert conn.execute("SELECT COUNT(*) FROM collector_observation").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM raw_artifact").fetchone()[0] == 1


def test_identity_assertion_conflict_blocks_even_with_high_scalar(tmp_path: Path) -> None:
    class ContradictoryCollector:
        name = "contradictory"
        version = "v1"
        def collect(self, candidate):
            from topic_admission.models import CollectorResult, EvidenceItem
            return CollectorResult(
                source=self.name, source_version=self.version, identity_match=1.0, status="ok",
                evidence=(EvidenceItem("test", "field", "Chemistry", "fixture"),),
                identity_assertion={"decision": "conflict", "candidate_paper_id": candidate.paper_id},
            )
    called = False
    def adjudicator(candidate, evidence):
        nonlocal called
        called = True
        return full_decision(candidate, evidence)
    store = AdmissionStore(tmp_path / "admission.db")
    result = AdmissionOrchestrator(store, [ContradictoryCollector()], adjudicator).run(
        "run-contradiction", CandidateIdentity("P-1", "A title")
    )
    assert result["status"] == "hold"
    assert not called


def test_unknown_collector_status_is_failed_closed(tmp_path: Path) -> None:
    class UnknownStatusCollector:
        name = "unknown"
        version = "v1"
        def collect(self, candidate):
            from topic_admission.models import CollectorResult, EvidenceItem
            return CollectorResult(self.name, self.version, 1.0, "banana",
                                   evidence=(EvidenceItem("test", "field", "X", "fixture"),))
    store = AdmissionStore(tmp_path / "admission.db")
    result = AdmissionOrchestrator(store, [UnknownStatusCollector()], full_decision).run(
        "run-status", CandidateIdentity("P-1", "A title")
    )
    assert result["status"] == "hold"
    assert "unknown collector status" in result["failures"][0]


def test_schema_v1_upgrades_additively_and_future_schema_refuses(tmp_path: Path) -> None:
    import sqlite3
    old_path = tmp_path / "old.db"
    con = sqlite3.connect(old_path)
    con.execute("CREATE TABLE schema_version(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
    con.execute("INSERT INTO schema_version VALUES (1, 'earlier')")
    con.commit()
    con.close()
    AdmissionStore(old_path)
    con = sqlite3.connect(old_path)
    assert con.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == 2
    assert con.execute("SELECT 1 FROM sqlite_master WHERE name='collector_plan'").fetchone()
    con.close()

    future_path = tmp_path / "future.db"
    con = sqlite3.connect(future_path)
    con.execute("CREATE TABLE schema_version(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
    con.execute("INSERT INTO schema_version VALUES (999, 'future')")
    con.commit()
    con.close()
    import pytest
    with pytest.raises(RuntimeError, match="newer than supported"):
        AdmissionStore(future_path)


def test_monitor_detects_missing_raw_artifact(tmp_path: Path) -> None:
    store = AdmissionStore(tmp_path / "admission.db")
    collector = OpenAlexCollector(RawArtifactStore(tmp_path / "raw"), transport=transport_for(openalex_record()))
    candidate = CandidateIdentity("PDF-0180", "The Atom and the Molecule",
                                  doi="10.1021/ja02261a002", authors=("Gilbert Lewis",), year=1916)
    assert AdmissionOrchestrator(store, [collector], full_decision).run("run-monitor", candidate)["status"] == "verified"
    assert monitor_snapshot(store)["status"] == "ok"
    with store.connect() as conn:
        locator = conn.execute("SELECT locator FROM raw_artifact").fetchone()[0]
    Path(locator).unlink()
    snapshot = monitor_snapshot(store)
    assert snapshot["status"] == "attention"
    assert snapshot["missing_raw_artifacts"] == 1
