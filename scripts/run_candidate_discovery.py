#!/usr/bin/env python3
"""Run one target-driven candidate discovery pass."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from candidate_discovery import OpenAlexCandidateSource, TargetSearch
from candidate_discovery.run import run_target_discovery
from config.loader import get


def _terms(value: str | None) -> set[str]:
    if not value:
        return set()
    return {term.strip().lower() for term in value.split(",") if term.strip()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True)
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--target-type", default="question")
    parser.add_argument("--accept-terms", required=True, help="Comma-separated target terms.")
    parser.add_argument("--reject-terms", default="", help="Comma-separated exclusion terms.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--candidate-db", default="data/candidate_discovery.db")
    parser.add_argument("--af-db", default=get("paths.database", "data/article_finder.db"))
    parser.add_argument("--email", default=get("apis.openalex.email"))
    parser.add_argument("--api-key", default=get("apis.openalex.api_key"))
    parser.add_argument("--discovery-run-id")
    parser.add_argument("--voi", type=float)
    parser.add_argument("--acquire-pdfs", action="store_true")
    parser.add_argument("--pdf-dir", default="data/candidate_pdfs")
    parser.add_argument("--no-promote", action="store_true")
    args = parser.parse_args()

    source = OpenAlexCandidateSource(email=args.email, api_key=args.api_key)
    summary = run_target_discovery(
        target=TargetSearch(
            query=args.query,
            target_id=args.target_id,
            target_type=args.target_type,
            local_heuristic_voi=args.voi,
            discovery_run_id=args.discovery_run_id,
        ),
        candidate_db=Path(args.candidate_db),
        af_db=Path(args.af_db),
        accept_terms=_terms(args.accept_terms),
        reject_terms=_terms(args.reject_terms),
        limit=args.limit,
        source=source,
        acquire_pdfs=args.acquire_pdfs,
        pdf_dir=Path(args.pdf_dir),
        promote=not args.no_promote,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
