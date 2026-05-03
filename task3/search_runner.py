#!/usr/bin/env python3
"""
search_runner.py — Task 3 Phase 2.

Reads `query_results.json`, runs the Boolean query for each gap against one or
more search backends (SerpAPI primary, scholarly fallback, paper-scraper for
backlog), and inserts every harvested record into `article_references` with
full provenance.

Backends:
  - serpapi    : requires SERPAPI_API_KEY env var (Google Scholar engine)
  - scholarly  : python `scholarly` package, no key needed (rate-limited)
  - mock       : built-in synthetic generator — produces realistic, deduplicable
                 records so downstream stages can be exercised end-to-end without
                 burning API quota or relying on network.

Dedup key: doi if present, else sha1(lower(title))[:16].

Usage:
    python3 search_runner.py --queries ../query_results.json --backend mock --top-n 10
    python3 search_runner.py --queries ../query_results.json --backend serpapi --per-query 10
"""

from __future__ import annotations
import argparse
import hashlib
import json
import os
import random
import sqlite3
import sys
import time
from pathlib import Path
from typing import Iterable

from db_schema import open_db, DEFAULT_DB

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUERIES = REPO_ROOT / "query_results.json"


# ─────────────────────────────────────────────────────────────────────────────
# Dedup key
# ─────────────────────────────────────────────────────────────────────────────
def make_dedup_key(doi: str | None, title: str | None) -> str:
    if doi:
        return f"doi:{doi.strip().lower()}"
    base = (title or "").strip().lower()
    return "title:" + hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


# ─────────────────────────────────────────────────────────────────────────────
# Backends
# ─────────────────────────────────────────────────────────────────────────────
def search_serpapi(query: str, n: int = 10) -> list[dict]:
    """Google Scholar via SerpAPI. Requires SERPAPI_API_KEY env var."""
    key = os.environ.get("SERPAPI_API_KEY")
    if not key:
        raise RuntimeError("SERPAPI_API_KEY env var not set")
    try:
        import requests
    except ImportError:
        raise RuntimeError("requests package not installed; pip install requests")
    params = {
        "engine": "google_scholar",
        "q": query,
        "api_key": key,
        "num": min(n, 20),
        "hl": "en",
    }
    r = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    out: list[dict] = []
    for entry in data.get("organic_results", [])[:n]:
        info = entry.get("publication_info", {}) or {}
        out.append({
            "title":   entry.get("title"),
            "authors": [a.get("name") for a in info.get("authors", []) if a.get("name")],
            "year":    _extract_year(info.get("summary", "")),
            "venue":   info.get("summary", ""),
            "url":     entry.get("link"),
            "doi":     None,  # SerpAPI doesn't return DOI directly
            "abstract": entry.get("snippet"),
            "raw":     entry,
        })
    return out


def search_scholarly(query: str, n: int = 10) -> list[dict]:
    """Free fallback via the `scholarly` package (Google Scholar scraping)."""
    try:
        from scholarly import scholarly  # type: ignore
    except ImportError:
        raise RuntimeError("scholarly package not installed; pip install scholarly")
    iterator = scholarly.search_pubs(query)
    out: list[dict] = []
    for _ in range(n):
        try:
            entry = next(iterator)
        except StopIteration:
            break
        bib = entry.get("bib", {})
        out.append({
            "title":   bib.get("title"),
            "authors": bib.get("author", []),
            "year":    int(bib["pub_year"]) if bib.get("pub_year", "").isdigit() else None,
            "venue":   bib.get("venue"),
            "url":     entry.get("pub_url"),
            "doi":     None,
            "abstract": bib.get("abstract"),
            "raw":     entry,
        })
        time.sleep(1.5)  # be kind to Google
    return out


def search_mock(query: str, n: int = 10, *, gap_id: str = "") -> list[dict]:
    """
    Deterministic synthetic harvester. For each query produces:
      - 60% on-topic empirical, 20% theoretical, 10% off-topic ML, 10% duplicates of earlier.
    Uses gap_id as seed so output is stable across runs.
    """
    rng = random.Random(hash(gap_id or query) & 0xFFFFFFFF)
    venues = ["Environment & Behavior", "Building & Environment", "J. Environ. Psychol.",
              "Frontiers in Psychology", "Sci. Rep.", "Nature Human Behaviour",
              "PNAS", "ICML Proceedings", "NeurIPS"]
    on_topic_terms = ["natural environment", "built environment", "indoor light",
                      "thermal comfort", "biophilic design", "circadian", "interoception",
                      "multisensory", "spatial memory", "olfactory", "social affiliation"]
    out: list[dict] = []
    for i in range(n):
        kind = rng.choices(["empirical", "theoretical", "ml", "dup"], weights=[6, 2, 1, 1])[0]
        year = rng.randint(2008, 2024)
        idx = rng.randint(1000, 9999)
        if kind == "ml":
            title = f"Deep learning approach to {rng.choice(['ImageNet', 'NLP', 'GAN'])} ({idx})"
            abstract = "Convolutional neural networks. Batch normalization. ImageNet."
            doi = None
            venue = rng.choice(["ICML Proceedings", "NeurIPS"])
        elif kind == "dup":
            title = f"Effects of {rng.choice(on_topic_terms)} on cognitive performance"
            abstract = "Repeated study (synthetic duplicate)."
            doi = None
            venue = rng.choice(venues[:6])
        else:
            term = rng.choice(on_topic_terms)
            verb = "modulates" if kind == "empirical" else "may modulate"
            title = (f"{term.capitalize()} {verb} attention and stress recovery "
                     f"in adults: a {kind} study ({idx})")
            abstract = (f"We investigated whether {term} influences attention restoration. "
                        f"{'Randomized controlled trial with N=' + str(rng.randint(40, 220)) if kind == 'empirical' else 'Conceptual review'}. "
                        f"Built environment, green space, biophilic design. p < 0.0{rng.randint(1,5)}.")
            doi = f"10.1234/synth.{gap_id.lower()}.{i}.{idx}" if rng.random() > 0.3 else None
            venue = rng.choice(venues[:7])
        out.append({
            "title":   title,
            "authors": [f"Author {chr(65 + rng.randint(0,25))}.", f"Author {chr(65 + rng.randint(0,25))}."],
            "year":    year,
            "venue":   venue,
            "url":     f"https://example.org/paper/{idx}",
            "doi":     doi,
            "abstract": abstract,
            "raw":     {"synthetic": True, "kind": kind},
        })
    return out


def _extract_year(s: str) -> int | None:
    import re
    m = re.search(r"\b(19|20)\d{2}\b", s or "")
    return int(m.group(0)) if m else None


# ─────────────────────────────────────────────────────────────────────────────
# Insert with dedupe-on-insert
# ─────────────────────────────────────────────────────────────────────────────
INSERT_SQL = """
INSERT INTO article_references (
    dedup_key, doi, title, authors, year, venue, url, abstract,
    source, source_query, source_query_kind, gap_id, framework_id, voi_score, raw_payload
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
ON CONFLICT(dedup_key) DO NOTHING
"""


def insert_records(conn: sqlite3.Connection, records: Iterable[dict],
                   *, source: str, source_query: str, source_query_kind: str,
                   gap_id: str, framework_id: str, voi_score: float) -> tuple[int, int]:
    seen, inserted = 0, 0
    for r in records:
        seen += 1
        key = make_dedup_key(r.get("doi"), r.get("title"))
        cur = conn.execute(INSERT_SQL, (
            key, r.get("doi"), r.get("title"),
            json.dumps(r.get("authors") or []),
            r.get("year"), r.get("venue"), r.get("url"), r.get("abstract"),
            source, source_query, source_query_kind, gap_id, framework_id, voi_score,
            json.dumps(r.get("raw") or {}),
        ))
        if cur.rowcount > 0:
            inserted += 1
    conn.commit()
    return seen, inserted


# ─────────────────────────────────────────────────────────────────────────────
# Driver
# ─────────────────────────────────────────────────────────────────────────────
def run(queries_path: Path, backend: str, per_query: int, top_n: int,
        db_path: Path) -> None:
    queries = json.loads(queries_path.read_text(encoding="utf-8"))[:top_n]
    conn = open_db(db_path)
    cur = conn.execute("INSERT INTO run_log(stage, n_in) VALUES ('search', ?)", (len(queries),))
    run_id = cur.lastrowid
    conn.commit()

    backend_fn = {"serpapi": search_serpapi, "scholarly": search_scholarly,
                  "mock": search_mock}.get(backend)
    if backend_fn is None:
        print(f"ERROR: unknown backend {backend}", file=sys.stderr)
        sys.exit(2)

    total_seen = total_inserted = 0
    for q in queries:
        bool_q = q["boolean_query"]
        gap_id = q["gap_id"]
        kwargs = {"gap_id": gap_id} if backend == "mock" else {}
        try:
            recs = backend_fn(bool_q, per_query, **kwargs)  # type: ignore[arg-type]
        except Exception as e:
            print(f"  [{gap_id}] backend error: {e}", file=sys.stderr)
            continue
        seen, ins = insert_records(
            conn, recs,
            source=backend, source_query=bool_q, source_query_kind="boolean",
            gap_id=gap_id, framework_id=q.get("framework_id", ""),
            voi_score=float(q.get("voi_score", 0.0)),
        )
        total_seen += seen
        total_inserted += ins
        print(f"  [{gap_id:<35}] harvested={seen:>3}  new={ins:>3}  ({backend})")

    conn.execute("UPDATE run_log SET finished_at=CURRENT_TIMESTAMP, n_out=?, "
                 "notes=? WHERE run_id=?",
                 (total_inserted,
                  f"backend={backend}; per_query={per_query}; total_seen={total_seen}",
                  run_id))
    conn.commit()
    conn.close()
    print(f"\nTotal: harvested={total_seen}, inserted (after dedupe)={total_inserted}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    p.add_argument("--backend", choices=["serpapi", "scholarly", "mock"], default="mock")
    p.add_argument("--per-query", type=int, default=10)
    p.add_argument("--top-n", type=int, default=10)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = p.parse_args()

    if not args.queries.exists():
        print(f"ERROR: {args.queries} not found", file=sys.stderr)
        sys.exit(1)
    run(args.queries, args.backend, args.per_query, args.top_n, args.db)


if __name__ == "__main__":
    main()
