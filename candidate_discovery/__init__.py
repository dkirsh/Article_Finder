"""Track-2-inspired candidate discovery layer for Article Finder.

This package is intentionally an adapter layer, not a replacement for the
canonical AF `papers` table or Article Eater job-bundle flow.
"""

from .buffer import CandidateBuffer, normalize_doi, normalize_title
from .adapters import candidate_to_paper, promote_candidates_to_af
from .sources import OpenAlexCandidateSource, TargetSearch
from .triage import KeywordCandidateTriage

__all__ = [
    "CandidateBuffer",
    "KeywordCandidateTriage",
    "OpenAlexCandidateSource",
    "TargetSearch",
    "candidate_to_paper",
    "normalize_doi",
    "normalize_title",
    "promote_candidates_to_af",
]
