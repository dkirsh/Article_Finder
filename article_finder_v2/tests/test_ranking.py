"""Ranking and scoring tests."""
from article_finder.ranking.scorer import score_record, rank_records, WEIGHTS


def _rec(**kw):
    base = {"canonical_id": "x", "doi": None, "title": "", "abstract": "",
            "year": None, "is_oa": False, "pdf_url": None,
            "cited_by_count": 0, "sources": []}
    base.update(kw); return base


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_pdf_availability_increases_score():
    no_pdf = _rec(doi="10.1/x", abstract="x", is_oa=False, pdf_url=None)
    has_pdf = _rec(doi="10.1/x", abstract="x", is_oa=True,
                    pdf_url="https://example.org/x.pdf")
    s1 = score_record(no_pdf, topic_terms=set())["score"]
    s2 = score_record(has_pdf, topic_terms=set())["score"]
    assert s2 > s1


def test_score_breakdown_sums_to_score():
    r = _rec(doi="10.1/x", abstract="x", is_oa=True,
              pdf_url="https://example.org/x.pdf", year=2024,
              cited_by_count=42, sources=["openalex", "crossref"])
    s = score_record(r, topic_terms=set(["nothing"]))
    total = sum(s["score_breakdown"].values())
    assert abs(total - s["score"]) < 1e-6


def test_ranking_is_deterministic():
    rs = [_rec(canonical_id=f"x{i}", doi=f"10.1/{i}", title="t",
                year=2020 + (i % 3), abstract="x") for i in range(10)]
    r1 = rank_records(rs, topic_terms=set(["t"]))
    r2 = rank_records(rs, topic_terms=set(["t"]))
    assert [r["canonical_id"] for r in r1] == [r["canonical_id"] for r in r2]
    # All ranks are unique and contiguous
    ranks = [r["rank"] for r in r1]
    assert ranks == list(range(1, len(r1) + 1))


def test_topic_match_contributes():
    on_topic = _rec(title="daylight attention", abstract="daylight attention adults")
    off_topic = _rec(title="machine learning",  abstract="deep neural networks")
    terms = {"daylight", "attention"}
    s_on = score_record(on_topic, topic_terms=terms)["score"]
    s_off = score_record(off_topic, topic_terms=terms)["score"]
    assert s_on > s_off
