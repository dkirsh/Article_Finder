#!/usr/bin/env python3
"""kappa_r3_diff_and_rank.py — build the R3 efficient-queue overlay for the frozen
kappa-20 pack. Reads route-B blind extractions (scratchpad routeB/*.json) and the
R2 pack's route-A candidate projections, scores per-item disagreement, and writes:

  apps/kappa_review_r3/receipts/route_b_diff_receipt.json   (repo-side; FULL values,
      scores, per-stratum agreement, expected-load simulation — never shipped to
      the reviewer, who must stay blind to route B)
  apps/kappa_review_r3/efficient_queue.json                  (pack payload; ranks
      and stop-rule config ONLY — no route-B values, no agree/disagree flags)

Scoring: disagreement in [0,1] per stratum-appropriate comparator; one-sided null
mismatches score 1.0 (the most informative case: one route says the paper reports
it, the other says it does not). rank_score = 0.7*disagreement + 0.3*route_b
ambiguity ((5-confidence)/4), so David's ambiguity-touchpoint ruling shapes the
order too. Demo papers stay first in original order.
"""
import json, re, sys, math
from pathlib import Path

AF = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3")
PACK = Path("/Users/davidusa/REPOS/_shared_artifacts/AE_HITL/"
            "AE_KAPPA_PILOT_FROZEN_20_PLUS_DEMO_HITL_R2_2026-08-20")
ROUTE_B = Path("/private/tmp/claude-501/-Users-davidusa-REPOS-New-VR-Platform/"
               "b07ed661-0ea6-4535-8b9d-cd0200658a81/scratchpad/routeB")
OUT_DIR = AF / "apps/kappa_review_r3"
STOP = {
    "z_one_sided_80": 0.8416, "audit_fraction": 0.15, "audit_minimum": 1,
    "fail_threshold": 0.35,
    "classes": {
        "mechanical": {"threshold": 0.15, "min_n": 4,
            "strata": ["apa_citation", "article_type", "sample_n", "p_value", "effect_size"]},
        "semantic": {"threshold": 0.10, "min_n": 7,
            "strata": ["main_conclusion", "independent_variables", "dependent_variables",
                       "construct_pair", "direction", "stimulus_description",
                       "methods_surface_summary", "measurement_inventory"]},
    },
}
STOPWORDS = set("the a an of and or in on to for with by from at as is are was were be been this that these those it its".split())

def tokens(v):
    if v is None: return set()
    if isinstance(v, (list, tuple)): v = " ".join(str(x) for x in v)
    if isinstance(v, dict): v = " ".join(f"{k} {x}" for k, x in v.items())
    return {t for t in re.findall(r"[a-z0-9]+", str(v).lower()) if t not in STOPWORDS and len(t) > 2}

def jaccard(a, b):
    A, B = tokens(a), tokens(b)
    if not A and not B: return 1.0
    if not A or not B: return 0.0
    return len(A & B) / len(A | B)

def num_of(v):
    if v is None: return None
    m = re.search(r"\d[\d,]*", str(v))
    return int(m.group(0).replace(",", "")) if m else None

DIRECTION_MAP = {"positive": "positive", "increase": "positive", "beneficial": "positive",
    "negative": "negative", "decrease": "negative", "detrimental": "negative",
    "mixed": "mixed", "no_effect": "no_effect", "null": "no_effect", "none": "no_effect",
    "not_applicable": "na", "na": "na", "indeterminate": "indeterminate"}

def disagreement(stratum, a, b):
    """1.0 = maximal disagreement. Handles the one-sided-null case first."""
    a_null = a in (None, "", [], {})
    b_null = b in (None, "", [], {})
    if a_null and b_null: return 0.0
    if a_null != b_null: return 1.0
    if stratum == "sample_n":
        na, nb = num_of(a), num_of(b)
        if na is None or nb is None: return 1.0 if (na is None) != (nb is None) else 0.0
        return 0.0 if na == nb else min(1.0, abs(na - nb) / max(na, nb) + 0.5)
    if stratum in ("p_value", "effect_size"):
        ca = re.sub(r"[^0-9.<>=a-z]", "", str(a).lower())
        cb = re.sub(r"[^0-9.<>=a-z]", "", str(b).lower())
        if ca == cb or ca in cb or cb in ca: return 0.0
        return 0.3 if jaccard(a, b) > 0.5 else 1.0
    if stratum == "direction":
        da = DIRECTION_MAP.get(str(a).strip().lower(), str(a).strip().lower())
        db = DIRECTION_MAP.get(str(b).strip().lower(), str(b).strip().lower())
        if da == db: return 0.0
        if "indeterminate" in (da, db): return 0.85  # route says text is ambiguous
        return 1.0
    if stratum == "article_type":
        j = jaccard(str(a).replace("_", " "), str(b).replace("_", " "))
        return 0.0 if j >= 0.4 else 1.0
    if stratum == "apa_citation":
        j = jaccard(a, b)
        return 0.0 if j >= 0.35 else (0.5 if j >= 0.2 else 1.0)
    if stratum in ("independent_variables", "dependent_variables", "measurement_inventory"):
        j = jaccard(a, b)
        return max(0.0, 1.0 - min(1.0, j / 0.30))
    j = jaccard(a, b)          # free-text strata
    return max(0.0, 1.0 - min(1.0, j / 0.18))

def wilson_ub(errors, n, z):
    if n <= 0: return 1.0
    p, z2 = errors / n, z * z
    return ((p + z2/(2*n)) + z * math.sqrt(p*(1-p)/n + z2/(4*n*n))) / (1 + z2/n)

def wilson_lb(errors, n, z):
    if n <= 0: return 0.0
    p, z2 = errors / n, z * z
    return max(0.0, ((p + z2/(2*n)) - z * math.sqrt(p*(1-p)/n + z2/(4*n*n))) / (1 + z2/n))

def stratum_class(stratum):
    for name, cls in STOP["classes"].items():
        if stratum in cls["strata"]: return name, cls
    return "semantic", STOP["classes"]["semantic"]

def main():
    data = json.loads((PACK / "review_data.json").read_text())
    items = data["items"]
    route_b = {}
    for f in sorted(ROUTE_B.glob("PDF-*.json")):
        r = json.loads(f.read_text())
        route_b[r["paper_id"]] = r
    eval_pids = sorted({i["paper_id"] for i in items if i["evaluation_role"] == "human_kappa_evaluation"})
    missing = [p for p in eval_pids if p not in route_b]
    if missing:
        sys.exit(f"route-B extraction missing for {missing}; refusing to rank a partial diff.")

    rows, ranked = [], {}
    for item in items:
        pid, stratum = item["paper_id"], item["stratum"]
        if item["evaluation_role"] != "human_kappa_evaluation":
            rows.append({"item_id": item["item_id"], "paper_id": pid, "stratum": stratum,
                         "demo": True, "rank_score": None})
            continue
        b_rec = route_b[pid]
        a_val = item.get("candidate_projection")
        if a_val is None:
            a_val = (item.get("candidate_display") or {}).get("value")
        b_val = (b_rec.get("fields") or {}).get(stratum)
        conf = (b_rec.get("confidence") or {}).get(stratum, 3)
        dis = disagreement(stratum, a_val, b_val)
        ambiguity = max(0.0, (5 - float(conf)) / 4.0)
        score = round(0.7 * dis + 0.3 * ambiguity, 4)
        rows.append({"item_id": item["item_id"], "paper_id": pid, "stratum": stratum,
                     "demo": False, "route_a": a_val, "route_b": b_val,
                     "route_b_confidence": conf, "disagreement": round(dis, 4),
                     "ambiguity": round(ambiguity, 4), "rank_score": score})
        ranked[item["item_id"]] = score

    # Paper order: demo papers first (original order), then eval papers by mean score desc.
    original_order = list(dict.fromkeys(i["paper_id"] for i in items))
    demo_pids = [p for p in original_order if p not in eval_pids]
    paper_mass = {p: 0.0 for p in eval_pids}
    paper_count = {p: 0 for p in eval_pids}
    for r in rows:
        if not r["demo"]:
            paper_mass[r["paper_id"]] += r["rank_score"]; paper_count[r["paper_id"]] += 1
    paper_order = demo_pids + sorted(eval_pids,
        key=lambda p: -(paper_mass[p] / max(1, paper_count[p])))

    # Within-paper item ranks: demo items keep original priority; eval items by score desc.
    item_rank = {}
    for pid in paper_order:
        paper_items = [i for i in items if i["paper_id"] == pid]
        if pid in demo_pids:
            paper_items.sort(key=lambda i: i["priority"])
        else:
            paper_items.sort(key=lambda i: (-ranked.get(i["item_id"], 0.0), i["priority"]))
        for pos, it in enumerate(paper_items):
            item_rank[it["item_id"]] = pos

    # Expected-load simulation: reviewer confirms where routes agree (score<0.5),
    # errors where they disagree, in queue order under the stop rule.
    sim_state = {}
    for i in items:
        if i["evaluation_role"] != "human_kappa_evaluation": continue
        sim_state.setdefault(i["stratum"], {"n": 0, "errors": 0})
    order = sorted((i for i in items if i["evaluation_role"] == "human_kappa_evaluation"),
                   key=lambda i: (paper_order.index(i["paper_id"]) * 1000 + item_rank[i["item_id"]]))
    judged = 0
    released, condemned = set(), set()
    for it in order:
        s = it["stratum"]
        name, cls = stratum_class(s)
        st = sim_state[s]
        if s in released or s in condemned: continue
        judged += 1
        st["n"] += 1
        if ranked[it["item_id"]] >= 0.5: st["errors"] += 1
        if st["n"] < cls["min_n"]: continue
        if wilson_ub(st["errors"], st["n"], STOP["z_one_sided_80"]) <= cls["threshold"]:
            released.add(s)
        elif wilson_lb(st["errors"], st["n"], STOP["z_one_sided_80"]) >= STOP["fail_threshold"]:
            condemned.add(s)
    demo_count = sum(1 for r in rows if r["demo"])
    strata_summary = {}
    for s, st in sim_state.items():
        name, cls = stratum_class(s)
        dis_items = [r for r in rows if not r["demo"] and r["stratum"] == s]
        strata_summary[s] = {"class": name, "items": len(dis_items),
            "route_agreement_rate": round(sum(1 for r in dis_items if r["disagreement"] < 0.5) / max(1, len(dis_items)), 3),
            "mean_disagreement": round(sum(r["disagreement"] for r in dis_items) / max(1, len(dis_items)), 3),
            "sim_judged": st["n"], "sim_errors": st["errors"],
            "sim_released": s in released, "sim_condemned": s in condemned}

    receipt = {"schema": "kappa_r3_route_b_diff_receipt.v1",
        "pack": str(PACK), "pack_sha256": data["pack_sha256"],
        "route_b_system": "claude sonnet subagents, blind to candidates, docling text only (session 2026-09-11)",
        "items": rows, "strata": strata_summary,
        "simulation": {"assumption": "reviewer confirms agreements, errors disagreements, queue order",
            "expected_required_eval_items": judged, "demo_items_always_required": demo_count,
            "eval_items_total": len(order), "released_strata": sorted(released),
            "condemned_strata": sorted(condemned)}}
    payload = {"schema": "kappa_r3_efficient_queue.v1", "seed": "kappa-r3-2026-09-11",
        "note": ("Presentation-layer ordering + sequential stop rule (David Kirsh ruling "
                 "2026-09-11). Ranks derive from a second blind extraction route; the "
                 "route's values are deliberately NOT in this pack - the reviewer must "
                 "stay unanchored. Full diff receipt: Article_Finder apps/kappa_review_r3/receipts/."),
        "paper_order": paper_order, "item_rank": item_rank, "stop_rule": STOP}
    (OUT_DIR / "receipts").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "receipts/route_b_diff_receipt.json").write_text(json.dumps(receipt, indent=1))
    (OUT_DIR / "efficient_queue.json").write_text(json.dumps(payload, indent=1))
    print(f"items ranked: {len(item_rank)} (eval {len(order)}, demo {demo_count})")
    print(f"simulated required eval items: {judged}/{len(order)}  "
          f"(+{demo_count} demo always) -> total ~{judged + demo_count} of 287")
    print(f"released in sim: {len(released)}/13; condemned (fail-fast): {len(condemned)}/13")
    for s, row in sorted(strata_summary.items()):
        state = "RELEASED" if row["sim_released"] else ("CONDEMNED" if row["sim_condemned"] else "exhausted")
        print(f"  {s:26s} {row['class']:10s} agree={row['route_agreement_rate']:.2f} "
              f"sim_judged={row['sim_judged']:3d} {state}")

if __name__ == "__main__":
    main()
