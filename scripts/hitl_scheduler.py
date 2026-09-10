#!/usr/bin/env python3
"""hitl_scheduler.py — adaptive, value-of-information ordering for HITL batches.

David 2026-09-09: "how do you decide which pdfs to have hitl? This should be a
sort of adaptive preference thing or value of info calculation that you update
as you get answers... the list order and the list that a human eventually sees
is not predetermined."

Usage:
    python3 scripts/hitl_scheduler.py <batch_dir> [judgments.json ...]

Reads the batch's machine evidence (results.json, and judge_verdicts*.json if
present) plus any exported human judgment files, scores every unruled paper for
expected information value, and REWRITES tasks.json in priority order. Run it
between human sessions; the viewer shows whatever order tasks.json carries, so
the list regenerates as answers arrive.

Priority score (v0 — four terms, weights explicit so David can retune):
  uncertainty   machine confidence low, or judge abstained          (w=0.35)
  conflict      layers disagree: mechanical vs judge vs S2 vs the   (w=0.25)
                stored registry label — a ruling here flips beliefs
  cluster_mass  the paper's signal-profile cluster is large and     (w=0.20)
                mostly unruled — one ruling propagates to many
  surprise_sim  similar (same cluster) to a paper where the human   (w=0.20)
                DISAGREED with the machine — surprises localize,
                so their neighborhoods need human eyes

Update rule: each human judgment (a) removes its paper, (b) if it AGREED with
the machine, damps its whole cluster's priority (the machine is trustworthy
there), (c) if it DISAGREED, boosts the cluster (surprise_sim). Escalated
papers are listed first regardless, so David's queue surfaces at the top.

IMPORTANT: never run this on a BLIND VALIDATION batch before the human finishes
it — adaptive reordering conditioned on machine output biases the kappa. The
script refuses when tasks.json says mode=blind unless --force-blind is given.
"""
import json, sys, collections
from pathlib import Path

W = {"uncertainty": 0.35, "conflict": 0.25, "cluster_mass": 0.20, "surprise_sim": 0.20}
SIG_KEYS = ("stats", "participants", "prisma", "meta", "qual", "review_lang")

def cluster_of(rec):
    sig = rec.get("signals", {})
    return "".join(str(int(bool(sig.get(k)))) for k in SIG_KEYS)

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    batch = Path(sys.argv[1])
    force = "--force-blind" in sys.argv
    jfiles = [Path(p) for p in sys.argv[2:] if not p.startswith("--")]

    tasks_doc = json.loads((batch / "tasks.json").read_text())
    if tasks_doc.get("mode") == "blind" and not force:
        sys.exit("REFUSING: blind validation batch — adaptive reordering would bias kappa. "
                 "Finish the human round first, or pass --force-blind for a production batch "
                 "mislabeled as blind.")
    results = {r["paper_id"]: r for r in json.loads((batch / "results.json").read_text())}
    verdicts = {}
    for vf in sorted(batch.glob("judge_verdicts*.json")):
        for v in json.loads(vf.read_text()).get("verdicts", []):
            verdicts[v["paper_id"]] = v

    human = {}
    for jf in jfiles:
        for j in json.loads(jf.read_text()).get("judgments", []):
            if j: human[j["paper_id"]] = j

    clusters = collections.defaultdict(list)
    for pid, r in results.items():
        clusters[cluster_of(r)].append(pid)

    cluster_state = {}  # cid -> {"ruled": n, "agreed": n, "disagreed": n}
    fam = lambda m: ("empirical" if m and m.startswith(("empirical", "mixed")) else
                     "review" if m and (m.startswith("review") or m in ("meta_analysis", "narrative_review", "systematic_review")) else m)
    for cid, pids in clusters.items():
        st = {"ruled": 0, "agreed": 0, "disagreed": 0}
        for pid in pids:
            if pid in human:
                st["ruled"] += 1
                mv = verdicts.get(pid, {}).get("method")
                hv = human[pid].get("method")
                if mv and hv:
                    st["agreed" if fam(mv) == fam(hv) else "disagreed"] += 1
        cluster_state[cid] = st

    scored = []
    for pid, r in results.items():
        if pid in human:
            continue
        v = verdicts.get(pid, {})
        conf = v.get("confidence")
        uncertainty = 1.0 if conf is None else max(0.0, 1.0 - float(conf))
        opinions = set()
        if v.get("method"): opinions.add(fam(v["method"]))
        mech = r.get("mechanical_method")
        if mech and mech != "OPEN": opinions.add(fam(mech))
        s2 = r.get("s2_publicationTypes")
        if isinstance(s2, list):
            if "Review" in s2: opinions.add("review")
            if any(t in s2 for t in ("ClinicalTrial", "Study")): opinions.add("empirical")
        reg = r.get("registry_type_stratum")
        if reg: opinions.add(fam(reg))
        conflict = min(1.0, max(0, len(opinions) - 1) / 2.0)
        cid = cluster_of(r)
        st = cluster_state[cid]
        unruled = len(clusters[cid]) - st["ruled"]
        cluster_mass = min(1.0, unruled / 10.0)
        if st["ruled"]:
            agree_rate = st["agreed"] / st["ruled"]
            cluster_mass *= (1.0 - 0.7 * agree_rate)      # damp trusted clusters
            surprise = min(1.0, st["disagreed"] / st["ruled"])
        else:
            surprise = 0.0
        score = (W["uncertainty"] * uncertainty + W["conflict"] * conflict +
                 W["cluster_mass"] * cluster_mass + W["surprise_sim"] * surprise)
        scored.append((round(score, 4), pid,
                       {"uncertainty": round(uncertainty, 2), "conflict": round(conflict, 2),
                        "cluster": cid, "cluster_unruled": unruled,
                        "cluster_surprise": round(surprise, 2)}))

    scored.sort(reverse=True)
    escalated = [j["paper_id"] for j in human.values() if j.get("escalate")]

    by_id = {t["paper_id"]: t for t in tasks_doc["tasks"]}
    new_tasks = []
    for _, pid, why in scored:
        t = dict(by_id[pid]); t["voi_score"] = _; t["voi_why"] = why
        new_tasks.append(t)
    tasks_doc["tasks"] = new_tasks
    tasks_doc["escalated_for_david"] = escalated
    tasks_doc["scheduler"] = {"weights": W, "ruled": len(human),
                              "remaining": len(new_tasks)}
    (batch / "tasks.json").write_text(json.dumps(tasks_doc, indent=2))
    print(f"reordered {len(new_tasks)} remaining tasks "
          f"({len(human)} ruled, {len(escalated)} escalated for David)")
    for s, pid, why in scored[:8]:
        print(f"  {s:5.2f}  {pid}  {why}")

if __name__ == "__main__":
    main()
