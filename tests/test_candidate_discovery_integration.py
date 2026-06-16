import json
from pathlib import Path

from candidate_discovery import (
    CandidateBuffer,
    OpenAlexCandidateSource,
    TargetSearch,
    candidate_to_paper,
    promote_candidates_to_af,
)
from candidate_discovery.oa_acquisition import register_browser_pdf
from candidate_discovery.run import run_target_discovery
from core.database import Database


def _pdf(path: Path) -> Path:
    path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    return path


def test_candidate_buffer_preserves_provenance_and_fuzzy_dedupes(tmp_path):
    buffer = CandidateBuffer(tmp_path / "candidates.db")

    ref1, action1 = buffer.add_candidate(
        {
            "title": "Effects of daylight on attention restoration in offices",
            "authors": ["Kaplan, R."],
            "year": 2024,
            "abstract": "A relevant abstract.",
        },
        discovered_via="openalex_search",
        discovered_query="daylight attention",
        target_id="Q-NATURE-ATTENTION",
        target_type="question",
        local_heuristic_voi=0.72,
    )
    ref2, action2 = buffer.add_candidate(
        {
            "title": "Effects of daylight on attention restoration in office settings",
            "authors": ["Kaplan, R."],
            "year": 2024,
        },
        discovered_via="semantic_scholar_search",
        discovered_query="daylight attention restoration",
    )

    assert action1 == "inserted"
    assert action2 == "dedup_title"
    assert ref2 == ref1

    row = buffer.fetchone(ref1)
    assert row is not None
    assert row["discovered_via"] == "openalex_search,semantic_scholar_search"


def test_browser_assisted_pdf_registration_records_sha_and_lifecycle(tmp_path):
    buffer = CandidateBuffer(tmp_path / "candidates.db")
    ref, _ = buffer.add_candidate(
        {"doi": "https://doi.org/10.1234/example", "title": "OA blocked paper"},
        discovered_via="openalex_search",
    )
    buffer.set_triage(ref, decision="ACCEPT", reason="on-topic", confidence=0.9)

    out = register_browser_pdf(buffer, ref, _pdf(tmp_path / "download.pdf"), tmp_path / "pdfs")

    assert out["reference_id"] == ref
    assert out["bytes"] > 0
    row = buffer.fetchone(ref)
    assert row["triage_stage"] == "acquired"
    assert row["pdf_path"].endswith(f"{ref}.pdf")
    assert row["pdf_sha256"] == out["sha256"]


def test_promote_candidates_maps_track2_decisions_to_af_vocabulary(tmp_path):
    buffer = CandidateBuffer(tmp_path / "candidates.db")
    af_db = Database(tmp_path / "af.db")

    accept_ref, _ = buffer.add_candidate(
        {
            "doi": "10.5555/accepted",
            "title": "Accepted daylight paper",
            "abstract": "An empirical daylight and attention paper.",
            "year": 2025,
        },
        discovered_via="openalex_search",
        target_id="Q-DAYLIGHT",
        target_type="question",
        local_heuristic_voi=0.8,
        voi_breakdown_json=json.dumps({"local_confidence_gap": 0.5}),
    )
    buffer.set_triage(accept_ref, decision="ACCEPT", reason="on-topic", confidence=0.91)

    edge_ref, _ = buffer.add_candidate(
        {"title": "Borderline attention paper", "abstract": "Related but not definitive."},
        discovered_via="crossref_search",
    )
    buffer.set_triage(edge_ref, decision="EDGE_CASE", reason="borderline", confidence=0.61)

    promoted_default = promote_candidates_to_af(buffer, af_db)
    assert promoted_default == ["doi:10.5555/accepted"]

    accepted = af_db.get_paper("doi:10.5555/accepted")
    assert accepted["triage_decision"] == "send_to_eater"
    assert accepted["status"] == "candidate"
    assert "on-topic" in accepted["triage_reasons"]
    assert accepted["tags"]["candidate_reference_id"] == accept_ref

    paper = candidate_to_paper(buffer.fetchone(edge_ref))
    assert paper["triage_decision"] == "review"
    assert paper["status"] == "candidate"


def test_openalex_target_discovery_harvests_triages_acquires_and_promotes(tmp_path):
    class FakeOpenAlexClient:
        def search_works(self, query, limit=10):
            assert query == "daylight attention office"
            assert limit == 3
            return [
                {
                    "doi": "10.1000/daylight",
                    "title": "Daylight exposure and attention in office work",
                    "abstract": "Daylight improved attention during office tasks.",
                    "year": 2026,
                    "venue": "Journal of Built Environment Cognition",
                    "url": "https://openalex.org/W1",
                    "oa_url": "https://example.test/daylight.pdf",
                    "open_access": True,
                    "cited_by_count": 12,
                    "source": "openalex",
                },
                {
                    "doi": "10.1000/noabstract",
                    "title": "Daylight and work",
                    "abstract": None,
                    "year": 2025,
                    "url": "https://openalex.org/W2",
                    "source": "openalex",
                },
                {
                    "doi": "10.1000/thermal",
                    "title": "Thermal comfort in offices",
                    "abstract": "Thermal comfort affected survey ratings.",
                    "year": 2024,
                    "url": "https://openalex.org/W3",
                    "source": "openalex",
                },
            ]

    def fake_pdf_fetch(url, headers, timeout):
        assert url == "https://example.test/daylight.pdf"
        assert "ArticleFinderCandidateDiscovery" in headers["User-Agent"]
        return 200, b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"

    summary = run_target_discovery(
        target=TargetSearch(
            query="daylight attention office",
            target_id="Q-DAYLIGHT-ATTENTION",
            local_heuristic_voi=0.77,
            voi_breakdown={"coverage_gap": 0.5, "decision_relevance": 0.27},
        ),
        candidate_db=tmp_path / "candidates.db",
        af_db=tmp_path / "af.db",
        accept_terms={"daylight", "attention", "office"},
        reject_terms={"thermal"},
        limit=3,
        source=OpenAlexCandidateSource(client=FakeOpenAlexClient()),
        acquire_pdfs=True,
        pdf_dir=tmp_path / "pdfs",
        pdf_fetch=fake_pdf_fetch,
    )

    assert len(summary["harvested"]) == 3
    decisions = {row["decision"] for row in summary["triage"]}
    assert decisions == {"ACCEPT", "MISSING_ABSTRACT", "REJECT"}
    assert len(summary["acquired_pdfs"]) == 1
    assert summary["promoted"] == ["doi:10.1000/daylight"]

    paper = Database(tmp_path / "af.db").get_paper("doi:10.1000/daylight")
    assert paper["status"] == "downloaded"
    assert paper["triage_decision"] == "send_to_eater"
    assert paper["url"] == "https://openalex.org/W1"
    assert paper["pdf_sha256"] == summary["acquired_pdfs"][0]["sha256"]
