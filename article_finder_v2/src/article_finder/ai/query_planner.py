"""
AI-assisted query planner — the v2 contribution.

Takes a research gap or topic and produces:
  - a structured decomposition (constructs, population, methods, outcomes,
    synonyms, exclusion terms)
  - source-specific queries for OpenAlex, Crossref, and arXiv
  - broad + narrow + citation-chasing variants

Backends:
  - "none"      — deterministic decomposition (no network). Always available.
  - "anthropic" — uses ANTHROPIC_API_KEY if set. Falls back to "none" on error.
  - "openai"    — uses OPENAI_API_KEY if set. Falls back to "none" on error.

NOT a Google Scholar wrapper. This is OUR planner.
"""
from __future__ import annotations
import json
import os
import re
from dataclasses import dataclass, asdict
from typing import List, Optional


@dataclass
class QueryPlan:
    gap: str
    constructs: List[str]
    population: List[str]
    methods: List[str]
    outcomes: List[str]
    synonyms: List[str]
    exclusions: List[str]
    queries: dict  # {"openalex": [...], "crossref": [...], "arxiv": [...]}
    confidence: float
    backend: str
    prompt: Optional[str] = None
    raw_response: Optional[str] = None

    def to_log(self) -> dict:
        return asdict(self)


STOPWORDS = {"the", "a", "an", "and", "or", "of", "for", "in", "on", "to", "with",
             "by", "is", "are", "what", "which", "how", "does", "do", "from"}


def _deterministic_plan(gap: str) -> QueryPlan:
    """Always-available fallback. Splits the gap into noun-phrase-ish tokens."""
    tokens = [t for t in re.findall(r"[A-Za-z][A-Za-z-]+", gap.lower())
              if t not in STOPWORDS and len(t) > 2]
    seen, uniq = set(), []
    for t in tokens:
        if t not in seen:
            seen.add(t); uniq.append(t)
    constructs = uniq[:5]
    quoted = [f'"{c}"' for c in constructs]

    boolean_broad = " AND ".join(quoted[:3]) if len(quoted) >= 3 else " AND ".join(quoted)
    boolean_narrow = " AND ".join(quoted)
    return QueryPlan(
        gap=gap,
        constructs=constructs,
        population=[],
        methods=[],
        outcomes=[],
        synonyms=[],
        exclusions=["review", "editorial", "commentary"],
        queries={
            "openalex":         [gap, boolean_broad],
            "crossref":         [gap, boolean_broad],
            "arxiv":            [gap, " ".join(constructs[:4])],
            "semantic_scholar": [gap, boolean_broad],
            "pubmed":           [gap, boolean_narrow],
            "europe_pmc":       [gap, boolean_broad],
        },
        confidence=0.4,
        backend="none",
        prompt=None,
        raw_response=None,
    )


def _anthropic_plan(gap: str, model: str = "claude-sonnet-4-6") -> QueryPlan:
    try:
        from anthropic import Anthropic
    except ImportError:
        return _deterministic_plan(gap)
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return _deterministic_plan(gap)
    client = Anthropic(api_key=key)
    prompt = _planner_prompt(gap)
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(b.text for b in resp.content if hasattr(b, "text"))
        return _parse_planner_response(gap, raw, "anthropic", prompt)
    except Exception:
        return _deterministic_plan(gap)


def _openai_plan(gap: str, model: str = "gpt-4o-mini") -> QueryPlan:
    try:
        from openai import OpenAI
    except ImportError:
        return _deterministic_plan(gap)
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return _deterministic_plan(gap)
    client = OpenAI(api_key=key)
    prompt = _planner_prompt(gap)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
        return _parse_planner_response(gap, raw, "openai", prompt)
    except Exception:
        return _deterministic_plan(gap)


def _planner_prompt(gap: str) -> str:
    return f"""You are a scholarly research librarian. Given a research gap, decompose it
into search dimensions and produce search queries for OpenAlex, Crossref, and arXiv.

Research gap:
{gap}

Respond as JSON only, with this exact shape:
{{
  "constructs":  ["...", ...],
  "population":  ["adults", ...],
  "methods":    ["fMRI", "RCT", ...],
  "outcomes":   ["attention", ...],
  "synonyms":   [["construct", "synonym1", "synonym2"], ...],
  "exclusions": ["review", "editorial", ...],
  "queries": {{
     "openalex":  ["natural-language broad query",
                    "boolean narrow query with AND/OR"],
     "crossref":  [...],
     "arxiv":    [...]
  }},
  "confidence": 0.0
}}

Do not include any prose outside the JSON object. Keep each query under 250 chars."""


def _parse_planner_response(gap: str, raw: str, backend: str, prompt: str) -> QueryPlan:
    try:
        data = json.loads(raw)
    except Exception:
        # Some LLMs wrap JSON in code fences
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return _deterministic_plan(gap)
        data = json.loads(m.group(0))

    return QueryPlan(
        gap=gap,
        constructs=list(data.get("constructs") or []),
        population=list(data.get("population") or []),
        methods=list(data.get("methods") or []),
        outcomes=list(data.get("outcomes") or []),
        synonyms=list(data.get("synonyms") or []),
        exclusions=list(data.get("exclusions") or []),
        queries=dict(data.get("queries") or {}),
        confidence=float(data.get("confidence") or 0.7),
        backend=backend,
        prompt=prompt,
        raw_response=raw,
    )


def plan_queries(gap: str, *, backend: str = "none") -> QueryPlan:
    """Public entrypoint. Picks the chosen backend; safe to call without keys."""
    if backend == "anthropic":
        return _anthropic_plan(gap)
    if backend == "openai":
        return _openai_plan(gap)
    return _deterministic_plan(gap)
