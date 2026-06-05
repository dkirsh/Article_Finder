"""
Title / author / venue normalization for fuzzy dedup.
"""
from __future__ import annotations
import re
import unicodedata
from typing import Optional


def normalize_title(title: Optional[str]) -> Optional[str]:
    if not title:
        return None
    # Unicode normalize, strip accents
    s = unicodedata.normalize("NFKD", str(title))
    s = "".join(c for c in s if not unicodedata.combining(c))
    # Lowercase, collapse whitespace, strip punctuation except inner hyphens
    s = s.lower()
    s = re.sub(r"[^\w\s-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def normalize_surname(name: Optional[str]) -> Optional[str]:
    """Take "Surname, F." or "First Middle Last" and return lowercase surname."""
    if not name:
        return None
    s = str(name).strip()
    # "Surname, First M."  -> "surname"
    if "," in s:
        return s.split(",", 1)[0].strip().lower() or None
    # "First M. Last"  -> "last"
    parts = s.split()
    return parts[-1].strip(".").lower() if parts else None


def normalize_venue(venue: Optional[str]) -> Optional[str]:
    if not venue:
        return None
    s = unicodedata.normalize("NFKD", str(venue))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s&-]", " ", s.lower())
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def first_author_surname(authors) -> Optional[str]:
    """authors: list of strings or list of {"name": "..."} dicts."""
    if not authors:
        return None
    first = authors[0]
    if isinstance(first, dict):
        first = first.get("name") or first.get("family") or first.get("given", "") + " " + first.get("family", "")
    return normalize_surname(first)


_TITLE_STOPWORDS = {"a", "an", "the", "and", "or", "of", "for", "in", "on",
                     "to", "with", "by", "from", "is", "are", "as", "at",
                     "into", "their", "its"}


def _title_tokens(s: Optional[str]) -> set[str]:
    n = normalize_title(s)
    if not n:
        return set()
    return {t for t in n.split() if t not in _TITLE_STOPWORDS and len(t) > 2}


def title_similarity(a: Optional[str], b: Optional[str]) -> float:
    """
    Token-Jaccard with stopwords removed. Cheap and adequate for dedup screening.
    """
    sa, sb = _title_tokens(a), _title_tokens(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def title_overlap(a: Optional[str], b: Optional[str]) -> float:
    """
    Overlap coefficient (intersection / smaller set). Catches the case where
    one title is a longer phrasing of the other ('X' vs 'X in adults').
    """
    sa, sb = _title_tokens(a), _title_tokens(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / min(len(sa), len(sb))
