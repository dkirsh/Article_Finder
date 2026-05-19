"""
Per-abstract AI triage. Returns a score in [0, 1] and an explanation.

Backend strategy mirrors query_planner.py: deterministic fallback, optional
Anthropic or OpenAI when keys are configured. Always safe to call.
"""
from __future__ import annotations
import json
import os
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class TriageVerdict:
    score: float  # 0..1
    why_selected: str
    risks_or_limitations: list
    backend: str
    confidence: float
    raw_response: Optional[str] = None


def _deterministic(abstract: str, topic_terms: list[str]) -> TriageVerdict:
    if not abstract:
        return TriageVerdict(0.0, "no abstract available", ["missing_abstract"], "none", 0.0)
    txt = abstract.lower()
    hits = [t for t in topic_terms if t.lower() in txt]
    score = min(len(hits) / max(1, len(topic_terms)), 1.0) if topic_terms else 0.5
    why = f"abstract contains {len(hits)}/{len(topic_terms)} topic terms" + (
        f": {', '.join(hits[:5])}" if hits else "")
    risks = []
    if score < 0.3:
        risks.append("low_topic_overlap")
    if len(abstract.split()) < 50:
        risks.append("abstract_unusually_short")
    return TriageVerdict(score, why, risks, "none", 0.6 if topic_terms else 0.3)


def _llm_prompt(abstract: str, gap: str) -> str:
    return f"""You are triaging a paper for inclusion in a systematic literature search.

Research gap:
{gap}

Paper abstract:
{abstract}

Respond as JSON only:
{{
  "score": 0.0,                              // 0..1 relevance to the gap
  "why_selected": "one-sentence rationale",
  "risks_or_limitations": ["off_topic", "wrong_population", ...],
  "confidence": 0.0                          // your confidence in the score
}}
"""


def _from_llm(raw: str, backend: str) -> TriageVerdict:
    try:
        data = json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(m.group(0)) if m else {}
    return TriageVerdict(
        score=float(data.get("score") or 0.0),
        why_selected=str(data.get("why_selected") or "(no rationale provided)"),
        risks_or_limitations=list(data.get("risks_or_limitations") or []),
        backend=backend,
        confidence=float(data.get("confidence") or 0.5),
        raw_response=raw,
    )


def triage(abstract: str, gap: str, topic_terms: list[str],
           *, backend: str = "none") -> TriageVerdict:
    if backend == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            resp = client.messages.create(
                model="claude-sonnet-4-6", max_tokens=400,
                messages=[{"role": "user", "content": _llm_prompt(abstract, gap)}],
            )
            return _from_llm("".join(b.text for b in resp.content if hasattr(b, "text")),
                             "anthropic")
        except Exception:
            pass
    if backend == "openai" and os.environ.get("OPENAI_API_KEY"):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": _llm_prompt(abstract, gap)}],
                response_format={"type": "json_object"},
            )
            return _from_llm(resp.choices[0].message.content, "openai")
        except Exception:
            pass
    return _deterministic(abstract, topic_terms)
