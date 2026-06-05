"""
Write the six required handoff files atomically (write-temp-then-rename).
"""
from __future__ import annotations
import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List


CSV_COLUMNS = [
    "rank", "canonical_id", "doi", "title", "year", "venue",
    "first_author_surname", "is_oa", "pdf_status", "local_pdf_path",
    "pdf_sha256", "score", "duplicate_group_id", "sources",
    "openalex_id", "arxiv_id", "pubmed_id",
]


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except Exception: pass


def write_handoff(out_dir: Path, *,
                  articles: List[Dict[str, Any]],
                  download_report: List[Dict[str, Any]],
                  query_log: List[Dict[str, Any]],
                  dedup_report: List[Dict[str, Any]],
                  triage_notes: List[Dict[str, Any]],
                  plan_summary: Dict[str, Any] | None = None) -> Dict[str, str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "articles_json":     out_dir / "articles.json",
        "articles_csv":      out_dir / "articles.csv",
        "download_report":   out_dir / "download_report.json",
        "query_log":         out_dir / "query_log.json",
        "dedup_report":      out_dir / "dedup_report.json",
        "triage_report":     out_dir / "triage_report.md",
    }

    _atomic_write(paths["articles_json"], json.dumps(articles, indent=2, ensure_ascii=False))
    _atomic_write(paths["download_report"], json.dumps(download_report, indent=2))
    _atomic_write(paths["query_log"], json.dumps(query_log, indent=2))
    _atomic_write(paths["dedup_report"], json.dumps(dedup_report, indent=2))

    # CSV
    import io
    sio = io.StringIO()
    w = csv.writer(sio)
    w.writerow(CSV_COLUMNS)
    for r in articles:
        w.writerow([
            r.get("rank"),
            r.get("canonical_id"),
            r.get("doi"),
            (r.get("title") or "").replace("\n", " ")[:200],
            r.get("year"),
            (r.get("venue") or "")[:80],
            r.get("first_author_surname"),
            r.get("is_oa"),
            r.get("pdf_status"),
            r.get("local_pdf_path"),
            r.get("pdf_sha256"),
            r.get("score"),
            r.get("duplicate_group_id"),
            ",".join(r.get("sources") or []),
            r.get("openalex_id"),
            r.get("arxiv_id"),
            r.get("pubmed_id"),
        ])
    _atomic_write(paths["articles_csv"], sio.getvalue())

    # Markdown triage report
    md = ["# Triage report", ""]
    if plan_summary:
        md.append("## Query plan")
        md.append(f"- Backend: `{plan_summary.get('backend')}`")
        md.append(f"- Confidence: {plan_summary.get('confidence')}")
        md.append(f"- Constructs: {', '.join(plan_summary.get('constructs') or [])}")
        md.append("")
    md.append("## Per-paper triage")
    for note in triage_notes:
        md.append(f"### {note.get('rank','?')}. {note.get('title','(no title)')}")
        md.append(f"- canonical_id: `{note.get('canonical_id')}`")
        md.append(f"- score: {note.get('score')}  ·  ai_triage: {note.get('ai_triage_score')}")
        md.append(f"- why_selected: {note.get('why_selected')}")
        if note.get("risks_or_limitations"):
            md.append(f"- risks: {', '.join(note['risks_or_limitations'])}")
        md.append("")
    _atomic_write(paths["triage_report"], "\n".join(md))

    return {k: str(v) for k, v in paths.items()}
