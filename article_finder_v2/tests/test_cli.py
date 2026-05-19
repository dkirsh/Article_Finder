"""CLI + export smoke tests, all offline (--no-network)."""
import json
from pathlib import Path
from article_finder.cli import main


def test_cli_no_network_smoke(tmp_path):
    rc = main([
        "search",
        "--topic", "circadian lighting attention adults",
        "--max-results", "5",
        "--queries-per-source", "1",
        "--enabled-sources", "openalex,crossref,arxiv",
        "--ai-backend", "none",
        "--no-network",
        "--output-dir", str(tmp_path),
    ])
    # Exit code 2 is expected because --no-network produces zero records
    # from every source, but the pipeline must still write its handoff files.
    assert rc in (0, 2, 3)

    expected = ["articles.json", "articles.csv", "download_report.json",
                "query_log.json", "dedup_report.json", "triage_report.md"]
    for name in expected:
        p = tmp_path / name
        assert p.exists(), f"missing handoff file: {name}"

    # JSON files must be parseable
    for name in ("articles.json", "download_report.json",
                  "query_log.json", "dedup_report.json"):
        json.loads((tmp_path / name).read_text())


def test_cli_rejects_empty_topic():
    rc = main([
        "search",
        "--enabled-sources", "openalex",
        "--ai-backend", "none",
        "--no-network",
        "--output-dir", "/tmp/_af_v2_empty_topic",
    ])
    assert rc == 1
