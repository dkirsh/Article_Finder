"""Deduplicator + merge tests."""
from article_finder.dedup.deduplicator import deduplicate
from article_finder.metadata.merge import merge_records


def _rec(**kw):
    base = {"canonical_id": None, "doi": None, "title": None,
            "authors": [], "first_author_surname": None, "year": None,
            "venue": None, "abstract": None, "is_oa": False,
            "sources": [], "provenance": {}}
    base.update(kw)
    return base


def test_same_doi_three_sources_collapses_to_one():
    a = _rec(doi="10.1/x", title="A title", sources=["openalex"],
              provenance={"openalex": {"id": "W1"}})
    b = _rec(doi="10.1/x", title="A title", sources=["crossref"],
              provenance={"crossref": {"doi": "10.1/x"}})
    c = _rec(doi="10.1/x", title="A title", sources=["arxiv"],
              provenance={"arxiv": {"id": "2103.01"}})
    out, report = deduplicate([a, b, c])
    assert len(out) == 1
    assert sorted(out[0]["sources"]) == ["arxiv", "crossref", "openalex"]
    assert report[0]["member_count"] == 3


def test_title_capitalization_dedups():
    a = _rec(title="Effects of Daylight on Attention", sources=["openalex"])
    b = _rec(title="EFFECTS OF DAYLIGHT ON ATTENTION", sources=["arxiv"])
    out, _ = deduplicate([a, b])
    assert len(out) == 1


def test_title_plus_author_plus_year_dedups():
    a = _rec(title="Circadian lighting and attention",
              first_author_surname="kim", year=2020, sources=["openalex"])
    b = _rec(title="Circadian lighting and attention in adults",
              first_author_surname="kim", year=2021, sources=["crossref"])
    out, _ = deduplicate([a, b])
    assert len(out) == 1


def test_different_papers_with_similar_topic_do_not_merge():
    a = _rec(title="Daylight and attention restoration",
              first_author_surname="smith", year=2015, sources=["openalex"])
    b = _rec(title="Daylight and circadian rhythm entrainment",
              first_author_surname="jones", year=2018, sources=["openalex"])
    out, _ = deduplicate([a, b])
    assert len(out) == 2


def test_merge_preserves_longer_abstract():
    a = _rec(doi="10.1/x", abstract="Short.", sources=["a"])
    b = _rec(doi="10.1/x", abstract="A much longer abstract with details.",
              sources=["b"])
    m = merge_records(a, b)
    assert "longer" in m["abstract"]
