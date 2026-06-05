#!/usr/bin/env python3
"""
abstract_collector.py — Task 3 Phase 4B (Stage 2A).

Walks the abstract fallback chain ONLY for rows that survived Stage 1
(triage_stage='metadata_only', not yet rejected_at_metadata):

    Semantic Scholar → CrossRef → PubMed → OpenAlex

Records `abstract_source` per row. If the snippet from search_runner already
qualifies as an abstract (≥120 chars), uses it as-is and tags it
abstract_source='search_payload' (this is the canonical mock-mode behaviour and
also the fallback when no DOI is available).

Papers with no abstract from any source get triage_decision='MISSING_ABSTRACT'
(rubric §4C — never silently dropped).

Rate limits respected: ≤20 req/min when calling Semantic Scholar without a key.
DOI and title fallback handled. Ambiguous title matches (>1 candidate above
the threshold) are NOT blindly accepted — they fall through to the next source.

Usage:
    python3 abstract_collector.py
    python3 abstract_collector.py --enable-network   # actually call S2/CrossRef/etc
"""

from __future__ import annotations
import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path

from db_schema import open_db, DEFAULT_DB, log_transition

ABSTRACT_MIN_CHARS = 120

# Polite-pool contact for CrossRef / OpenAlex. Override per deployment with
# CONTACT_EMAIL env var; never commit a personal address as a default.
CONTACT_EMAIL = os.environ.get(
    "CONTACT_EMAIL", "cogs160-track2@knowledge-atlas.local"
)
USER_AGENT = f"ArticleFinderTrack2/1.0 (mailto:{CONTACT_EMAIL})"


# ─────────────────────────────────────────────────────────────────────────────
# Source clients (network calls gated behind --enable-network)
# ─────────────────────────────────────────────────────────────────────────────
def fetch_s2(doi: str | None, title: str | None) -> str | None:
    if not (doi or title): return None
    import requests
    base = "https://api.semanticscholar.org/graph/v1/paper"
    try:
        if doi:
            r = requests.get(f"{base}/DOI:{doi}", params={"fields": "abstract"},
                             timeout=15)
            if r.status_code == 200:
                return (r.json() or {}).get("abstract")
        # title search — accept only single high-confidence match
        r = requests.get(f"{base}/search", params={"query": title, "limit": 2,
                                                    "fields": "abstract,title"},
                         timeout=15)
        data = r.json() if r.status_code == 200 else {"data": []}
        hits = data.get("data") or []
        if len(hits) == 1 and hits[0].get("abstract"):
            return hits[0]["abstract"]
        return None
    except Exception:
        return None


def fetch_crossref(doi: str | None) -> str | None:
    if not doi: return None
    import requests
    try:
        r = requests.get(f"https://api.crossref.org/works/{doi}", timeout=15,
                         headers={"User-Agent": USER_AGENT})
        if r.status_code == 200:
            msg = r.json().get("message", {})
            abstract = msg.get("abstract") or ""
            # CrossRef abstracts are JATS-XML wrapped — strip tags
            import re
            return re.sub(r"<[^>]+>", " ", abstract).strip() or None
    except Exception:
        pass
    return None


def fetch_pubmed(title: str | None) -> str | None:
    if not title: return None
    import requests
    try:
        r = requests.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                         params={"db": "pubmed", "term": title, "retmax": 2,
                                 "retmode": "json"}, timeout=15)
        ids = (r.json().get("esearchresult", {}) or {}).get("idlist", []) if r.status_code == 200 else []
        if len(ids) != 1: return None
        r2 = requests.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                          params={"db": "pubmed", "id": ids[0], "rettype": "abstract",
                                  "retmode": "text"}, timeout=15)
        if r2.status_code == 200 and len(r2.text) > ABSTRACT_MIN_CHARS:
            return r2.text.strip()
    except Exception:
        pass
    return None


def fetch_openalex(doi: str | None) -> str | None:
    if not doi: return None
    import requests
    try:
        r = requests.get(f"https://api.openalex.org/works/doi:{doi}",
                         params={"mailto": CONTACT_EMAIL}, timeout=15)
        if r.status_code != 200: return None
        inv = (r.json() or {}).get("abstract_inverted_index") or {}
        if not inv: return None
        # Reconstruct abstract from inverted index
        positions: dict[int, str] = {}
        for word, idxs in inv.items():
            for i in idxs: positions[i] = word
        return " ".join(positions[i] for i in sorted(positions))
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Main collector
# ─────────────────────────────────────────────────────────────────────────────
def collect_one(conn: sqlite3.Connection, ref_id: str, doi: str | None,
                title: str | None, snippet: str | None,
                enable_network: bool) -> tuple[str | None, str]:
    """Returns (abstract, source_label)."""
    # Stage 0 — search snippet large enough to count as abstract
    if snippet and len(snippet) >= ABSTRACT_MIN_CHARS:
        return snippet, "search_payload"
    if not enable_network:
        return None, "none"

    for fn, label in [(lambda: fetch_s2(doi, title),     "s2"),
                      (lambda: fetch_crossref(doi),      "crossref"),
                      (lambda: fetch_pubmed(title),      "pubmed"),
                      (lambda: fetch_openalex(doi),      "openalex")]:
        text = fn()
        time.sleep(3.5)  # ≤20 req/min on S2 free tier; safe for others too
        if text and len(text) >= ABSTRACT_MIN_CHARS:
            return text, label
    return None, "none"


def run(db_path: Path, enable_network: bool) -> dict:
    conn = open_db(db_path)
    cur = conn.execute(
        "INSERT INTO run_log (stage, notes) VALUES ('collect_abstract', ?)",
        (f"network={'on' if enable_network else 'off'}",))
    run_id = cur.lastrowid; conn.commit()

    rows = conn.execute(
        "SELECT reference_id, doi, title_raw, snippet FROM article_references "
        "WHERE triage_stage = 'metadata_only' AND triage_decision IS NULL "
        "AND abstract IS NULL"
    ).fetchall()

    counts = {"considered": len(rows), "found": 0, "missing": 0,
              "by_source": {}}
    for r in rows:
        text, src = collect_one(conn, r["reference_id"], r["doi"],
                                r["title_raw"], r["snippet"], enable_network)
        if text:
            conn.execute(
                "UPDATE article_references SET abstract=?, abstract_source=?, "
                "triage_stage='abstract_collected', "
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE reference_id=?", (text, src, r["reference_id"]))
            log_transition(conn, reference_id=r["reference_id"],
                           from_stage="metadata_only",
                           to_stage="abstract_collected",
                           agent="abstract_collector", outcome="success",
                           notes=f"source={src}")
            counts["found"] += 1
            counts["by_source"][src] = counts["by_source"].get(src, 0) + 1
        else:
            conn.execute(
                "UPDATE article_references SET abstract_source='none', "
                "triage_decision='MISSING_ABSTRACT', "
                "triage_reason='no abstract from S2/CrossRef/PubMed/OpenAlex', "
                "triage_stage='abstract_collected', "
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE reference_id=?", (r["reference_id"],))
            log_transition(conn, reference_id=r["reference_id"],
                           from_stage="metadata_only",
                           to_stage="abstract_collected",
                           agent="abstract_collector", outcome="missing",
                           notes="all sources empty")
            counts["missing"] += 1
    conn.commit()
    import json
    conn.execute(
        "UPDATE run_log SET finished_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'), "
        "n_in=?, n_out=?, notes=? WHERE run_id=?",
        (counts["considered"], counts["found"], json.dumps(counts), run_id))
    conn.commit(); conn.close()
    print(f"Abstract collection: considered={counts['considered']} "
          f"found={counts['found']} missing={counts['missing']} "
          f"by_source={counts['by_source']}")
    return counts


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--enable-network", action="store_true",
                   help="Allow real S2/CrossRef/PubMed/OpenAlex calls")
    args = p.parse_args()
    run(args.db, args.enable_network)


if __name__ == "__main__":
    main()
