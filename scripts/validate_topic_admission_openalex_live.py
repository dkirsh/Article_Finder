#!/usr/bin/env python3
"""Live, read-only validation of the topic-admission OpenAlex contract."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from topic_admission.artifacts import RawArtifactStore
from topic_admission.collectors.openalex import OpenAlexCollector
from topic_admission.identity import resolve_identity
from topic_admission.models import CandidateIdentity


def validate(email: str | None = None) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="af-openalex-validation-") as temporary:
        collector = OpenAlexCollector(RawArtifactStore(Path(temporary) / "raw"), email=email)
        correct = collector.collect(CandidateIdentity(
            paper_id="PDF-0180",
            title="The Atom and the Molecule",
            doi="10.1021/ja02261a002",
            authors=("Gilbert N. Lewis",),
            year=1916,
        ))
        misleading_candidate = CandidateIdentity(
            paper_id="PDF-0180-negative-control",
            title="California environmental psychology and human wellbeing",
            doi="10.1021/ja02261a002",
            year=1916,
        )
        raw_record = json.loads(Path(correct.raw_response_locator).read_text(encoding="utf-8")) if correct.raw_response_locator else {}
        misleading = resolve_identity(misleading_candidate, collector._identity_record(raw_record))
        topics = [item for item in correct.evidence if item.scheme == "OpenAlex Topics"]
        fields = {
            str((item.value.get("hierarchy") or {}).get("field", {}).get("name") or "")
            for item in topics
        }
        findings = []
        if correct.status != "ok":
            findings.append(f"correct lookup status={correct.status}")
        if (correct.identity_assertion or {}).get("decision") != "resolved":
            findings.append("correct identity did not resolve")
        if "Chemistry" not in fields:
            findings.append("OpenAlex topics did not expose Chemistry")
        if misleading.decision != "conflict":
            findings.append("misleading title did not produce identity conflict")
        if not correct.raw_response_sha256 or not correct.request_sha256:
            findings.append("missing request/response hashes")
        if "api_key=" in correct.request_url.lower():
            findings.append("credential appeared in recorded URL")
        return {
            "status": "ok" if not findings else "fail",
            "service": "OpenAlex",
            "collector_version": collector.version,
            "work_id": (correct.identity_assertion or {}).get("observed_record_id"),
            "identity_score": correct.identity_match,
            "field_names": sorted(field for field in fields if field),
            "raw_response_sha256": correct.raw_response_sha256,
            "request_sha256": correct.request_sha256,
            "negative_control_decision": misleading.decision,
            "findings": findings,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email")
    parser.add_argument("--wall-seconds", type=int, default=40)
    args = parser.parse_args()
    def deadline(signum, frame):
        raise TimeoutError(f"live validation exceeded {args.wall_seconds} seconds")
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(args.wall_seconds)
    try:
        payload = validate(args.email)
    except TimeoutError as exc:
        payload = {"status": "fail", "service": "OpenAlex", "findings": [str(exc)]}
    finally:
        signal.alarm(0)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
