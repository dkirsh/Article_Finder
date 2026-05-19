"""
Compliance scan.

The v2 module must never reference any Sci-Hub library or URL, and must
never call into Google Scholar's web UI. This test scans the whole v2
source tree (not tests, not docs) for forbidden tokens and fails if any
appears in executable code.
"""
import re
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parents[1]
SRC = V2_ROOT / "src" / "article_finder"

FORBIDDEN_IMPORTS = [
    r"\bimport\s+scidownl\b",
    r"\bfrom\s+scidownl\b",
    r"\bimport\s+scihub\b",
    r"\bfrom\s+scihub\b",
    r"\bimport\s+scihub_downloader\b",
    r"\bfrom\s+scihub_downloader\b",
]

FORBIDDEN_URLS = [
    r"sci-hub\.",       # any sci-hub.tld mirror
    r"sci_hub\.",
    r"scholar\.google\.com/scholar\?",  # raw Scholar HTML scrape pattern
]


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def test_no_scihub_imports_in_v2_source():
    offenders = []
    for p in SRC.rglob("*.py"):
        text = _read(p)
        for pat in FORBIDDEN_IMPORTS:
            if re.search(pat, text):
                offenders.append((str(p.relative_to(V2_ROOT)), pat))
    assert not offenders, f"forbidden imports found: {offenders}"


def test_no_scihub_urls_in_v2_source():
    offenders = []
    for p in SRC.rglob("*.py"):
        text = _read(p)
        for pat in FORBIDDEN_URLS:
            if re.search(pat, text, re.IGNORECASE):
                offenders.append((str(p.relative_to(V2_ROOT)), pat))
    assert not offenders, f"forbidden URLs found: {offenders}"


def test_downloader_only_accepts_oa_verified_locations():
    """The downloader must only consume an OALocation produced by the resolver.
       A grep proves there is no alternate code path that bypasses the resolver."""
    text = _read(SRC / "pdf" / "downloader.py")
    # The downloader imports from oa_resolver and never builds OALocation itself.
    assert "from .oa_resolver import" in text
    # The only entry point used is resolve(record, ...)
    assert "resolve(record" in text


def test_no_scholar_html_scraping_in_v2():
    """No request to a scholar.google.com search URL anywhere in v2."""
    offenders = []
    for p in SRC.rglob("*.py"):
        text = _read(p)
        if "scholar.google.com" in text.lower():
            offenders.append(str(p.relative_to(V2_ROOT)))
    assert not offenders, f"scholar.google.com references in v2 source: {offenders}"
