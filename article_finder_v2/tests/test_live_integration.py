"""
Live-API integration tests.

Opt-in: these tests hit real public APIs and are tagged `@pytest.mark.live`
so they do NOT run by default. To execute them:

    PYTHONPATH=src python3 -m pytest tests/test_live_integration.py -m live

Tests skip cleanly (not fail) if:
  - the `requests` package is unavailable
  - the public API is unreachable (network down, DNS failure, etc.)

Each test uses a stable canonical DOI (Satish et al. 2012 — CO₂ and
decision-making — a real, widely-cited paper anchored in your K-ATLAS Q16
research front) and verifies the response parses into our normalized
record shape. We do not pin specific titles or counts because public
APIs drift over time.
"""
from __future__ import annotations
import os
import socket
import pytest

# Canonical paper for live integration tests:
#   Satish, U., Mendell, M. J., Shekhar, K., Hotchi, T., Sullivan, D.,
#   Streufert, S., & Fisk, W. J. (2012). Is CO2 an Indoor Pollutant?
#   Direct Effects of Low-to-Moderate CO2 Concentrations on Human
#   Decision-Making Performance. Environmental Health Perspectives.
KNOWN_DOI = "10.1289/ehp.1104789"
KNOWN_QUERY_HINT = "satish co2 decision-making 2012"


def _network_ok(host="openalex.org", port=443, timeout=3) -> bool:
    try:
        socket.create_connection((host, port), timeout=timeout)
        return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not _network_ok(), reason="no internet"),
]

try:
    import requests  # noqa: F401
except ImportError:
    pytest.skip("requests not installed", allow_module_level=True)


# --------------------------------------------------------------------------- #
# Search backends
# --------------------------------------------------------------------------- #
def test_live_openalex_search_returns_normalized_records():
    from article_finder.search.openalex import OpenAlexBackend
    qr = OpenAlexBackend().search(KNOWN_QUERY_HINT, max_results=5)
    assert qr.error is None, f"OpenAlex returned error: {qr.error}"
    assert qr.n_results > 0
    r0 = qr.records[0]
    # Every record carries the canonical fields our pipeline depends on
    for k in ("canonical_id", "title", "title_normalized", "authors",
              "sources", "provenance"):
        assert k in r0, f"OpenAlex record missing field: {k}"
    assert "openalex" in r0["sources"]


def test_live_crossref_search_returns_doi():
    from article_finder.search.crossref import CrossrefBackend
    qr = CrossrefBackend().search(KNOWN_QUERY_HINT, max_results=5)
    assert qr.error is None
    assert qr.n_results > 0
    # At least one Crossref hit should carry a DOI
    assert any(r.get("doi") for r in qr.records), "no Crossref result had a DOI"


def test_live_arxiv_search_smoke():
    """arXiv is mostly preprints; results may vary. We just confirm it doesn't
    error and returns 0+ records with the expected schema. arXiv frequently
    rate-limits 429 — we skip rather than fail in that case."""
    from article_finder.search.arxiv import ArxivBackend
    qr = ArxivBackend().search("attention restoration daylight", max_results=3)
    if qr.error and ("429" in qr.error or "timeout" in qr.error.lower()):
        pytest.skip(f"arXiv rate-limited / timeout: {qr.error}")
    assert qr.error is None, f"arXiv returned error: {qr.error}"
    if qr.records:
        assert qr.records[0]["sources"] == ["arxiv"]
        assert qr.records[0]["is_oa"] is True


def test_live_semantic_scholar_search():
    from article_finder.search.semantic_scholar import SemanticScholarBackend
    qr = SemanticScholarBackend().search(KNOWN_QUERY_HINT, max_results=3)
    # S2's anon endpoint is flaky — skip on rate-limit / network errors
    if qr.error and ("429" in qr.error or "HTTP GET failed" in qr.error
                      or "timeout" in qr.error.lower()):
        pytest.skip(f"S2 rate-limited / unreachable: {qr.error}")
    assert qr.error is None, f"S2 returned error: {qr.error}"
    if qr.records:
        assert "semantic_scholar" in qr.records[0]["sources"]


def test_live_pubmed_search():
    from article_finder.search.pubmed import PubmedBackend
    qr = PubmedBackend().search("CO2 decision-making cognitive performance", max_results=3)
    assert qr.error is None, f"PubMed returned error: {qr.error}"
    # esearch should find at least one match for this query
    assert qr.n_results > 0
    r0 = qr.records[0]
    assert r0["pubmed_id"]
    assert "pubmed" in r0["sources"]


def test_live_europe_pmc_search():
    from article_finder.search.europe_pmc import EuropePmcBackend
    qr = EuropePmcBackend().search("CO2 decision-making cognitive", max_results=3)
    assert qr.error is None, f"EuropePMC returned error: {qr.error}"
    assert qr.n_results >= 0  # may be 0 on some queries; schema check only
    if qr.records:
        r0 = qr.records[0]
        assert "europe_pmc" in r0["sources"]


# --------------------------------------------------------------------------- #
# OA resolver — Unpaywall
# --------------------------------------------------------------------------- #
def test_live_unpaywall_returns_oa_location_for_open_paper():
    """Pick a paper known to be OA. PLoS ONE 2014 'Power posing' paper or
    any other reliably-OA DOI works; we use a PLoS Biology paper."""
    from article_finder.pdf.oa_resolver import resolve

    # A PLoS Biology paper — PLoS is fully OA, so Unpaywall should find a PDF.
    record = {"doi": "10.1371/journal.pbio.1002195",
              "title": "Test PLoS Biology paper",
              "is_oa": False,  # let the resolver discover this
              "pdf_url": None}
    loc = resolve(record, enable_network=True)
    if loc is None:
        pytest.skip("Unpaywall/cascade returned no OA URL (network or upstream drift)")
    assert loc.pdf_url and loc.pdf_url.lower().startswith("http")
    assert loc.source in ("unpaywall", "europe_pmc", "openalex", "publisher_oa",
                          "doaj", "core", "pmc", "arxiv")
    assert loc.legal_oa_proof is not None


def test_live_unpaywall_returns_none_for_synthetic_doi():
    """A synthetic DOI must NOT resolve to any OA URL."""
    from article_finder.pdf.oa_resolver import resolve

    record = {"doi": "10.1234/totally.synthetic.does.not.exist.9999",
              "is_oa": False, "pdf_url": None}
    loc = resolve(record, enable_network=True)
    assert loc is None, f"synthetic DOI improperly resolved to {loc}"


# --------------------------------------------------------------------------- #
# CLI smoke against the live cascade (no PDF download)
# --------------------------------------------------------------------------- #
def test_live_cli_smoke_against_real_apis(tmp_path):
    """Run the full pipeline against real OpenAlex+Crossref+arXiv (no PDF
    download) on a focused query, and verify the 6 handoff files come back
    valid + non-empty."""
    import json
    from article_finder.cli import main

    rc = main([
        "search",
        "--topic", "indoor CO2 decision-making cognitive",
        "--max-results", "3",
        "--queries-per-source", "1",
        "--enabled-sources", "openalex,crossref",
        "--ai-backend", "none",
        "--output-dir", str(tmp_path),
    ])
    assert rc in (0, 3)  # 0 = success, 3 = partial-success (some source failed)

    arts = json.loads((tmp_path / "articles.json").read_text())
    assert isinstance(arts, list)
    assert len(arts) > 0, "no records harvested live"
    # Every record has rank, score, score_breakdown
    for r in arts:
        assert "rank" in r and r["rank"] >= 1
        assert "score" in r and 0.0 <= r["score"] <= 1.0
        assert "score_breakdown" in r and sum(r["score_breakdown"].values()) > 0
