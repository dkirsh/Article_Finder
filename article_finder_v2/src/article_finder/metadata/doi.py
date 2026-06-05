"""
DOI extraction and normalization.

Strict — a DOI is `10.<registrant>/<suffix>` where registrant is 4-9 digits.
We never invent DOIs; if extraction fails, we return None.
"""
from __future__ import annotations
import re
from typing import Iterable, Optional

# Tighter than the Crossref-suggested regex: must start with 10., must contain /,
# must have at least one printable character after the /.
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")

_PREFIX_STRIPS = (
    "https://doi.org/", "http://doi.org/",
    "https://dx.doi.org/", "http://dx.doi.org/",
    "doi:", "DOI:", "doi: ",
)


def normalize_doi(raw: Optional[str]) -> Optional[str]:
    """Canonicalize a DOI string. Returns None for empty or clearly-invalid input."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    for p in _PREFIX_STRIPS:
        if s.lower().startswith(p.lower()):
            s = s[len(p):]
            break
    s = s.strip().strip("/").strip()
    s = s.rstrip(".,;)")
    s = s.lower()
    # Validate
    if not DOI_PATTERN.fullmatch(s):
        # Try one more salvage: maybe the input has whitespace inside
        m = DOI_PATTERN.search(s)
        if m:
            return m.group(0).lower()
        return None
    return s


def extract_doi_from_text(text: Optional[str]) -> Optional[str]:
    """Pull the first DOI out of free text or a URL. Returns normalized form."""
    if not text:
        return None
    m = DOI_PATTERN.search(str(text))
    if not m:
        return None
    return normalize_doi(m.group(0))


def extract_doi_from_url(url: Optional[str]) -> Optional[str]:
    """Extract a DOI from a publisher / repository URL."""
    if not url:
        return None
    # Common patterns: nature.com/articles/<doi-suffix-without-10-prefix>
    # Fall back to generic text extraction.
    return extract_doi_from_text(url)


def is_valid_doi(s: Optional[str]) -> bool:
    return bool(s) and DOI_PATTERN.fullmatch(s.lower()) is not None


def first_doi(candidates: Iterable[Optional[str]]) -> Optional[str]:
    """Return the first normalized DOI from an iterable."""
    for c in candidates:
        d = normalize_doi(c)
        if d:
            return d
    return None
