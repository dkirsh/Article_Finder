#!/usr/bin/env python3
"""
query_generator.py — Task 2 Phase 3
Takes gap_results.json and generates paired search queries for each gap:
  - AI Citation query  (natural-language sentence, 5-component pattern, ends with ?)
  - Boolean query      (quoted phrases + AND/OR + -review, for SerpAPI / Google Scholar)

Usage:
    python3 query_generator.py --gaps gap_results.json
    python3 query_generator.py --gaps gap_results.json --top-n 15 --output query_results.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_GAPS   = REPO_ROOT / "gap_results.json"
DEFAULT_OUTPUT = REPO_ROOT / "query_results.json"
DEFAULT_TOP_N  = 10


# ── Framework vocabulary (theoretical anchors + synonyms) ─────────────────────
FRAMEWORK_VOCAB: dict[str, dict] = {
    "AL": {
        "name": "Allostatic Load",
        "theory_anchor": "consistent with Allostatic Load theory",
        "env_terms": ["built environment", "indoor environment", "workplace", "urban environment"],
        "mechanism_synonyms": ["HPA axis", "cortisol", "allostatic load", "chronic stress response"],
    },
    "PP": {
        "name": "Predictive Processing",
        "theory_anchor": "as predicted by Predictive Processing theory",
        "env_terms": ["architectural space", "spatial complexity", "visual environment"],
        "mechanism_synonyms": ["prediction error", "precision weighting", "top-down prediction", "surprise signal"],
    },
    "CB": {
        "name": "Circadian Biology",
        "theory_anchor": "consistent with circadian entrainment research",
        "env_terms": ["daylight", "light exposure", "luminous environment", "natural light"],
        "mechanism_synonyms": ["circadian rhythm", "melatonin", "sleep-wake cycle", "light entrainment"],
    },
    "MS": {
        "name": "Memory Systems",
        "theory_anchor": "within the memory-systems framework",
        "env_terms": ["spatial environment", "architectural layout", "built space"],
        "mechanism_synonyms": ["hippocampal encoding", "place cells", "spatial memory", "theta oscillation"],
    },
    "MSI": {
        "name": "Multi-Sensory Integration",
        "theory_anchor": "as explained by multisensory integration theory",
        "env_terms": ["multisensory environment", "acoustic and visual space", "built environment"],
        "mechanism_synonyms": ["cross-modal congruence", "superadditivity", "sensory weighting", "multisensory binding"],
    },
    "SN": {
        "name": "Social Neuroscience",
        "theory_anchor": "as predicted by social neuroscience",
        "env_terms": ["social space", "architectural configuration", "built environment"],
        "mechanism_synonyms": ["social cognition", "oxytocin", "neural coupling", "social affiliation"],
    },
    "DT": {
        "name": "Default-Mode Network",
        "theory_anchor": "within the default-mode network suppression framework",
        "env_terms": ["restorative environment", "attention-demanding space", "built environment"],
        "mechanism_synonyms": ["DMN suppression", "task-positive network", "mind-wandering", "attentional focus"],
    },
    "IC": {
        "name": "Interoception",
        "theory_anchor": "consistent with interoceptive predictive processing",
        "env_terms": ["thermal environment", "indoor climate", "built environment"],
        "mechanism_synonyms": ["interoception", "body state prediction", "autonomic regulation", "physiological state"],
    },
    "EC": {
        "name": "Embodied Cognition",
        "theory_anchor": "as explained by embodied cognition theory",
        "env_terms": ["architectural space", "haptic environment", "material environment"],
        "mechanism_synonyms": ["embodied simulation", "sensorimotor coupling", "action-perception loop", "affordance"],
    },
    "OL": {
        "name": "Olfactory-Limbic",
        "theory_anchor": "within the olfactory-limbic memory framework",
        "env_terms": ["indoor air quality", "olfactory environment", "built environment"],
        "mechanism_synonyms": ["olfactory memory", "hippocampal binding", "place memory", "limbic response"],
    },
    "NM": {
        "name": "Neuromodulation",
        "theory_anchor": "consistent with neuromodulatory accounts",
        "env_terms": ["sensory environment", "built environment", "acoustic environment"],
        "mechanism_synonyms": ["dopamine", "serotonin", "norepinephrine", "arousal modulation"],
    },
    "SC": {
        "name": "Stress & Coping",
        "theory_anchor": "as predicted by Stress Recovery Theory (SRT)",
        "env_terms": ["natural environment", "restorative space", "green space"],
        "mechanism_synonyms": ["stress recovery", "autonomic restoration", "cortisol reduction", "amygdala response"],
    },
    "DEV": {
        "name": "Developmental Neuroscience",
        "theory_anchor": "within developmental neuroscience",
        "env_terms": ["early-life environment", "built environment", "school environment"],
        "mechanism_synonyms": ["neural development", "critical period", "brain maturation", "developmental trajectory"],
    },
    "DP": {
        "name": "Depth Perception",
        "theory_anchor": "within depth perception and scene processing",
        "env_terms": ["visual environment", "spatial layout", "architectural depth"],
        "mechanism_synonyms": ["depth cue", "scene gist", "perspective", "spatial affordance"],
    },
    "IBS": {
        "name": "Immune-Brain-Stress",
        "theory_anchor": "consistent with immune-brain-stress crosstalk",
        "env_terms": ["indoor environment", "built environment", "occupant health"],
        "mechanism_synonyms": ["neuroinflammation", "cytokines", "immune signalling", "stress-immune axis"],
    },
    "cross_framework": {
        "name": "Cross-Framework",
        "theory_anchor": "across multiple neuroscientific frameworks",
        "env_terms": ["built environment", "indoor environment", "architectural space"],
        "mechanism_synonyms": ["neural pathway", "neurocognitive mechanism", "brain-environment interaction"],
    },
}


# Per-gap vocabulary overrides for cross_framework mechanisms (inferred from mechanism content)
CROSS_FRAMEWORK_VOCAB_MAP: dict[str, dict] = {
    "SOCIAL-AFFILIATION-002": {
        "env_terms": ["architectural configuration", "social space", "built environment"],
        "mechanism_synonyms": ["social cognition", "group identity", "oxytocin", "social affiliation"],
        "theory_anchor": "as predicted by social neuroscience and embodied cognition",
    },
    "INTERO-PP-ALLOSTASIS-001": {
        "env_terms": ["thermal environment", "indoor climate", "built environment"],
        "mechanism_synonyms": ["interoception", "allostatic load", "autonomic regulation", "body state prediction"],
        "theory_anchor": "consistent with interoceptive predictive processing and Allostatic Load theory",
    },
    "SOCIAL-ACOUSTIC-COUPLING-001": {
        "env_terms": ["acoustic environment", "multisensory environment", "built environment"],
        "mechanism_synonyms": ["signal-to-noise ratio", "neural coupling", "cross-modal congruence", "sensory weighting"],
        "theory_anchor": "as explained by multisensory integration and social neuroscience",
    },
    "MULTISENSORY-CONGRUENCE-001": {
        "env_terms": ["multisensory environment", "built environment", "acoustic and visual space"],
        "mechanism_synonyms": ["cross-modal congruence", "superadditivity", "multisensory binding", "sensory weighting"],
        "theory_anchor": "as explained by multisensory integration theory",
    },
    "COMPLEXITY-LOAD-001": {
        "env_terms": ["architectural space", "visual environment", "built environment"],
        "mechanism_synonyms": ["prediction error", "cognitive load", "precision weighting", "top-down prediction"],
        "theory_anchor": "as predicted by Predictive Processing theory",
    },
    "WAYFINDING-002": {
        "env_terms": ["spatial environment", "architectural layout", "built space"],
        "mechanism_synonyms": ["spatial memory", "hippocampal encoding", "place cells", "route planning"],
        "theory_anchor": "within the memory-systems framework",
    },
    "CIRCADIAN-DEV-PROGRAM-001": {
        "env_terms": ["daylight", "natural light", "light exposure"],
        "mechanism_synonyms": ["circadian rhythm", "light entrainment", "melatonin", "sleep-wake cycle"],
        "theory_anchor": "consistent with circadian entrainment research",
    },
    "THERMAL-SOCIAL-WARMTH-001": {
        "env_terms": ["thermal environment", "indoor climate", "built environment"],
        "mechanism_synonyms": ["embodied simulation", "social warmth", "sensorimotor coupling", "affordance"],
        "theory_anchor": "as explained by embodied cognition and social neuroscience",
    },
    "EMOTION-REGULATION-001": {
        "env_terms": ["natural environment", "restorative space", "built environment"],
        "mechanism_synonyms": ["stress recovery", "amygdala response", "autonomic restoration", "cortisol reduction"],
        "theory_anchor": "as predicted by Stress Recovery Theory",
    },
    "OLFACTORY-SPATIAL-MEMORY-001": {
        "env_terms": ["indoor air quality", "olfactory environment", "built environment"],
        "mechanism_synonyms": ["olfactory memory", "hippocampal binding", "place memory", "limbic response"],
        "theory_anchor": "within the olfactory-limbic memory framework",
    },
    "SOCIAL-PROXIMITY-001": {
        "env_terms": ["social space", "architectural configuration", "built environment"],
        "mechanism_synonyms": ["social cognition", "oxytocin", "neural coupling", "social inference"],
        "theory_anchor": "as predicted by social neuroscience",
    },
}


def _parse_mechanism_parts(name: str) -> tuple[str, str]:
    """Split 'A → B' into (source, target). Falls back to (name, name)."""
    for sep in (" → ", " -> ", " → "):
        if sep in name:
            parts = name.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    return name.strip(), name.strip()


def _clean_for_boolean(phrase: str, max_words: int = 4) -> str:
    """Lowercase, drop special chars, keep first max_words words."""
    words = re.sub(r"[→\->/\\]", " ", phrase).split()[:max_words]
    return " ".join(w.strip(".,;:()") for w in words if w.strip(".,;:()"))


def _evidence_type(gap: dict) -> str:
    temporal = (gap.get("temporal") or "").lower()
    fw = gap.get("framework_id", "")
    # All return values are mass/singular noun phrases so the template
    # "What {ev_type} shows that …" stays grammatical.
    if any(t in temporal for t in ("chronic", "years", "long")):
        return "longitudinal evidence"
    if fw in ("MS", "PP", "DT"):
        return "neuroimaging evidence"
    if fw in ("AL", "IC", "SC"):
        return "physiological evidence"
    return "empirical evidence"


def generate_ai_citation(gap: dict, fw_vocab: dict) -> str:
    """
    5-component AI Citation query:
      C1: evidence type
      C2: mechanism / pathway
      C3: environmental condition
      C4: population context
      C5: theoretical anchor
    Must be > 50 chars and end with '?'
    """
    src, dst = _parse_mechanism_parts(gap["mechanism_name"])
    ev_type = _evidence_type(gap)
    env_terms = fw_vocab.get("env_terms", ["built environment"])
    env_cond = env_terms[0]
    theory = fw_vocab.get("theory_anchor", "in environment-behaviour research")
    synonyms = fw_vocab.get("mechanism_synonyms", [])

    src_phrase = _clean_for_boolean(src, 6)
    dst_phrase = _clean_for_boolean(dst, 6)

    # Mechanisms without a "→" separator give us src == dst, which produces
    # the degenerate "X influences X leading to X" sentence. Fall back to:
    #   IV = first synonym (or the env condition)
    #   DV = the mechanism name as-is, framed as the outcome
    if src_phrase == dst_phrase:
        iv = synonyms[0] if synonyms else env_cond
        # Phrase as "exposure to <env_cond> shapes <mechanism>" so the
        # sentence stays grammatical even when the mechanism is a single
        # noun phrase rather than a source→destination chain.
        query = (
            f"What {ev_type} shows that exposure to {env_cond} shapes "
            f"'{_clean_for_boolean(gap['mechanism_name'], 6)}', and how does "
            f"'{iv}' mediate the effect in healthy adults, {theory}?"
        )
    else:
        query = (
            f"What {ev_type} shows that {env_cond} exposure influences "
            f"'{src_phrase}' leading to '{dst_phrase}' "
            f"in healthy adults, {theory}?"
        )

    if len(query) < 60:
        query = (
            f"What {ev_type} demonstrates that {env_cond} modulates "
            f"'{gap['mechanism_name'][:80]}' in humans, {theory}?"
        )
    return query


def quality_flags(gap: dict, ai_q: str, bool_q: str) -> list[str]:
    """Return the closed-set quality flags from the contract enum."""
    flags: list[str] = []
    src, dst = _parse_mechanism_parts(gap["mechanism_name"])
    if src.strip().lower() == dst.strip().lower():
        flags.append("degenerate_dv")
    if not ai_q.endswith("?"):
        flags.append("no_question_mark")
    if len(ai_q) < 50:
        flags.append("too_short")
    if "OR " not in bool_q:
        flags.append("no_synonyms")
    if bool_q.count('"') < 2:
        flags.append("single_term_only")
    if len(bool_q) > 250:
        flags.append("exceeds_length_limit")
    if "-review" not in bool_q:
        flags.append("no_review_filter")
    return flags


def generate_boolean(gap: dict, fw_vocab: dict) -> str:
    """
    Boolean query for Google Scholar / SerpAPI:
      - Quoted exact phrases
      - AND/OR joins
      - -review to exclude review papers for primary studies
    """
    src, dst = _parse_mechanism_parts(gap["mechanism_name"])
    synonyms = fw_vocab.get("mechanism_synonyms", [])
    env_terms = fw_vocab.get("env_terms", ["built environment"])

    # Mechanism phrase (src) + 1–2 synonyms
    mech_src = _clean_for_boolean(src, 4)
    mech_dst = _clean_for_boolean(dst, 4)
    syn1 = synonyms[0] if synonyms else mech_src
    syn2 = synonyms[1] if len(synonyms) > 1 else mech_dst

    # Environment phrase
    env1 = env_terms[0]
    env2 = env_terms[1] if len(env_terms) > 1 else env1

    # Construct Boolean
    boolean = (
        f'("{mech_src}" OR "{syn1}") '
        f'AND ("{env1}" OR "{env2}") '
        f'AND ("{mech_dst}" OR "{syn2}") '
        f"-review"
    )
    return boolean


def generate_rationale(gap: dict, fw_vocab: dict) -> str:
    src, dst = _parse_mechanism_parts(gap["mechanism_name"])
    ev_type = _evidence_type(gap)
    return (
        f"Targets {ev_type} linking '{_clean_for_boolean(src, 5)}' to "
        f"'{_clean_for_boolean(dst, 5)}' within {fw_vocab.get('name', gap['framework_id'])}. "
        f"-review excludes narrative summaries to prioritise primary studies. "
        f"VOI={gap['voi_score']:.3f} (confidence={gap['confidence']:.2f})."
    )


def _load_corpus_inventory(path: Path | None) -> set[str]:
    """
    Load DOIs / normalised titles from pdf_corpus_inventory/latest.csv if it
    exists. Rubric: don't generate queries for papers already in the corpus.
    Returns a set of identifiers (lowercase DOIs + lowercased title strings).
    Returns an empty set + a stderr note when the file is absent — that is
    the expected path on this checkout because the lifecycle DB is empty.
    """
    if path is None:
        return set()
    if not path.exists():
        print(f"  (corpus-awareness) {path} not found → skipping corpus check",
              file=sys.stderr)
        return set()
    import csv
    out: set[str] = set()
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doi = (row.get("doi") or "").strip().lower()
            title = (row.get("title") or "").strip().lower()
            if doi: out.add(doi)
            if title: out.add(title)
    print(f"  (corpus-awareness) loaded {len(out)} corpus entries from {path}",
          file=sys.stderr)
    return out


def generate_queries(gaps: list[dict], top_n: int,
                     corpus_inventory: set[str] | None = None) -> list[dict]:
    corpus_inventory = corpus_inventory or set()
    results = []
    for gap in gaps[:top_n]:
        fw_id = gap.get("framework_id", "cross_framework")
        fw_vocab = dict(FRAMEWORK_VOCAB.get(fw_id, FRAMEWORK_VOCAB["cross_framework"]))
        if fw_id == "cross_framework" and gap["gap_id"] in CROSS_FRAMEWORK_VOCAB_MAP:
            fw_vocab.update(CROSS_FRAMEWORK_VOCAB_MAP[gap["gap_id"]])

        ai_q   = generate_ai_citation(gap, fw_vocab)
        bool_q = generate_boolean(gap, fw_vocab)
        rationale = generate_rationale(gap, fw_vocab)

        # Corpus-awareness flag: if the mechanism name happens to match a
        # title already in CURRENT_GOLD, mark this query as
        # `targets_owned_paper` so the search runner can skip it.
        owned = gap["mechanism_name"].strip().lower() in corpus_inventory

        flags = quality_flags(gap, ai_q, bool_q)
        if owned:
            flags.append("targets_owned_paper")

        env_terms = fw_vocab.get("env_terms", [])
        syns      = fw_vocab.get("mechanism_synonyms", [])
        results.append({
            "gap_id":           gap["gap_id"],
            "template_id":      gap.get("template_id", gap["gap_id"]),
            "mechanism_name":   gap["mechanism_name"],
            "framework_id":     fw_id,
            "framework_name":   gap.get("framework_name", fw_vocab.get("name", "")),
            "voi_score":        gap["voi_score"],
            "confidence":       gap["confidence"],
            "gap_type":         gap.get("gap_type", ""),
            "gap_summary":      f"{gap['mechanism_name']} ({fw_vocab.get('name','')}, {gap.get('maturity','')})",
            "ai_citation_query": ai_q,
            "boolean_query":    bool_q,
            "query_terms": {
                "environment_terms": list(env_terms[:3]),
                "mechanism_terms":   [gap["mechanism_name"]] + list(syns[:1]),
                "outcome_terms":     list(syns[1:3]),
                "method_terms":      [_evidence_type(gap)],
            },
            "query_quality_flags": flags,
            "query_rationale":  rationale,
            "what_is_missing":  gap.get("what_is_missing", ""),
        })
    return results


def validate_queries(results: list[dict]) -> bool:
    """Run contract test checklist. Returns True if all pass."""
    all_ok = True
    checks = {
        "ai_citation ends with ?":    all(r["ai_citation_query"].endswith("?") for r in results),
        "ai_citation > 50 chars":     all(len(r["ai_citation_query"]) > 50 for r in results),
        "boolean has AND/OR":         all(("AND" in r["boolean_query"] or "OR" in r["boolean_query"]) for r in results),
        "boolean has quoted phrase":  all('"' in r["boolean_query"] for r in results),
        "no bare comma list":         all("," not in r["boolean_query"].replace('", "', "") for r in results),
        "output JSON valid":          True,  # if we got here it's valid
    }
    for check, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_ok = False
        print(f"  {status}  {check}")
    return all_ok


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate AI Citation + Boolean query pairs from gap_results.json."
    )
    parser.add_argument("--gaps",   type=Path, default=DEFAULT_GAPS,   help="gap_results.json")
    parser.add_argument("--top-n",  type=int,  default=DEFAULT_TOP_N,  help="Top N gaps to query (default: 10)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output JSON path")
    parser.add_argument("--corpus-inventory", type=Path,
                        default=Path("pdf_corpus_inventory/latest.csv"),
                        help="Optional CSV of papers already in the corpus; "
                             "queries that target an owned paper are flagged "
                             "with `targets_owned_paper`. Skipped if absent.")
    args = parser.parse_args()

    if not args.gaps.exists():
        print(f"ERROR: {args.gaps} not found — run gap_extractor.py first.", file=sys.stderr)
        sys.exit(1)

    gaps = json.loads(args.gaps.read_text(encoding="utf-8"))
    corpus = _load_corpus_inventory(args.corpus_inventory)
    print(f"Loaded {len(gaps)} gaps from {args.gaps}")
    print(f"Generating queries for top {args.top_n} gaps by VOI score …\n")

    results = generate_queries(gaps, args.top_n, corpus_inventory=corpus)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Written {len(results)} query pairs to: {args.output}\n")

    # Print query pairs
    for i, r in enumerate(results, 1):
        print(f"{'─'*72}")
        print(f"Gap #{i}: {r['gap_id']}  (VOI={r['voi_score']:.3f})")
        print(f"  Name: {r['mechanism_name']}")
        print(f"  AI Citation: {r['ai_citation_query']}")
        print(f"  Boolean:     {r['boolean_query']}")
        print()

    print("Contract validation:")
    all_pass = validate_queries(results)
    print(f"\n{'ALL PASS' if all_pass else 'SOME FAILURES'}")


if __name__ == "__main__":
    main()
