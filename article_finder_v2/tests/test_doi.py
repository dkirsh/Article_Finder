"""DOI normalization / extraction tests."""
import pytest
from article_finder.metadata.doi import normalize_doi, extract_doi_from_text, is_valid_doi


@pytest.mark.parametrize("raw,expected", [
    ("https://doi.org/10.1038/ABC.123",                "10.1038/abc.123"),
    ("https://dx.doi.org/10.1038/s41562-020-0942-6",   "10.1038/s41562-020-0942-6"),
    ("doi:10.1145/1234567",                            "10.1145/1234567"),
    ("DOI: 10.1145/1234567",                           "10.1145/1234567"),
    ("  10.1037/abn0000123  ",                         "10.1037/abn0000123"),
    ("10.1037/abn0000123.",                            "10.1037/abn0000123"),
])
def test_normalize_doi_valid(raw, expected):
    assert normalize_doi(raw) == expected


@pytest.mark.parametrize("raw", [
    None, "", "  ", "not-a-doi", "10.1", "10/something",
    "https://example.com/no-doi-here",
])
def test_normalize_doi_invalid(raw):
    assert normalize_doi(raw) is None


def test_extract_doi_from_url():
    url = "https://www.springer.com/article/10.1007/s10548-019-00718-8?utm_x=1"
    assert extract_doi_from_text(url) == "10.1007/s10548-019-00718-8"


def test_is_valid_doi():
    assert is_valid_doi("10.1038/s41562-020-0942-6")
    assert not is_valid_doi("not-a-doi")
    assert not is_valid_doi(None)
