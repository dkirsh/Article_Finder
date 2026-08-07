from __future__ import annotations

import json

import pytest

import core.contract_fsm_runtime as runtime
from core.contract_fsm_runtime import ContractFSMViolation, enforce_transition


def test_paper_status_positive_trace() -> None:
    state = "candidate"
    for target in ("pending_scorer", "candidate", "downloaded", "queued_for_eater"):
        state = enforce_transition("paper_status", state, f"set:{target}")
    assert state == "queued_for_eater"


def test_rejected_paper_cannot_reenter_queue() -> None:
    state = enforce_transition("paper_status", "candidate", "set:rejected")
    with pytest.raises(ContractFSMViolation):
        enforce_transition("paper_status", state, "set:queued_for_eater")


def test_handoff_requires_existing_job_path_guard() -> None:
    with pytest.raises(ContractFSMViolation):
        enforce_transition(
            "ae_handoff",
            "unbuilt",
            "record_job",
            guards={"job_path_exists": False},
        )
    assert enforce_transition(
        "ae_handoff",
        "unbuilt",
        "record_job",
        guards={"job_path_exists": True},
    ) == "pending"


def test_runtime_refuses_always_rejecting_declaration(monkeypatch, tmp_path) -> None:
    spec = {
        "name": "broken",
        "severity": "block",
        "states": ["raw", "done"],
        "initial": "raw",
        "terminal": ["done"],
        "transitions": [{"from": "raw", "on": "finish", "to": "done"}],
        "positive_control": {
            "trace": [{"on": "undeclared"}],
            "expected_state": "done",
        },
        "negative_control": {
            "trace": [{"on": "undeclared"}],
            "must_reject_at": 0,
        },
    }
    path = tmp_path / "broken.fsm.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    monkeypatch.setattr(runtime, "FSM_ROOT", tmp_path)
    runtime.load_fsm.cache_clear()
    with pytest.raises(ContractFSMViolation, match=r"positive[_ ]control"):
        runtime.load_fsm("broken")
    runtime.load_fsm.cache_clear()
