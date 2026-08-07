#!/usr/bin/env python3
"""Fail-closed state-machine enforcement for repository contracts.

Every specification must prove one legal trace and one illegal trace. Guarded
edges use named guard results; a single boolean cannot safely select between
two guarded edges carrying the same event.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class FSMError(ValueError):
    """Base class for invalid specifications and illegal transitions."""


class InvalidSpecification(FSMError):
    """The FSM declaration is incomplete or contradictory."""


class IllegalTransition(FSMError):
    """A blocking FSM rejected an event from the current state."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidSpecification(message)


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


class FSM:
    def __init__(self, spec: Mapping[str, Any]):
        validate_structure(spec)
        self.name = str(spec["name"])
        self.severity = str(spec["severity"])
        self.states = frozenset(spec["states"])
        self.initial = str(spec["initial"])
        self.terminal = frozenset(spec["terminal"])
        self._transitions: dict[
            tuple[str, str], list[tuple[str, str | None]]
        ] = {}
        for transition in spec["transitions"]:
            key = (transition["from"], transition["on"])
            self._transitions.setdefault(key, []).append(
                (transition["to"], transition.get("guard"))
            )

    def step(
        self,
        state: str,
        event: str,
        *,
        guards: Mapping[str, bool] | None = None,
    ) -> str | dict[str, str]:
        """Return the next state or reject an absent/failed/ambiguous edge."""
        if state not in self.states:
            return self._reject(state, event, "current state is undeclared")
        candidates = self._transitions.get((state, event), [])
        if not candidates:
            return self._reject(state, event, "no declared transition")

        guard_values = guards or {}
        eligible = [
            (target, guard)
            for target, guard in candidates
            if guard is None or guard_values.get(guard) is True
        ]
        if not eligible:
            required = sorted(guard for _target, guard in candidates if guard)
            return self._reject(
                state,
                event,
                f"no guard passed; required one of {required}",
            )
        if len(eligible) != 1:
            matched = sorted(guard or "<unguarded>" for _target, guard in eligible)
            return self._reject(
                state,
                event,
                f"ambiguous guards passed: {matched}",
            )
        return eligible[0][0]

    def _reject(self, state: str, event: str, reason: str) -> dict[str, str]:
        message = (
            f"[{self.name}] illegal transition: state={state} "
            f"on={event} ({reason})"
        )
        if self.severity == "block":
            raise IllegalTransition(message)
        return {"warn": message, "state": state, "on": event}

    def validate_trace(self, trace: list[Mapping[str, Any]]) -> str:
        state: str | dict[str, str] = self.initial
        for item in trace:
            if isinstance(state, dict):
                return "WARN:" + state["warn"]
            state = self.step(
                state,
                str(item["on"]),
                guards=item.get("guards"),
            )
        if isinstance(state, dict):
            return "WARN:" + state["warn"]
        return state


def validate_structure(spec: Mapping[str, Any]) -> None:
    _require(isinstance(spec, Mapping), "FSM spec must be an object")
    _require(_is_nonempty_string(spec.get("name")), "name must be non-empty")
    _require(
        spec.get("severity") in {"block", "warn"},
        "severity must be 'block' or 'warn'",
    )
    states = spec.get("states")
    _require(
        isinstance(states, list)
        and bool(states)
        and all(_is_nonempty_string(state) for state in states),
        "states must be a non-empty list of strings",
    )
    _require(len(states) == len(set(states)), "states must be unique")
    _require(spec.get("initial") in states, "initial must be a declared state")
    terminal = spec.get("terminal")
    lifecycle = spec.get("lifecycle", "terminating")
    _require(
        lifecycle in {"terminating", "cyclic"},
        "lifecycle must be 'terminating' or 'cyclic'",
    )
    _require(
        isinstance(terminal, list) and all(state in states for state in terminal),
        "terminal must be a list of declared states",
    )
    if lifecycle == "terminating":
        _require(bool(terminal), "terminating FSM requires a terminal state")
    else:
        _require(not terminal, "cyclic FSM must declare terminal=[]")

    transitions = spec.get("transitions")
    _require(
        isinstance(transitions, list) and bool(transitions),
        "transitions must be a non-empty list",
    )
    seen: set[tuple[str, str, str, str | None]] = set()
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for index, transition in enumerate(transitions):
        _require(isinstance(transition, Mapping), f"transition {index} is not an object")
        _require(transition.get("from") in states, f"transition {index} has unknown from")
        _require(transition.get("to") in states, f"transition {index} has unknown to")
        _require(_is_nonempty_string(transition.get("on")), f"transition {index} has invalid event")
        guard = transition.get("guard")
        _require(guard is None or _is_nonempty_string(guard), f"transition {index} has invalid guard")
        identity = (
            transition["from"],
            transition["on"],
            transition["to"],
            guard,
        )
        _require(identity not in seen, f"duplicate transition at index {index}")
        seen.add(identity)
        grouped.setdefault((transition["from"], transition["on"]), []).append(
            transition
        )
    for key, alternatives in grouped.items():
        if len(alternatives) > 1:
            guards = [item.get("guard") for item in alternatives]
            _require(
                None not in guards and len(guards) == len(set(guards)),
                f"ambiguous alternatives for state/event {key}",
            )

    graph: dict[str, set[str]] = {state: set() for state in states}
    reverse_graph: dict[str, set[str]] = {state: set() for state in states}
    for transition in transitions:
        graph[transition["from"]].add(transition["to"])
        reverse_graph[transition["to"]].add(transition["from"])
    reachable = {spec["initial"]}
    frontier = [spec["initial"]]
    while frontier:
        current = frontier.pop()
        for target in graph[current] - reachable:
            reachable.add(target)
            frontier.append(target)
    _require(
        reachable == set(states),
        f"unreachable states: {sorted(set(states) - reachable)}",
    )
    if lifecycle == "terminating":
        _require(
            all(not graph[state] for state in terminal),
            "terminal states must have no outgoing transitions",
        )
        can_terminate = set(terminal)
        frontier = list(terminal)
        while frontier:
            current = frontier.pop()
            for source in reverse_graph[current] - can_terminate:
                can_terminate.add(source)
                frontier.append(source)
        _require(
            can_terminate == set(states),
            f"states with no path to terminal: {sorted(set(states) - can_terminate)}",
        )

    declared_events = {transition["on"] for transition in transitions}
    for control_name in ("positive_control", "negative_control"):
        control = spec.get(control_name)
        _require(isinstance(control, Mapping), f"{control_name} is required")
        trace = control.get("trace")
        _require(
            isinstance(trace, list) and bool(trace),
            f"{control_name}.trace must be non-empty",
        )
        for index, item in enumerate(trace):
            _require(
                isinstance(item, Mapping) and _is_nonempty_string(item.get("on")),
                f"{control_name}.trace[{index}] has no event",
            )
            _require(
                set(item).issubset({"on", "guards"}),
                f"{control_name}.trace[{index}] has unknown keys",
            )
            guards = item.get("guards", {})
            _require(
                isinstance(guards, Mapping)
                and all(
                    _is_nonempty_string(key) and type(value) is bool
                    for key, value in guards.items()
                ),
                f"{control_name}.trace[{index}].guards is invalid",
            )
            _require(
                item["on"] in declared_events,
                f"{control_name}.trace[{index}] uses undeclared event",
            )
    _require(
        _is_nonempty_string(spec["positive_control"].get("expected_state")),
        "positive_control.expected_state is required",
    )
    _require(
        spec["positive_control"]["expected_state"] in states,
        "positive_control.expected_state is undeclared",
    )
    reject_at = spec["negative_control"].get("must_reject_at")
    _require(
        type(reject_at) is int
        and 0 <= reject_at < len(spec["negative_control"]["trace"]),
        "negative_control.must_reject_at is outside the trace",
    )


def validate_spec(spec: Mapping[str, Any]) -> None:
    """Prove that the declaration accepts its good trace and rejects its bad one."""
    validate_structure(spec)
    blocking_spec = dict(spec)
    blocking_spec["severity"] = "block"
    fsm = FSM(blocking_spec)

    try:
        final_state = fsm.validate_trace(spec["positive_control"]["trace"])
    except IllegalTransition as exc:
        raise InvalidSpecification(
            f"FSM '{spec['name']}' rejects its positive_control: {exc}"
        ) from exc
    expected = spec["positive_control"]["expected_state"]
    if final_state != expected:
        raise InvalidSpecification(
            f"FSM '{spec['name']}' positive_control ended at {final_state}, "
            f"expected {expected}"
        )

    state = fsm.initial
    rejected_at: int | None = None
    for index, item in enumerate(spec["negative_control"]["trace"]):
        try:
            result = fsm.step(state, item["on"], guards=item.get("guards"))
            if isinstance(result, dict):
                raise InvalidSpecification("blocking negative control returned warning")
            state = result
        except IllegalTransition:
            rejected_at = index
            break
    expected_rejection = spec["negative_control"]["must_reject_at"]
    if rejected_at != expected_rejection:
        raise InvalidSpecification(
            f"FSM '{spec['name']}' negative_control rejected_at={rejected_at}; "
            f"expected {expected_rejection}"
        )


def load_and_validate(path: Path) -> FSM:
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InvalidSpecification(f"cannot read {path}: {exc}") from exc
    validate_spec(spec)
    return FSM(spec)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("specs", nargs="+", type=Path)
    args = parser.parse_args()
    failed = False
    for path in args.specs:
        try:
            fsm = load_and_validate(path)
            print(f"OK {path} severity={fsm.severity} controls=positive+negative")
        except FSMError as exc:
            failed = True
            print(f"RED {path}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
