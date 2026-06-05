#!/usr/bin/env python3
"""
ae_inbox_stub.py — minimal stand-in for the Article Eater INTAKE side.

Article Eater is not on this checkout (see TASK3_CONTRACT.md §0), so this is the
documented stub that plays AE's role at the boundary: it READS a
`data/handoff/*.json` artefact and VALIDATES that it conforms to the handoff
contract (§0.1) so AE could consume it. It deliberately does NOT run extraction
— that is AE-owned and out of AF scope.

Why it exists: writing a file proves we *produced* an artefact; this stub proves
the artefact is *consumable* by the downstream reader. It validates positively
(accept good artefacts) and negatively (reject malformed ones with a reason).

Usage:
    python3 ae_inbox_stub.py --handoff-dir data/handoff
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ae_handoff import HANDOFF_DIR, HANDOFF_SCHEMA_FIELDS

# Fields AE requires present AND non-empty to start a job.
REQUIRED_NONEMPTY = ("handoff_id", "article_id", "abstract")
# The full set of fields AE expects to exist (some may legitimately be null).
REQUIRED_PRESENT = set(HANDOFF_SCHEMA_FIELDS)


class HandoffRejected(Exception):
    """Raised when an artefact cannot be consumed by AE intake."""


def validate_artefact(obj) -> dict:
    """Validate one handoff object the way AE intake would.

    Raises HandoffRejected(reason) if the artefact cannot be consumed.
    Returns a small accepted-job summary on success.
    """
    if not isinstance(obj, dict):
        raise HandoffRejected("not a JSON object")
    missing = REQUIRED_PRESENT - set(obj)
    if missing:
        raise HandoffRejected(f"missing fields: {sorted(missing)}")
    extra = set(obj) - REQUIRED_PRESENT
    if extra:
        raise HandoffRejected(f"unknown fields: {sorted(extra)}")
    for f in REQUIRED_NONEMPTY:
        v = obj.get(f)
        if not (isinstance(v, str) and v.strip()):
            raise HandoffRejected(f"required field '{f}' is empty/missing")
    if obj.get("handoff_status") != "written":
        raise HandoffRejected(f"handoff_status != 'written' ({obj.get('handoff_status')!r})")
    return {"job_id": obj["article_id"], "doi": obj.get("doi"),
            "abstract_chars": len(obj["abstract"])}


def read_inbox(handoff_dir: Path = HANDOFF_DIR) -> dict:
    """Read every artefact in the inbox. Returns {accepted:[...], rejected:[...]}."""
    accepted, rejected = [], []
    for p in sorted(handoff_dir.glob("*.json")):
        try:
            obj = json.loads(p.read_text())
            job = validate_artefact(obj)
            accepted.append({"file": p.name, **job})
        except (json.JSONDecodeError, HandoffRejected) as e:
            rejected.append({"file": p.name, "reason": str(e)})
    return {"accepted": accepted, "rejected": rejected}


def main() -> None:
    ap = argparse.ArgumentParser(description="Article Eater intake stub (validate handoffs).")
    ap.add_argument("--handoff-dir", type=Path, default=HANDOFF_DIR)
    args = ap.parse_args()
    res = read_inbox(args.handoff_dir)
    print(f"AE inbox: {len(res['accepted'])} accepted, {len(res['rejected'])} rejected")
    for j in res["accepted"]:
        print(f"  OK  {j['file']} -> job {j['job_id']} ({j['abstract_chars']} abstract chars)")
    for j in res["rejected"]:
        print(f"  NO  {j['file']}: {j['reason']}")


if __name__ == "__main__":
    main()
