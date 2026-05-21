"""
article_finder CLI.

Usage:
    python3 -m article_finder.cli search \\
        --topic "circadian lighting attention" \\
        --max-results 10 \\
        --enabled-sources openalex,crossref,arxiv \\
        --ai-backend none \\
        --output-dir data/handoff

Designed to run offline (deterministic backend, network disabled) for
tests, and online when network is enabled and API keys are set.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from .search.openalex import OpenAlexBackend
from .search.crossref import CrossrefBackend
from .search.arxiv import ArxivBackend
from .dedup.deduplicator import deduplicate
from .pdf.downloader import download_pdf
from .ranking.scorer import rank_records
from .ai.query_planner import plan_queries
from .ai.abstract_triage import triage
from .export.handoff import write_handoff

BACKENDS = {
    "openalex": OpenAlexBackend,
    "crossref": CrossrefBackend,
    "arxiv":    ArxivBackend,
}


def _parse_csv(s: str) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def cmd_search(args) -> int:
    out_dir = Path(args.output_dir)
    enabled = _parse_csv(args.enabled_sources)
    if not enabled:
        print("ERROR: --enabled-sources is empty", file=sys.stderr)
        return 1
    if not (args.topic or args.research_gap or args.seed_dois):
        print("ERROR: need --topic or --research-gap or --seed-dois", file=sys.stderr)
        return 1

    gap_text = args.research_gap or args.topic
    plan = plan_queries(gap_text, backend=args.ai_backend)
    topic_terms = set((plan.constructs or []) + (plan.outcomes or []) + (plan.population or []))
    if not topic_terms:
        topic_terms = set([t.lower() for t in gap_text.split() if len(t) > 3])

    # ── 1. Search each enabled source with its queries
    all_records: List[Dict[str, Any]] = []
    query_log: List[Dict[str, Any]] = [{
        "stage": "plan",
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "gap": gap_text,
        "plan": plan.to_log(),
    }]
    for src in enabled:
        cls = BACKENDS.get(src)
        if cls is None:
            print(f"  (skip) unknown source: {src}", file=sys.stderr)
            continue
        backend = cls()
        queries = plan.queries.get(src) or [gap_text]
        for q in queries[: args.queries_per_source]:
            t0 = time.time()
            if args.no_network:
                qr = type("QR", (), {"source": src, "query": q, "records": [],
                                      "n_results": 0, "error": "no_network",
                                      "elapsed_s": 0.0})
            else:
                qr = backend.search(q, max_results=args.max_results)
            query_log.append({
                "stage": "search",
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                "source": qr.source,
                "query": qr.query,
                "n_results": qr.n_results,
                "error": qr.error,
                "elapsed_s": getattr(qr, "elapsed_s", time.time() - t0),
            })
            all_records.extend(qr.records)
            print(f"  [{src:<10}] q={q[:50]!r:<55} n={qr.n_results}"
                  f"{' ERROR=' + qr.error if qr.error else ''}")

    if not all_records:
        print("No records harvested from any source.", file=sys.stderr)
        write_handoff(out_dir, articles=[], download_report=[],
                       query_log=query_log, dedup_report=[],
                       triage_notes=[], plan_summary=plan.to_log())
        return 2

    # ── 2. Deduplicate (preserving provenance)
    canonical, dedup_report = deduplicate(all_records)
    print(f"Dedup: {len(all_records)} -> {len(canonical)} canonical records")

    # ── 3. AI per-abstract triage
    triage_notes = []
    for r in canonical:
        v = triage(r.get("abstract") or "", gap_text,
                   list(topic_terms), backend=args.ai_backend)
        r["ai_triage_score"] = v.score
        r["why_selected"] = v.why_selected
        r["risks_or_limitations"] = v.risks_or_limitations
        triage_notes.append({
            "canonical_id": r.get("canonical_id"),
            "title": r.get("title"),
            "ai_triage_score": v.score,
            "why_selected": v.why_selected,
            "risks_or_limitations": v.risks_or_limitations,
        })

    # ── 4. Rank
    ranked = rank_records(canonical, topic_terms=topic_terms)
    for note, r in zip(triage_notes, ranked):
        note["rank"] = r["rank"]
        note["score"] = r["score"]

    # ── 5. PDF acquisition (only if --download-pdfs)
    download_report = []
    if args.download_pdfs:
        pdf_dir = out_dir / "pdfs"
        for r in ranked[: args.download_top_n]:
            res = download_pdf(r, pdf_dir, enable_network=not args.no_network)
            download_report.append(res)
            r["local_pdf_path"] = res.get("local_pdf_path")
            r["pdf_sha256"] = res.get("pdf_sha256")
            r["pdf_status"] = res.get("pdf_status")
    else:
        for r in ranked:
            r["pdf_status"] = "skipped_no_download"

    # ── 6. Write handoff
    paths = write_handoff(out_dir,
                          articles=ranked,
                          download_report=download_report,
                          query_log=query_log,
                          dedup_report=dedup_report,
                          triage_notes=triage_notes,
                          plan_summary=plan.to_log())
    print("\nHandoff files:")
    for k, v in paths.items():
        print(f"  {k:<20} {v}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="article_finder")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="run a search + triage + (optional) download")
    s.add_argument("--topic", default="")
    s.add_argument("--research-gap", default="")
    s.add_argument("--seed-dois", default="")
    s.add_argument("--max-results", type=int, default=25)
    s.add_argument("--queries-per-source", type=int, default=2)
    s.add_argument("--download-pdfs", action="store_true")
    s.add_argument("--download-top-n", type=int, default=10)
    s.add_argument("--enabled-sources", default="openalex,crossref,arxiv")
    s.add_argument("--ai-backend", choices=["none", "anthropic", "openai"], default="none")
    s.add_argument("--output-dir", default="data/handoff")
    s.add_argument("--no-network", action="store_true",
                   help="Disable all network calls; use for tests")
    s.set_defaults(func=cmd_search)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
