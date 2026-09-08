from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from topic_admission.artifacts import RawArtifactStore
from topic_admission.collectors.openalex import OpenAlexCollector, _default_transport
from topic_admission.identity import resolve_identity, valid_doi
from topic_admission.models import CandidateIdentity, CollectorRequirement, CollectorResult, EvidenceItem, RunState
from topic_admission.orchestrator import AdmissionOrchestrator
from topic_admission.store import AdmissionStore
from topic_admission.verification import monitor_snapshot, verify_run


def openalex_record() -> dict:
    topic = {"id": "https://openalex.org/T100", "display_name": "Chemical bonding", "score": 0.998,
             "domain": {"id": "https://openalex.org/domains/3", "display_name": "Physical Sciences"},
             "field": {"id": "https://openalex.org/fields/16", "display_name": "Chemistry"},
             "subfield": {"id": "https://openalex.org/subfields/1604", "display_name": "Physical Chemistry"}}
    return {"id": "https://openalex.org/W123", "doi": "https://doi.org/10.1021/ja02261a002",
            "title": "The Atom and the Molecule", "publication_year": 1916, "type": "article",
            "authorships": [{"author": {"display_name": "Gilbert N. Lewis"}}],
            "primary_topic": topic, "topics": [], "updated_date": "2026-08-01T00:00:00"}


def transport_for(record: dict):
    body = json.dumps(record, sort_keys=True).encode()
    return lambda url, headers, timeout: (200, {"content-type": "application/json"}, body)


def full_decision(paper, evidence):
    return {"paper_id": paper.paper_id, "intake_decision": "accept_candidate",
            "routing_target": "article_eater", "domain_relevance": "on_domain",
            "article_type": "journal_article", "confidence": 0.9, "needs_manual_review": False,
            "reasons": ["fixture"], "primary_topic": "chemistry", "primary_bundle_id": "B-1",
            "topic_candidates": ["chemistry"], "matched_question_ids": ["Q-1"], "edge_case_kind": "",
            "novelty_signal": 0.0, "topic_expansion_candidate": False, "new_topic_candidate": False,
            "proposed_topic_label": "", "adjacent_topics": [], "facts": [{"fixture": True}],
            "corpus_role": "off_topic", "bridge": {}, "contradictions": [],
            "evidence_refs": [item["collector"] for item in evidence], "constitution_version": "fixture-v1"}


def candidate() -> CandidateIdentity:
    return CandidateIdentity("P-1", "The Atom and the Molecule", doi="10.1021/ja02261a002",
                             authors=("Gilbert N. Lewis",), year=1916)


def verified_fixture(tmp_path: Path) -> AdmissionStore:
    store = AdmissionStore(tmp_path / "admission.db")
    collector = OpenAlexCollector(RawArtifactStore(tmp_path / "raw"), transport=transport_for(openalex_record()))
    assert AdmissionOrchestrator(store, [collector], full_decision).run("run", candidate())["status"] == "verified"
    return store


@pytest.mark.parametrize("mutation,expected", [
    ("DELETE FROM identity_resolution", "identity-resolution set mismatch"),
    ("DELETE FROM raw_artifact", "raw artifact registration missing"),
    ("DELETE FROM state_transition", "missing state transition ledger"),
])
def test_deleting_required_integrity_rows_fails_closed(tmp_path: Path, mutation: str, expected: str) -> None:
    store = verified_fixture(tmp_path)
    with store.connect() as conn:
        conn.execute(mutation)
    assert any(expected in finding for finding in verify_run(store, "run"))


def test_identity_hard_conflicts_and_malformed_year_never_resolve() -> None:
    base = candidate()
    wrong_author = {"id": "W", "doi": base.doi, "title": base.title, "authors": ["Marie Curie"], "year": 1916}
    wrong_year = {"id": "W", "doi": base.doi, "title": base.title, "authors": ["Gilbert N. Lewis"], "year": 1999}
    malformed_year = dict(wrong_year, year="online first")
    assert resolve_identity(base, wrong_author).decision == "conflict"
    assert resolve_identity(base, wrong_year).decision == "conflict"
    assert resolve_identity(base, malformed_year).decision == "conflict"
    comma = dict(wrong_author, authors=["Lewis, Gilbert N."])
    assert resolve_identity(base, comma).author_similarity == 1.0


@pytest.mark.parametrize("doi", [
    "10.1000/abc?api_key=SECRET", "10.1000/abc#fragment", "10.1000/<bad>",
    "10.1000/abc\\def", "10.1000/abc%0Aevil",
])
def test_hostile_doi_forms_are_rejected(doi: str) -> None:
    assert not valid_doi(doi)
    assert valid_doi("10.1002/(sici)1099-0844(199912)17:4<290::aid-cbf849>3.0.co;2-p") is False
    assert valid_doi("10.5555/example(test)")


def test_secret_bearing_errors_and_echoes_are_not_persisted(tmp_path: Path) -> None:
    secret = "SENTINEL_BEARER_8675309"
    def raising(url, headers, timeout):
        raise OSError(repr(headers))
    store = AdmissionStore(tmp_path / "errors.db")
    collector = OpenAlexCollector(RawArtifactStore(tmp_path / "raw-errors"), api_key=secret, transport=raising)
    AdmissionOrchestrator(store, [collector], full_decision).run("error", candidate())
    assert secret.encode() not in (tmp_path / "errors.db").read_bytes()

    echoed = json.dumps({"authorization": f"Bearer {secret}"}).encode()
    store2 = AdmissionStore(tmp_path / "echo.db")
    collector2 = OpenAlexCollector(RawArtifactStore(tmp_path / "raw-echo"), api_key=secret,
                                   transport=lambda u, h, t: (200, {"content-type": "application/json"}, echoed))
    AdmissionOrchestrator(store2, [collector2], full_decision).run("echo", candidate())
    assert secret.encode() not in (tmp_path / "echo.db").read_bytes()
    assert not list((tmp_path / "raw-echo").rglob("*.json"))


@pytest.mark.parametrize("header", ["etag", "content-type", "retry-after"])
def test_secret_echoed_in_allowlisted_header_is_not_persisted(tmp_path: Path, header: str) -> None:
    secret = "HEADER_SENTINEL_8675309"
    body = json.dumps(openalex_record()).encode()
    value = f"Bearer {secret}" if header != "content-type" else f"application/json; credential={secret}"
    collector = OpenAlexCollector(
        RawArtifactStore(tmp_path / "raw"), api_key=secret,
        transport=lambda u, h, t: (200, {header: value}, body),
    )
    store = AdmissionStore(tmp_path / "header.db")
    assert AdmissionOrchestrator(store, [collector], full_decision).run("header", candidate())["status"] == "hold"
    assert secret.encode() not in (tmp_path / "header.db").read_bytes()


def test_extreme_topic_score_and_conflicting_duplicate_hold_without_crash(tmp_path: Path) -> None:
    for suffix, mutate in (
        ("huge", lambda r: r["primary_topic"].update(score=10**400)),
        ("duplicate", lambda r: r.update(topics=[dict(r["primary_topic"], score=0.1)])),
    ):
        record = openalex_record()
        mutate(record)
        store = AdmissionStore(tmp_path / f"{suffix}.db")
        collector = OpenAlexCollector(RawArtifactStore(tmp_path / f"raw-{suffix}"), transport=transport_for(record))
        result = AdmissionOrchestrator(store, [collector], full_decision).run(suffix, candidate())
        assert result["status"] == "hold"


def test_raw_artifact_store_rejects_symlink_digest_target(tmp_path: Path) -> None:
    root = tmp_path / "raw"
    body = b"metadata"
    digest = hashlib.sha256(body).hexdigest()
    directory = root / digest[:2]
    directory.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.write_bytes(b"do not overwrite")
    os.symlink(outside, directory / f"{digest}.json")
    with pytest.raises(ValueError, match="symlink"):
        RawArtifactStore(root).put(body, media_type="application/json", access_class="public_metadata")
    assert outside.read_bytes() == b"do not overwrite"


class SlowCollector(OpenAlexCollector):
    def plan(self, paper):
        base = super().plan(paper)
        return CollectorRequirement(base.collector, base.collector_version, True, "applicable", "deadline test",
                                    request_sha256=base.request_sha256, timeout_seconds=0.01, max_attempts=1)

    def collect(self, paper):
        time.sleep(2)
        return super().collect(paper)


def test_declared_collector_deadline_is_enforced(tmp_path: Path) -> None:
    store = AdmissionStore(tmp_path / "deadline.db")
    collector = SlowCollector(RawArtifactStore(tmp_path / "raw-deadline"), transport=transport_for(openalex_record()))
    started = time.monotonic()
    result = AdmissionOrchestrator(store, [collector], full_decision).run("deadline", candidate())
    assert time.monotonic() - started < 1.5
    assert result["status"] == "hold"
    assert "deadline_exceeded" in result["failures"][0]


def test_monitor_detects_corrupt_raw_bytes(tmp_path: Path) -> None:
    store = verified_fixture(tmp_path)
    with store.connect() as conn:
        locator = conn.execute("SELECT locator FROM raw_artifact").fetchone()[0]
    Path(locator).write_bytes(b"tampered")
    snapshot = monitor_snapshot(store)
    assert snapshot["status"] == "attention"
    assert snapshot["corrupt_raw_artifacts"] == 1


@pytest.mark.parametrize("table,metric", [
    ("identity_resolution", "missing_identity_resolutions"),
    ("raw_artifact", "missing_raw_registrations"),
])
def test_monitor_detects_deleted_provenance_rows(tmp_path: Path, table: str, metric: str) -> None:
    store = verified_fixture(tmp_path)
    with store.connect() as conn:
        conn.execute(f"DELETE FROM {table}")
    snapshot = monitor_snapshot(store)
    assert snapshot["status"] == "attention"
    assert snapshot[metric] == 1


@pytest.mark.parametrize("table", ["evidence_record", "admission_decision", "state_transition"])
def test_monitor_full_integrity_audit_detects_verified_structure_deletion(tmp_path: Path, table: str) -> None:
    store = verified_fixture(tmp_path)
    with store.connect() as conn:
        conn.execute(f"DELETE FROM {table}")
    snapshot = monitor_snapshot(store)
    assert snapshot["status"] == "attention"
    assert snapshot["corrupt_verified_runs"] == 1


def test_monitor_fails_closed_on_malformed_observation_json(tmp_path: Path) -> None:
    store = verified_fixture(tmp_path)
    with store.connect() as conn:
        conn.execute("UPDATE collector_observation SET result_json='not-json'")
    snapshot = monitor_snapshot(store)
    assert snapshot["status"] == "attention"
    assert snapshot["malformed_observations"] == 1


def test_verifier_recomputes_request_url_hash_and_endpoint_policy(tmp_path: Path) -> None:
    store = verified_fixture(tmp_path)
    with store.connect() as conn:
        row = conn.execute("SELECT result_json FROM collector_observation WHERE run_id='run'").fetchone()
        payload = json.loads(row[0])
        payload["request_url"] = "https://evil.example/elsewhere"
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        conn.execute("UPDATE collector_observation SET result_json=?, result_sha256=? WHERE run_id='run'",
                     (canonical, hashlib.sha256(canonical.encode()).hexdigest()))
    findings = verify_run(store, "run")
    assert any("URL/hash mismatch" in finding for finding in findings)
    assert "OpenAlex request endpoint policy mismatch" in findings


@pytest.mark.parametrize("mutation", [
    lambda r: r["primary_topic"].update(display_name=""),
    lambda r: r["primary_topic"].update(id="banana"),
    lambda r: r.update(topics=[dict(r["primary_topic"], field={"id": "https://openalex.org/fields/17", "display_name": "Psychology"})]),
])
def test_malformed_or_contradictory_openalex_topics_hold(tmp_path: Path, mutation) -> None:
    record = openalex_record()
    mutation(record)
    store = AdmissionStore(tmp_path / "taxonomy.db")
    collector = OpenAlexCollector(RawArtifactStore(tmp_path / "raw-taxonomy"), transport=transport_for(record))
    assert AdmissionOrchestrator(store, [collector], full_decision).run("taxonomy", candidate())["status"] == "hold"


def test_realistic_v1_admission_table_gains_heartbeat_and_accepts_named_insert(tmp_path: Path) -> None:
    path = tmp_path / "v1.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE schema_version(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
    con.execute("INSERT INTO schema_version VALUES (1, 'earlier')")
    con.execute("CREATE TABLE admission_run(run_id TEXT PRIMARY KEY,paper_id TEXT NOT NULL,state TEXT NOT NULL,"
                "candidate_json TEXT NOT NULL,candidate_sha256 TEXT NOT NULL,contract_version TEXT NOT NULL,"
                "created_at TEXT NOT NULL,updated_at TEXT NOT NULL,error TEXT)")
    con.commit(); con.close()
    store = AdmissionStore(path)
    store.create_run("new", CandidateIdentity("P", "Title"), "v1")
    with store.connect() as conn:
        assert "heartbeat_at" in {row[1] for row in conn.execute("PRAGMA table_info(admission_run)")}


@pytest.mark.parametrize("kind", ["mismatch", "exception", "bad-timeout"])
def test_malformed_or_failing_planner_terminates_run_and_alerts(tmp_path: Path, kind: str) -> None:
    class BadPlanner:
        name = "actual"
        version = "v1"
        def plan(self, paper):
            if kind == "exception":
                raise RuntimeError("secret detail")
            return CollectorRequirement("different" if kind == "mismatch" else self.name, self.version,
                                        True, "applicable", "bad",
                                        timeout_seconds=float("nan") if kind == "bad-timeout" else 1)
        def collect(self, paper):
            raise AssertionError
    store = AdmissionStore(tmp_path / f"{kind}.db")
    result = AdmissionOrchestrator(store, [BadPlanner()], full_decision).run(kind, candidate())
    assert result["status"] == "failed"
    assert store.state(kind).value == "failed"
    assert monitor_snapshot(store)["status"] == "attention"


def test_verifier_binds_candidate_initial_transition_and_raw_metadata(tmp_path: Path) -> None:
    for suffix, mutation, expected in (
        ("candidate", "UPDATE admission_run SET candidate_json=json_set(candidate_json,'$.paper_id','OTHER'), "
                      "candidate_sha256=''", "candidate paper_id disagrees"),
        ("initial", "UPDATE state_transition SET actor='', reason='' WHERE transition_id=(SELECT MIN(transition_id) FROM state_transition)",
         "initial state transition lacks"),
        ("raw", "UPDATE raw_artifact SET access_class='untrusted'", "raw artifact access class mismatch"),
    ):
        store = verified_fixture(tmp_path / suffix)
        with store.connect() as conn:
            if suffix == "candidate":
                row = conn.execute("SELECT candidate_json FROM admission_run WHERE run_id='run'").fetchone()
                payload = json.loads(row[0]); payload["paper_id"] = "OTHER"
                canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                conn.execute("UPDATE admission_run SET candidate_json=?, candidate_sha256=? WHERE run_id='run'",
                             (canonical, hashlib.sha256(canonical.encode()).hexdigest()))
            else:
                conn.execute(mutation)
        assert any(expected in finding for finding in verify_run(store, "run"))


def test_default_transport_does_not_follow_bearer_redirect() -> None:
    received = {"authorization": None}
    class Sink(BaseHTTPRequestHandler):
        def do_GET(self):
            received["authorization"] = self.headers.get("Authorization")
            self.send_response(200); self.end_headers(); self.wfile.write(b"{}")
        def log_message(self, *args): pass
    sink = HTTPServer(("127.0.0.1", 0), Sink)
    class Redirect(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{sink.server_port}/sink")
            self.end_headers()
        def log_message(self, *args): pass
    redirect = HTTPServer(("127.0.0.1", 0), Redirect)
    threads = [threading.Thread(target=server.serve_forever, daemon=True) for server in (sink, redirect)]
    for thread in threads: thread.start()
    try:
        status, _, _ = _default_transport(f"http://127.0.0.1:{redirect.server_port}/start",
                                          {"Authorization": "Bearer SENTINEL"}, 2)
        assert status == 302
        assert received["authorization"] is None
    finally:
        redirect.shutdown(); sink.shutdown()


def test_every_store_write_surface_rejects_credential_markers(tmp_path: Path) -> None:
    path = tmp_path / "guard.db"
    store = AdmissionStore(path)
    sentinel = "SENTINEL_UNIVERSAL_8675309"
    marker = f"api_key={sentinel}"
    with pytest.raises(ValueError, match="credential-like"):
        store.create_run("bad-create", CandidateIdentity("P", "Title", metadata={"note": marker}), "v1")
    store.create_run("run", CandidateIdentity("P", "Title"), "v1")
    with pytest.raises(ValueError, match="credential-like"):
        store.save_plan("run", [CollectorRequirement("c", "v1", True, "not_applicable", marker)])
    with pytest.raises(ValueError, match="credential-like"):
        store.transition("run", RunState.FAILED, marker, "actor")
    with pytest.raises(ValueError, match="credential-like"):
        store.start_attempt("run", marker, "v1")
    store.start_attempt("run", "c", "v1")
    with pytest.raises(ValueError, match="credential-like"):
        store.fail_attempt("run", "c", marker)
    result = CollectorResult("c", "v1", 1.0, "ok",
                             evidence=(EvidenceItem("s", "l", "v", "fixture"),), warnings=(marker,),
                             identity_assertion={"decision": "resolved"})
    with pytest.raises(ValueError, match="credential-like"):
        store.finish_attempt("run", result)
    with pytest.raises(ValueError, match="credential-like"):
        store.save_decision("run", {"note": marker}, "a", "v1")
    with pytest.raises(ValueError, match="credential-like"):
        store.save_verification("run", "v", "v1", "fail", [marker])
    for db_file in tmp_path.glob("guard.db*"):
        assert sentinel.encode() not in db_file.read_bytes()
