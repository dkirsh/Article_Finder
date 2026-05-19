"""PDF downloader tests — no live network."""
import os
from pathlib import Path
import pytest
from article_finder.pdf.validators import (looks_like_pdf, safe_filename,
                                           ensure_safe_path, sha256,
                                           MIN_PDF_BYTES)
from article_finder.pdf.downloader import download_pdf


def test_looks_like_pdf_magic_bytes():
    assert looks_like_pdf(b"%PDF-1.4\n" + b"x" * (MIN_PDF_BYTES + 10))
    assert not looks_like_pdf(b"not a pdf")


def test_safe_filename_format():
    fn = safe_filename(2024, "Smith", "Daylight and attention", "10.1/x")
    assert fn.endswith(".pdf")
    assert "2024" in fn and "smith" in fn


def test_ensure_safe_path_rejects_traversal(tmp_path):
    with pytest.raises(ValueError):
        ensure_safe_path(tmp_path, "../escape.pdf")


def test_sha256_deterministic():
    assert sha256(b"hello") == sha256(b"hello")
    assert sha256(b"hello") != sha256(b"world")


def test_download_pdf_no_oa_returns_no_oa_pdf(tmp_path):
    """A record with no OA proof and no embedded pdf_url skips legally."""
    rec = {"canonical_id": "openalex:W1", "doi": "10.1/synth", "title": "T",
            "year": 2024, "is_oa": False, "pdf_url": None}
    res = download_pdf(rec, tmp_path, enable_network=False)
    assert res["pdf_status"] == "no_oa_pdf"
    assert res["local_pdf_path"] is None


def test_download_pdf_offline_skips_with_reason(tmp_path):
    """Record IS OA but network disabled → skipped_no_download."""
    rec = {"canonical_id": "openalex:W1", "doi": "10.1/x", "title": "T",
            "year": 2024, "is_oa": True,
            "pdf_url": "https://example.org/x.pdf",
            "first_author_surname": "smith"}
    res = download_pdf(rec, tmp_path, enable_network=False)
    assert res["pdf_status"] == "skipped_no_download"
    assert res["pdf_url"] == "https://example.org/x.pdf"


def test_download_pdf_already_exists_does_not_redownload(tmp_path):
    """Pre-place a file at the safe path; a second 'download' should detect it."""
    rec = {"canonical_id": "openalex:W1", "doi": "10.1/x", "title": "T",
            "year": 2024, "is_oa": True,
            "pdf_url": "https://example.org/x.pdf",
            "first_author_surname": "smith"}
    # Pre-create the target file with valid magic bytes
    fn = safe_filename(rec["year"], rec["first_author_surname"],
                        rec["title"], rec["doi"])
    (tmp_path / fn).write_bytes(b"%PDF-1.4\n" + b"x" * (MIN_PDF_BYTES + 1))

    res = download_pdf(rec, tmp_path, enable_network=False)
    assert res["pdf_status"] == "already_exists"
    assert res["pdf_sha256"]
    # Hash is stable across calls
    res2 = download_pdf(rec, tmp_path, enable_network=False)
    assert res["pdf_sha256"] == res2["pdf_sha256"]
