"""Repository path adapter for the control-governed FSM runtime."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from core.vendor_fsm_enforcer import FSMError, load_and_validate


FSM_ROOT = Path(__file__).resolve().parents[1] / "contracts" / "fsm"


class ContractFSMViolation(ValueError):
    """Product-facing form of a fail-closed FSM rejection."""


@lru_cache(maxsize=None)
def load_fsm(name: str):
    path = FSM_ROOT / f"{name}.fsm.json"
    try:
        fsm = load_and_validate(path)
    except FSMError as exc:
        raise ContractFSMViolation(str(exc)) from exc
    if fsm.severity != "block":
        raise ContractFSMViolation(f"product P1 FSM must be blocking: {path}")
    return fsm


def enforce_transition(
    name: str,
    state: str,
    event: str,
    *,
    guards: Mapping[str, bool] | None = None,
) -> str:
    try:
        result = load_fsm(name).step(state, event, guards=guards)
    except FSMError as exc:
        raise ContractFSMViolation(str(exc)) from exc
    if not isinstance(result, str):
        raise ContractFSMViolation(result["warn"])
    return result


def transition_targets(name: str) -> dict[str, list[str]]:
    """Expose validated transitions through the legacy mapping API."""
    load_fsm(name)
    path = FSM_ROOT / f"{name}.fsm.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    result = {str(state): [] for state in spec["states"]}
    for transition in spec["transitions"]:
        source = str(transition["from"])
        target = str(transition["to"])
        if target not in result[source]:
            result[source].append(target)
    return result
