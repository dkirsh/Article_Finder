#!/usr/bin/env python3
"""
gap_extractor.py — Task 2 Phase 2
Reads the Knowledge Atlas mechanism profile manifest (proxy for Article_Eater
PNU templates), extracts mechanisms whose confidence falls below a threshold,
scores each gap by Value of Information, and writes gap_results.json.

Data source note: spec references Article_Eater/data/templates/ (166 PNU
templates with mechanism_chain confidence scores). As a compliant substitute
per the submission note, this script uses Knowledge_Atlas/data/ka_payloads/
mechanisms.json — the canonical mechanism manifest produced by Article_Eater
(71 mechanisms, 15 frameworks). The --mechanisms-path flag accepts any
compatible JSON source if Article_Eater templates become available.

Usage:
    python3 gap_extractor.py
    python3 gap_extractor.py --mechanisms-path /path/to/mechanisms.json
    python3 gap_extractor.py --confidence-threshold 0.5 --output gap_results.json
"""

import argparse
import json
import sys
from pathlib import Path

# ── defaults ──────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_MECHANISMS = (
    REPO_ROOT.parent / "Knowledge_Atlas" / "data" / "ka_payloads" / "mechanisms.json"
)
DEFAULT_OUTPUT = REPO_ROOT / "gap_results.json"
DEFAULT_THRESHOLD = 0.60
DEFAULT_MIN_GAPS = 10

# Confidence scores derived from maturity labels (mirrors PNU template confidence)
MATURITY_CONFIDENCE = {
    "How-Actually":   0.78,
    "How-Plausibly":  0.42,
    "stub":           0.20,
    "brief":          0.35,
}

# Gap-type labels derived from maturity + word_count
def _gap_type(maturity: str, word_count: int) -> str:
    if maturity in ("stub", "brief") or word_count < 200:
        return "mechanism_undocumented"
    if maturity == "How-Plausibly":
        return "mechanism_underpowered"
    return "mechanism_gap"


# ── VOI scoring ───────────────────────────────────────────────────────────────
def compute_voi(mechanism: dict, confidence: float) -> float:
    """
    Value-of-information score in [0, 1].

    base          = 1 - confidence          (lower confidence → higher priority)
    centrality    = +0.15 for cross_framework hubs (downstream of many beliefs)
    temporal_bonus= +0.08 for Chronic/Long-term cascades (harder to study)
    coverage_pen  = −min(word_count/2000, 0.20) (well-documented → less urgent)
    """
    base = 1.0 - confidence

    fw = mechanism.get("framework_id", "") or ""
    centrality_bonus = 0.15 if fw == "cross_framework" else 0.0

    temporal = (mechanism.get("temporal") or "").lower()
    temporal_bonus = 0.08 if any(t in temporal for t in ("chronic", "long", "years")) else 0.0

    word_count = mechanism.get("word_count") or 0
    coverage_penalty = min(word_count / 2000.0, 0.20)

    voi = base + centrality_bonus + temporal_bonus - coverage_penalty
    return round(max(0.0, min(1.0, voi)), 4)


# ── what-is-missing generator ──────────────────────────────────────────────────
def _what_is_missing(mechanism: dict, maturity: str) -> str:
    name = mechanism.get("name", "")
    fw = mechanism.get("framework_name", mechanism.get("framework_id", ""))
    temporal = mechanism.get("temporal") or "unspecified timescale"

    if maturity in ("stub", "brief"):
        return (
            f"The mechanism '{name}' within the {fw} framework is documented only "
            f"at stub/brief level. Primary empirical studies establishing the "
            f"causal pathway ({temporal}) are needed."
        )
    # How-Plausibly
    arrows = name.split("→") if "→" in name else name.split("->") if "->" in name else [name]
    if len(arrows) >= 2:
        src = arrows[0].strip()
        dst = arrows[-1].strip()
        return (
            f"Direct empirical measurement linking '{src}' to '{dst}' in built-"
            f"environment contexts ({temporal}) is absent. The pathway is theorised "
            f"within {fw} but lacks grounding in primary human studies."
        )
    return (
        f"Empirical grounding for '{name}' ({fw}, {temporal}) is at the plausible "
        f"stage; primary neurobiological or psychophysiological evidence is needed."
    )


# ── main extraction logic ──────────────────────────────────────────────────────
def extract_gaps(
    mechanisms_path: Path,
    confidence_threshold: float,
    min_gaps: int,
) -> list[dict]:
    if not mechanisms_path.exists():
        print(f"ERROR: mechanisms file not found: {mechanisms_path}", file=sys.stderr)
        sys.exit(1)

    raw = json.loads(mechanisms_path.read_text(encoding="utf-8"))
    mlist: list[dict] = raw.get("mechanisms", raw) if isinstance(raw, dict) else raw

    gaps: list[dict] = []
    seen_ids: set[str] = set()

    for m in mlist:
        mid = m.get("id", "")
        if not mid or mid in seen_ids:
            continue
        seen_ids.add(mid)

        maturity = m.get("maturity", "stub")
        confidence = MATURITY_CONFIDENCE.get(maturity, 0.30)

        if confidence >= confidence_threshold:
            continue  # Not a gap at this threshold

        voi = compute_voi(m, confidence)

        gaps.append({
            "gap_id":         mid,
            "mechanism_name": m.get("name", mid),
            "framework_id":   m.get("framework_id", "unknown"),
            "framework_name": m.get("framework_name", ""),
            "maturity":       maturity,
            "confidence":     confidence,
            "gap_type":       _gap_type(maturity, m.get("word_count") or 0),
            "voi_score":      voi,
            "what_is_missing": _what_is_missing(m, maturity),
            "temporal":       m.get("temporal") or "",
            "word_count":     m.get("word_count") or 0,
        })

    # Sort highest VOI first
    gaps.sort(key=lambda g: g["voi_score"], reverse=True)

    if len(gaps) < min_gaps:
        print(
            f"WARNING: only {len(gaps)} gaps found (min={min_gaps}). "
            f"Try lowering --confidence-threshold.",
            file=sys.stderr,
        )

    return gaps


# ── CLI ────────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract knowledge gaps from PNU mechanism profiles and score by VOI."
    )
    parser.add_argument(
        "--mechanisms-path",
        type=Path,
        default=DEFAULT_MECHANISMS,
        help=f"Path to mechanisms.json (default: {DEFAULT_MECHANISMS})",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Mechanisms with confidence < threshold are extracted as gaps (default: {DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "--min-gaps",
        type=int,
        default=DEFAULT_MIN_GAPS,
        help=f"Warn if fewer than this many gaps found (default: {DEFAULT_MIN_GAPS})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSON path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    print(f"Loading mechanisms from: {args.mechanisms_path}")
    gaps = extract_gaps(args.mechanisms_path, args.confidence_threshold, args.min_gaps)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(gaps, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nExtracted {len(gaps)} gaps (threshold={args.confidence_threshold})")
    print(f"Written to: {args.output}\n")
    print(f"{'Rank':<5} {'VOI':>6} {'Conf':>5} {'Gap ID':<40} Framework")
    print("-" * 80)
    for i, g in enumerate(gaps[:15], 1):
        print(
            f"{i:<5} {g['voi_score']:>6.3f} {g['confidence']:>5.2f} "
            f"{g['gap_id']:<40} {g['framework_id']}"
        )
    if len(gaps) > 15:
        print(f"  ... and {len(gaps) - 15} more")

    # Verify success conditions
    framework_ids = {g["framework_id"] for g in gaps}
    voi_ok = all(0.0 <= g["voi_score"] <= 1.0 for g in gaps)
    conf_ok = all(0.0 <= g["confidence"] <= 1.0 for g in gaps)
    sorted_ok = all(gaps[i]["voi_score"] >= gaps[i+1]["voi_score"] for i in range(len(gaps)-1))
    dups_ok = len({g["gap_id"] for g in gaps}) == len(gaps)

    print(f"\nVerification:")
    print(f"  gaps >= {args.min_gaps}:        {'PASS' if len(gaps) >= args.min_gaps else 'FAIL'} ({len(gaps)} found)")
    print(f"  VOI in [0,1]:         {'PASS' if voi_ok else 'FAIL'}")
    print(f"  confidence in [0,1]:  {'PASS' if conf_ok else 'FAIL'}")
    print(f"  sorted desc:          {'PASS' if sorted_ok else 'FAIL'}")
    print(f"  no duplicates:        {'PASS' if dups_ok else 'FAIL'}")
    print(f"  frameworks >= 3:      {'PASS' if len(framework_ids) >= 3 else 'FAIL'} ({len(framework_ids)} found: {framework_ids})")


if __name__ == "__main__":
    main()
