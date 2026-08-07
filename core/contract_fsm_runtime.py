"""Small fail-closed runtime for repository-owned contract FSM declarations."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
FSM_ROOT = ROOT / "contracts" / "fsm"


class ContractFSMViolation(ValueError):
    """Raised when an undeclared or ambiguous transition is attempted."""


@lru_cache(maxsize=None)
def load_fsm(name: str) -> Mapping[str, Any]:
    path = FSM_ROOT / f"{name}.fsm.json"
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractFSMViolation(f"cannot load FSM {path}: {exc}") from exc

    _validate_spec(name, spec, path)
    return spec


def _next_state(
    name: str,
    spec: Mapping[str, Any],
    state: str,
    event: str,
    guards: Mapping[str, bool] | None,
) -> str:
    states = set(spec["states"])
    if state not in states:
        raise ContractFSMViolation(f"[{name}] undeclared current state: {state}")
    guard_values = guards or {}
    candidates = [
        transition
        for transition in spec["transitions"]
        if transition.get("from") == state and transition.get("on") == event
    ]
    eligible = [
        transition
        for transition in candidates
        if transition.get("guard") is None
        or guard_values.get(str(transition["guard"])) is True
    ]
    if len(eligible) != 1:
        raise ContractFSMViolation(
            f"[{name}] illegal or ambiguous transition: "
            f"state={state} event={event} eligible={len(eligible)}"
        )
    return str(eligible[0]["to"])


def _validate_spec(name: str, spec: object, path: Path) -> None:
    if not isinstance(spec, dict) or spec.get("severity") != "block":
        raise ContractFSMViolation(f"incomplete blocking FSM declaration: {path}")
    states = spec.get("states")
    transitions = spec.get("transitions")
    if (
        not isinstance(states, list)
        or not states
        or not all(isinstance(state, str) and state for state in states)
        or len(states) != len(set(states))
        or spec.get("initial") not in states
        or not isinstance(spec.get("terminal"), list)
        or not spec["terminal"]
        or not set(spec["terminal"]).issubset(states)
        or not isinstance(transitions, list)
        or not transitions
    ):
        raise ContractFSMViolation(f"invalid states or transitions in {path}")

    alternatives: dict[tuple[str, str], list[str | None]] = {}
    for transition in transitions:
        if (
            not isinstance(transition, dict)
            or transition.get("from") not in states
            or transition.get("to") not in states
            or not isinstance(transition.get("on"), str)
            or not transition["on"]
            or (
                transition.get("guard") is not None
                and not isinstance(transition.get("guard"), str)
            )
        ):
            raise ContractFSMViolation(f"invalid transition in {path}: {transition}")
        key = (transition["from"], transition["on"])
        alternatives.setdefault(key, []).append(transition.get("guard"))
    for key, guards in alternatives.items():
        if len(guards) > 1 and (None in guards or len(guards) != len(set(guards))):
            raise ContractFSMViolation(f"ambiguous transition alternatives {key} in {path}")

    positive = spec.get("positive_control")
    negative = spec.get("negative_control")
    if not isinstance(positive, dict) or not isinstance(negative, dict):
        raise ContractFSMViolation(f"positive and negative controls are required: {path}")
    positive_trace = positive.get("trace")
    negative_trace = negative.get("trace")
    if not isinstance(positive_trace, list) or not positive_trace:
        raise ContractFSMViolation(f"positive control trace is required: {path}")
    if not isinstance(negative_trace, list) or not negative_trace:
        raise ContractFSMViolation(f"negative control trace is required: {path}")

    state = str(spec["initial"])
    try:
        for item in positive_trace:
            state = _next_state(name, spec, state, item["on"], item.get("guards"))
    except (KeyError, TypeError, ContractFSMViolation) as exc:
        raise ContractFSMViolation(f"positive control is not accepted in {path}: {exc}") from exc
    if state != positive.get("expected_state"):
        raise ContractFSMViolation(
            f"positive control ended at {state}, expected {positive.get('expected_state')}"
        )

    expected_rejection = negative.get("must_reject_at")
    if not isinstance(expected_rejection, int):
        raise ContractFSMViolation(f"negative control rejection index is required: {path}")
    state = str(spec["initial"])
    rejected_at = None
    for index, item in enumerate(negative_trace):
        try:
            state = _next_state(name, spec, state, item["on"], item.get("guards"))
        except (KeyError, TypeError, ContractFSMViolation):
            rejected_at = index
            break
    if rejected_at != expected_rejection:
        raise ContractFSMViolation(
            f"negative control rejected_at={rejected_at}, expected {expected_rejection}"
        )


def enforce_transition(
    name: str,
    state: str,
    event: str,
    *,
    guards: Mapping[str, bool] | None = None,
) -> str:
    """Return the one declared next state, otherwise reject the write."""
    spec = load_fsm(name)
    return _next_state(name, spec, state, event, guards)


def transition_targets(name: str) -> dict[str, list[str]]:
    """Expose the declaration as the legacy state-to-target mapping."""
    spec = load_fsm(name)
    result = {str(state): [] for state in spec["states"]}
    for transition in spec["transitions"]:
        source = str(transition["from"])
        target = str(transition["to"])
        if target not in result[source]:
            result[source].append(target)
    return result
