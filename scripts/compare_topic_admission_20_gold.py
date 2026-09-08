#!/usr/bin/env python3
"""Twenty-paper positive-recall and article-type assay for AF topic admission."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


AF = Path(__file__).resolve().parents[1]
REPOS = AF.parent
AE = REPOS / "Article_Eater_PostQuinean_v1_recovery"
ATLAS_SRC = REPOS / "atlas_shared" / "src"
for root in (AF, ATLAS_SRC):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from atlas_shared.classifier_system import AdaptiveClassifierSubsystem, ClassificationEvidence
from atlas_shared.topic_bank import load_topic_constitution_bank
from topic_admission.artifacts import RawArtifactStore
from topic_admission.collectors.openalex import OpenAlexCollector
from topic_admission.models import CandidateIdentity
from triage.classifier import HierarchicalClassifier


DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
KEYWORD_RE = re.compile(r"(?:key\s*words?|index terms?)\s*[:—-]\s*(.+)", re.I)
TYPE_FAMILIES = {
    "empirical_research": "empirical",
    "experimental": "empirical",
    "observational": "empirical",
    "meta_analysis": "review",
    "systematic_review": "review",
    "literature_review": "review",
    "review": "review",
    "narrative_review": "review",
    "theoretical": "theoretical",
    "conceptual": "theoretical",
    "case_study": "case_study",
    "qualitative": "qualitative",
    "qualitative_research": "qualitative",
    "reflective": "reflective",
    "commentary": "reflective",
    "methods": "methods",
    "methodological": "methods",
}


def now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def family(value: Any) -> str:
    text = str(value or "").strip().lower().replace(" ", "_")
    return TYPE_FAMILIES.get(text, text or "unknown")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_doi(value: Any) -> str:
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() == "doi" and isinstance(item, str) and item.strip():
                return item.strip()
        for item in value.values():
            found = find_doi(item)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = find_doi(item)
            if found:
                return found
    return ""


def read_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
    return rows


def pdf_surface(path: Path) -> dict[str, Any]:
    proc = subprocess.run(
        ["pdftotext", "-f", "1", "-l", "2", "-layout", str(path), "-"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    text = proc.stdout[:30000]
    dois = DOI_RE.findall(text)
    keyword_lines = KEYWORD_RE.findall(text)
    keywords: list[str] = []
    for line in keyword_lines:
        keywords.extend(item.strip(" .") for item in re.split(r"[;,]", line)
                        if item.strip(" .") and len(item.strip(" .")) <= 100)
    return {"doi_candidates": dois, "keywords": keywords, "first_two_pages_text": text[:12000]}


def sampling_frame() -> list[dict[str, Any]]:
    db = AE / "data/verification_runs/v7_gold_extraction_registry.db"
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    records = conn.execute(
        "SELECT paper_id,title,article_type,status,accepted_for_rebuild,output_jsonl_path "
        "FROM gold_papers WHERE accepted_for_rebuild=1 ORDER BY paper_id"
    ).fetchall()
    conn.close()
    cache: dict[Path, list[dict[str, Any]]] = {}
    frame = []
    for record in records:
        jsonl = Path(record["output_jsonl_path"])
        if jsonl not in cache:
            cache[jsonl] = read_rows(jsonl)
        payload = next(
            (item for item in cache[jsonl]
             if str(item.get("paper_id") or item.get("pdf_id") or "") == record["paper_id"]),
            None,
        )
        pdf = AE / "data/production/pdfs" / f"{record['paper_id']}.pdf"
        if not payload or not pdf.is_file() or not find_doi(payload):
            continue
        frame.append({
            "paper_id": record["paper_id"], "title": record["title"],
            "gold_article_type": record["article_type"], "registry_status": record["status"],
            "payload": payload, "pdf_path": str(pdf), "pdf_sha256": sha(pdf),
            "source_jsonl": str(jsonl), "stored_doi": find_doi(payload),
        })
    return frame


def atlas_result(subsystem: AdaptiveClassifierSubsystem, paper: dict[str, Any], mode: str,
                 external_keywords: tuple[str, ...] = (), topic_hints: tuple[str, ...] = ()) -> dict[str, Any]:
    payload = paper["payload"]
    evidence = ClassificationEvidence(
        paper_id=paper["paper_id"], title=paper["title"],
        abstract=str(payload.get("abstract") or "") if mode != "title_only" else "",
        keywords=external_keywords, topic_hints=topic_hints,
        doi=paper["stored_doi"], year=payload.get("year") if isinstance(payload.get("year"), int) else None,
        preliminary_article_type="",
    )
    started = time.perf_counter()
    result = subsystem.classify(evidence, allow_surface_creation=False).to_dict()
    elapsed = time.perf_counter() - started
    intake = result.get("intake_result") or {}
    routing = result.get("stable_topic_routing") or {}
    article_type = result.get("article_type") or {}
    decision = str(intake.get("intake_decision") or "")
    return {
        "mode": mode, "seconds": round(elapsed, 6), "decision": decision,
        "retained": decision not in {"reject_clear_false_positive", ""},
        "domain_relevance": intake.get("domain_relevance"),
        "primary_topic": intake.get("primary_topic") or routing.get("primary_topic"),
        "confidence": result.get("overall_confidence"),
        "needs_manual_review": intake.get("needs_manual_review"),
        "matched_question_ids": intake.get("matched_question_ids") or [],
        "article_type": article_type.get("value"),
        "article_type_family": family(article_type.get("value")),
        "article_type_confidence": article_type.get("confidence"),
        "gold_article_type_family": family(paper["gold_article_type"]),
        "article_type_correct": family(article_type.get("value")) == family(paper["gold_article_type"]),
    }


def openalex_one(paper: dict[str, Any], raw_root: Path) -> dict[str, Any]:
    surface = pdf_surface(Path(paper["pdf_path"]))
    pdf_doi = next((doi.rstrip(".,") for doi in surface["doi_candidates"] if len(doi) > 12), "")
    candidate_doi = pdf_doi or paper["stored_doi"]
    payload = paper["payload"]
    authors = payload.get("authors") or ()
    if isinstance(authors, str):
        authors = (authors,)
    collector = OpenAlexCollector(RawArtifactStore(raw_root / paper["paper_id"]), timeout=30)
    started = time.perf_counter()
    result = collector.collect(CandidateIdentity(
        paper_id=paper["paper_id"], title=paper["title"], doi=candidate_doi,
        authors=tuple(str(item) for item in authors),
        year=payload.get("year") if isinstance(payload.get("year"), int) else None,
    ))
    elapsed = time.perf_counter() - started
    topics = [item for item in result.evidence if item.scheme == "OpenAlex Topics"]
    work_types = [item for item in result.evidence if item.scheme == "OpenAlex Work Type"]
    raw_keywords: list[str] = []
    if result.raw_response_locator and Path(result.raw_response_locator).is_file():
        try:
            raw = json.loads(Path(result.raw_response_locator).read_text(encoding="utf-8"))
            for item in raw.get("keywords") or []:
                label = str(item.get("display_name") or "").strip() if isinstance(item, dict) else ""
                if label:
                    raw_keywords.append(label)
        except (OSError, json.JSONDecodeError):
            pass
    return {
        "seconds": round(elapsed, 6), "stored_doi": paper["stored_doi"], "pdf_doi": pdf_doi,
        "doi_corrected_from_pdf": bool(pdf_doi and pdf_doi.lower() != paper["stored_doi"].lower()),
        "pdf_keywords": surface["keywords"], "status": result.status,
        "http_status": result.http_status, "identity_match": result.identity_match,
        "identity_decision": result.identity_assertion.get("decision") if result.identity_assertion else "",
        "identity_conflicts": result.identity_assertion.get("conflicts") if result.identity_assertion else [],
        "topics": [{"id": item.stable_id, "label": item.label, "score": item.confidence,
                    "primary": item.primary_topic, "hierarchy": item.value.get("hierarchy")}
                   for item in topics],
        "openalex_keywords": raw_keywords,
        "work_type": work_types[0].value if work_types else "",
        "work_type_family": family(work_types[0].value if work_types else ""),
        "gold_article_type_family": family(paper["gold_article_type"]),
        "work_type_correct": family(work_types[0].value if work_types else "") == family(paper["gold_article_type"]),
    }


def summarize(rows: list[dict[str, Any]], frame_size: int, seed: int) -> dict[str, Any]:
    modes = ("title_only", "title_abstract", "keyword_enriched")
    summary: dict[str, Any] = {
        "sample_size": len(rows), "sampling_frame_size": frame_size, "random_seed": seed,
        "positive_only": True,
    }
    for mode in modes:
        values = [row["atlas"][mode] for row in rows]
        summary[mode] = {
            "retained": sum(item["retained"] for item in values),
            "recall": round(sum(item["retained"] for item in values) / len(values), 4),
            "manual_review": sum(bool(item["needs_manual_review"]) for item in values),
            "article_type_correct": sum(item["article_type_correct"] for item in values),
            "article_type_accuracy": round(sum(item["article_type_correct"] for item in values) / len(values), 4),
            "mean_seconds": round(sum(item["seconds"] for item in values) / len(values), 6),
        }
    oa = [row["openalex"] for row in rows]
    summary["openalex"] = {
        "source_ok": sum(item["status"] == "ok" for item in oa),
        "identity_resolved": sum(item["identity_decision"] == "resolved" for item in oa),
        "doi_corrected_from_pdf": sum(item["doi_corrected_from_pdf"] for item in oa),
        "has_topics": sum(bool(item["topics"]) for item in oa),
        "has_keywords": sum(bool(item["openalex_keywords"] or item["pdf_keywords"]) for item in oa),
        "work_type_correct": sum(item["work_type_correct"] for item in oa),
        "work_type_accuracy": round(sum(item["work_type_correct"] for item in oa) / len(oa), 4),
        "mean_seconds": round(sum(item["seconds"] for item in oa) / len(oa), 6),
    }
    return summary


def write_db(path: Path, run: dict[str, Any]) -> None:
    conn = sqlite3.connect(path)
    conn.executescript("""
    CREATE TABLE run(run_id TEXT PRIMARY KEY, created_at_utc TEXT, seed INTEGER, frame_size INTEGER,
                     sample_size INTEGER, result_json TEXT NOT NULL);
    CREATE TABLE paper(run_id TEXT, paper_id TEXT, title TEXT, pdf_sha256 TEXT, gold_article_type TEXT,
                       stored_doi TEXT, result_json TEXT NOT NULL, PRIMARY KEY(run_id,paper_id));
    CREATE TABLE event(event_id INTEGER PRIMARY KEY, run_id TEXT, occurred_at TEXT, stage TEXT, status TEXT, note TEXT);
    """)
    run_id = run["run_id"]
    conn.execute("INSERT INTO run VALUES(?,?,?,?,?,?)", (
        run_id, run["created_at_utc"], run["seed"], run["sampling_frame_size"], len(run["papers"]),
        json.dumps(run["summary"], sort_keys=True),
    ))
    for paper in run["papers"]:
        conn.execute("INSERT INTO paper VALUES(?,?,?,?,?,?,?)", (
            run_id, paper["paper_id"], paper["title"], paper["pdf_sha256"], paper["gold_article_type"],
            paper["stored_doi"], json.dumps(paper, ensure_ascii=False, sort_keys=True),
        ))
    conn.execute("INSERT INTO event(run_id,occurred_at,stage,status,note) VALUES(?,?,?,?,?)",
                 (run_id, now(), "complete", "ok", "positive-recall and article-type assay complete"))
    conn.commit()
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260829)
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--output", type=Path,
                        default=AF / "data/topic_comparison/gold_sample_20_2026-08-29")
    args = parser.parse_args()
    frame = sampling_frame()
    selected = random.Random(args.seed).sample(frame, args.sample_size)
    bank = load_topic_constitution_bank()
    subsystem = AdaptiveClassifierSubsystem(bank.constitutions)
    args.output.mkdir(parents=True, exist_ok=True)
    raw_root = args.output / "raw_openalex"
    oa_by_id: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(openalex_one, paper, raw_root): paper["paper_id"] for paper in selected}
        for future in as_completed(futures):
            paper_id = futures[future]
            try:
                oa_by_id[paper_id] = future.result()
            except Exception as exc:
                oa_by_id[paper_id] = {"status": "runner_error", "error": type(exc).__name__, "seconds": 0,
                                      "topics": [], "openalex_keywords": [], "pdf_keywords": [],
                                      "identity_decision": "", "doi_corrected_from_pdf": False,
                                      "work_type_correct": False}
            print(f"openalex {paper_id}: {oa_by_id[paper_id]['status']}", flush=True)
    rows = []
    for paper in selected:
        oa = oa_by_id[paper["paper_id"]]
        external_keywords = tuple(dict.fromkeys([*oa.get("pdf_keywords", []), *oa.get("openalex_keywords", [])]))
        topic_labels = tuple(item["label"] for item in oa.get("topics", []))
        external_keywords = tuple(dict.fromkeys([*external_keywords, *topic_labels]))
        paper["openalex"] = oa
        paper["atlas"] = {
            "title_only": atlas_result(subsystem, paper, "title_only"),
            "title_abstract": atlas_result(subsystem, paper, "title_abstract"),
            "keyword_enriched": atlas_result(subsystem, paper, "keyword_enriched", external_keywords),
        }
        paper.pop("payload")
        rows.append(paper)
    run = {
        "schema_version": "af_topic_admission_20_gold_v1", "run_id": f"gold20-{args.seed}",
        "created_at_utc": now(), "seed": args.seed, "sampling_frame_size": len(frame),
        "atlas_constitution_version": bank.version, "papers": rows,
    }
    run["summary"] = summarize(rows, len(frame), args.seed)
    (args.output / "results.json").write_text(json.dumps(run, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    write_db(args.output / "comparison.db", run)
    print(json.dumps(run["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
