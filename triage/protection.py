"""Shared reject-protection guard for AF triage.

Centralizes the "never auto-reject" policy (AGENTS.md / docs/PRODUCTION_RUN.md)
so the interactive triage path (triage/scorer.py) honors the SAME allowlists that
scripts/production_run.py already enforces in batch. A paper whose venue is on the
HBE or neuroscience allowlist -- or, when a citation count is supplied, at/above the
high-citation floor -- must never receive an automatic 'reject'; it is downgraded to
'review' for a human decision, and the reason is recorded (PRISMA-style).

Defensive by construction: a missing allowlist file contributes no protections
(no crash, no behavior change). Paths resolve relative to the repo root, not CWD.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HBE_ALLOWLIST = _REPO_ROOT / "config" / "hbe_journals_allowlist.txt"
DEFAULT_NEURO_ALLOWLIST = _REPO_ROOT / "config" / "neuroscience_venues_allowlist.txt"
DEFAULT_HIGH_CITE_THRESHOLD = 150

_NEURO_RE = re.compile(r"\bneuro|\bbrain")


def normalize_venue(value: str | None) -> str:
    """Match scripts/production_run.normalize_venue exactly (lower/strip/&->and/ws)."""
    if not value:
        return ""
    value = value.lower().strip()
    value = value.replace("&", "and")
    value = re.sub(r"\s+", " ", value)
    return value


def load_allowlist(path: Path) -> set[str]:
    try:
        if not path or not path.exists():
            return set()
        out: set[str] = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.add(normalize_venue(line))
        return out
    except OSError:
        return set()


@lru_cache(maxsize=1)
def _default_allowlists() -> tuple[frozenset, frozenset]:
    return (
        frozenset(load_allowlist(DEFAULT_HBE_ALLOWLIST)),
        frozenset(load_allowlist(DEFAULT_NEURO_ALLOWLIST)),
    )


def venue_protected_reasons(venue: str | None) -> list:
    """Reasons a venue must not be auto-rejected (empty list = not protected)."""
    venue_norm = normalize_venue(venue)
    if not venue_norm:
        return []
    hbe, neuro = _default_allowlists()
    reasons = []
    if venue_norm in hbe:
        reasons.append("hbe_allowlist")
    if venue_norm in neuro or _NEURO_RE.search(venue_norm):
        reasons.append("neuroscience")
    return reasons


def protected_reasons(paper, *, citation_count=None,
                      high_cite_threshold: int = DEFAULT_HIGH_CITE_THRESHOLD) -> list:
    """Full protection reasons for a paper dict (venue + optional citation floor)."""
    reasons = venue_protected_reasons(paper.get("venue"))
    if citation_count is not None and citation_count >= high_cite_threshold:
        reasons.append(f"high_citation>={high_cite_threshold}")
    return reasons


def is_protected(paper, **kw) -> bool:
    return bool(protected_reasons(paper, **kw))
