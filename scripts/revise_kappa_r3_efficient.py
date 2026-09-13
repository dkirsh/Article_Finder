#!/usr/bin/env python3
"""revise_kappa_r3_efficient.py — produce the R3 "efficient queue" revision of the
frozen kappa-20 HITL pack. Modeled on the AE reviser
(scripts/coordination/revise_frozen_scientific_hitl_batch.py @ AE 965ac10b); the
same invariant governs: OPERATIONAL surface may change, FROZEN SCIENTIFIC CONTENT
may not. The scientific-content hash (selection, source snapshot, write flags,
papers, items) must equal the ratified
acd779c44ad594ca6fba24b350a0cb0711eb0e79805dc8c4009c5935de95081b or this script
refuses to write.

R3 changes (presentation layer only):
  - queue_logic.js replaced by the R3 module (per-stratum Wilson stop rule,
    disagreement-first ordering, seeded audit retention);
  - app.js patched at four anchored sites (each match asserted exactly once);
  - index.html gains a strata-status strip; styles.css gains its rules;
  - review_data gains top-level `efficient_queue` (ranks + stop config; NO
    route-B values) and an updated reviewer_brief.
"""
import hashlib, json, re, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

AF = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3")
R3_ASSETS = AF / "apps/kappa_review_r3"
PACK = Path("/Users/davidusa/REPOS/_shared_artifacts/AE_HITL/"
            "AE_KAPPA_PILOT_FROZEN_20_PLUS_DEMO_HITL_R2_2026-08-20")
OUT = Path("/Users/davidusa/REPOS/_shared_artifacts/AE_HITL/"
           "AE_KAPPA_PILOT_FROZEN_20_PLUS_DEMO_HITL_R3_EFFICIENT_2026-09-11")
RATIFIED_SCIENTIFIC = "acd779c44ad594ca6fba24b350a0cb0711eb0e79805dc8c4009c5935de95081b"
IGNORED = {".DS_Store"}

def fail(code): sys.exit(f"REFUSED: {code}")

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()

def canonical(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()

def scientific_hash(review) -> str:
    return canonical({k: review.get(k) for k in (
        "selection_sha256", "source_snapshot", "canonical_write_performed",
        "re_extraction_performed", "papers", "items")})

def artifact_hashes(root: Path):
    return {str(p.relative_to(root)): sha256(p) for p in sorted(root.rglob("*"))
            if p.is_file() and p.name != "manifest.json" and p.name not in IGNORED}

def patch(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1: fail(f"patch_anchor_{label}_matched_{n}_times")
    return text.replace(old, new)

APP_PATCHES = [
    ("buildQueue",
     """function buildQueue() {
  const base = state.data.items.filter((item) => ["core", "reliability"].includes(item.phase));
  const activeStrata = new Set(
    AEHITLQueueLogic.activeStrataFromResponses(state.data.items, state.responses)
  );
  const extensions = state.data.items.filter(
    (item) => item.phase === "extension" && activeStrata.has(item.stratum)
  );
  const paperOrder = [...new Set(state.data.items.map((item) => item.paper_id))];
  state.queue = [...base, ...extensions]
    .sort((left, right) => {
      const paperDifference = paperOrder.indexOf(left.paper_id) - paperOrder.indexOf(right.paper_id);
      return paperDifference || left.priority - right.priority;
    })
    .map((item) => item.item_id);
}""",
     """function buildQueue() {
  const result = AEHITLQueueLogic.efficientQueue(state.data, state.responses);
  state.queue = result.queue;
  state.stopState = result.stopState;
  state.skippedCount = (result.skipped || []).length;
}"""),
    # A1 (blocking): the reviewer must NOT be able to tell audit items from
    # ordinary ones, nor see per-field verdicts while judging — queueReason is
    # deliberately left unpatched, and the strata strip below shows progress
    # counts only. Verdict state still reaches the EXPORT for post-hoc analysis.
    ("progressLabel",
     """    ? `${answered} of ${state.queue.length} current questions answered`""",
     """    ? `${answered} of ${state.queue.length} questions in the current queue`"""),
    ("progressStrata",
     """  byId("progressBar").max = Math.max(1, state.queue.length);
  byId("progressBar").value = answered;
}""",
     """  byId("progressBar").max = Math.max(1, state.queue.length);
  byId("progressBar").value = answered;
  renderStrataStatus();
}

function renderStrataStatus() {
  // Progress counts only — never verdicts. Showing a field's fate mid-review
  // would anchor the reviewer's remaining judgments (review amendment A1).
  const host = byId("strataStatus");
  if (!host || !state.stopState) { if (host) host.replaceChildren(); return; }
  host.replaceChildren(...Object.entries(state.stopState)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([stratum, s]) => {
      const chip = document.createElement("span");
      chip.className = "stratum-chip";
      const done = s.n + s.undecided;
      chip.title = `${done} of ${s.total_items} answered so far in this field`;
      chip.textContent = `${stratum.replaceAll("_", " ")} ${done}/${s.total_items}`;
      return chip;
    }));
}"""),
    ("completeMessage",
     """      : "The queue stopped because all core items and activated extensions have stable answers.";""",
     """      : "The queue stopped because the sampling plan has the answers it needs from every field; deferred items can return to the queue if later answers call for them.";"""),
    ("exportStopState",
     """      reliability_disagreement_item_ids: reliabilityDisagreements().map((item) => item.item_id),""",
     """      reliability_disagreement_item_ids: reliabilityDisagreements().map((item) => item.item_id),
      strata_stop_state: state.stopState || null,
      skipped_item_count: state.skippedCount || 0,"""),
]

def main():
    if not PACK.is_dir(): fail("parent_pack_missing")
    if OUT.exists(): fail("output_already_exists")
    eq_path = R3_ASSETS / "efficient_queue.json"
    if not eq_path.is_file(): fail("efficient_queue_payload_missing_run_diff_first")
    efficient_queue = json.loads(eq_path.read_text())
    # ALLOWLIST validation (review amendment A3): the payload may contain
    # exactly these keys with exactly these shapes. Anything else — however
    # innocently named — is refused, so a leak cannot ride in under a bland
    # or homoglyph key the way a denylist would allow.
    ALLOWED_TOP = {"schema", "seed", "note", "paper_order", "item_rank", "stop_rule"}
    extra = set(efficient_queue) - ALLOWED_TOP
    if extra: fail(f"efficient_queue_unexpected_keys:{sorted(extra)}")
    for key in ("paper_order", "item_rank", "stop_rule", "seed"):
        if key not in efficient_queue: fail(f"efficient_queue_missing_{key}")
    if not (isinstance(efficient_queue["paper_order"], list)
            and all(isinstance(p, str) for p in efficient_queue["paper_order"])):
        fail("paper_order_not_string_list")
    if not (isinstance(efficient_queue["item_rank"], dict)
            and all(isinstance(v, int) and not isinstance(v, bool)
                    for v in efficient_queue["item_rank"].values())):
        fail("item_rank_values_must_be_plain_ints")
    sr = efficient_queue["stop_rule"]
    ALLOWED_SR = {"z_one_sided_80", "audit_fraction", "audit_minimum",
                  "fail_threshold", "classes"}
    if set(sr) - ALLOWED_SR: fail(f"stop_rule_unexpected_keys:{sorted(set(sr) - ALLOWED_SR)}")
    for cname, cls in sr["classes"].items():
        if set(cls) - {"threshold", "min_n", "strata"}:
            fail(f"stop_rule_class_unexpected_keys:{cname}")
        if not all(isinstance(s, str) for s in cls["strata"]):
            fail(f"stop_rule_strata_not_strings:{cname}")
    if not isinstance(efficient_queue.get("note", ""), str):
        fail("note_not_a_string")
    if re.search(r"\d+\.\d{3,}", efficient_queue.get("note", "")):
        fail("note_contains_precise_floats")

    parent_review = json.loads((PACK / "review_data.json").read_text())
    unhashed = {k: v for k, v in parent_review.items() if k != "pack_sha256"}
    if canonical(unhashed) != parent_review.get("pack_sha256"):
        fail("parent_pack_self_hash_mismatch")
    sci = scientific_hash(parent_review)
    if sci != RATIFIED_SCIENTIFIC: fail("parent_scientific_hash_not_the_ratified_one")
    parent_manifest_sha = sha256(PACK / "manifest.json")
    parent_manifest = json.loads((PACK / "manifest.json").read_text())
    # full parent artifact verification, as the AE reviser does
    actual = artifact_hashes(PACK)
    declared = parent_manifest.get("artifacts") or {}
    if set(actual) != set(declared): fail("parent_artifact_set_mismatch")
    bad = [p for p, h in actual.items() if declared[p] != h]
    if bad: fail(f"parent_artifact_hash_mismatch:{bad[:3]}")

    # every item must carry a rank; every paper an order slot
    item_ids = {i["item_id"] for i in parent_review["items"]}
    missing_rank = item_ids - set(efficient_queue["item_rank"])
    if missing_rank: fail(f"item_rank_missing_for:{sorted(missing_rank)[:5]}")
    paper_ids = {i["paper_id"] for i in parent_review["items"]}
    if paper_ids - set(efficient_queue["paper_order"]): fail("paper_order_incomplete")

    shutil.copytree(PACK, OUT)
    (OUT / "queue_logic.js").write_text((R3_ASSETS / "queue_logic.js").read_text())
    app = (OUT / "app.js").read_text()
    for label, old, new in APP_PATCHES:
        app = patch(app, old, new, label)
    (OUT / "app.js").write_text(app)
    html = (OUT / "index.html").read_text()
    html = patch(html, '<progress id="progressBar"',
                 '<div id="strataStatus" class="strata-status"></div><progress id="progressBar"',
                 "strataStatusDiv")
    (OUT / "index.html").write_text(html)
    css = (OUT / "styles.css").read_text()
    css += ("\n.strata-status{display:flex;flex-wrap:wrap;gap:4px;margin:6px 0;}\n"
            ".stratum-chip{font-size:11px;padding:2px 8px;border-radius:10px;"
            "background:#eee7d9;color:#4a4234;}\n"
            ".stratum-chip.released{background:#d4edda;color:#2f6b3a;}\n"
            ".stratum-chip.condemned{background:#f8d7da;color:#8a2b2b;}\n")
    (OUT / "styles.css").write_text(css)
    (OUT / "START_REVIEW.command").chmod(0o755)

    review = json.loads((OUT / "review_data.json").read_text())
    review["efficient_queue"] = efficient_queue
    review["reviewer_brief"] = (
        "Judge independently against the complete paper. Questions arrive in an "
        "order we computed and each field switches off once your judgments pin its "
        "error rate down, so the required count shrinks as you work. Progress is "
        "saved in this browser; download a portable backup whenever you stop.")
    revision = {
        "revision_id": "kappa-20-hitl-operational-r3-efficient-2026-09-11",
        "parent_pack_sha256": parent_review["pack_sha256"],
        "parent_manifest_sha256": parent_manifest_sha,
        "scientific_content_sha256": sci,
        "scientific_inputs_changed": False,
        "built_by": "fable, Article_Finder scripts/revise_kappa_r3_efficient.py",
        "authority": "David Kirsh chat ruling 2026-09-11 (efficient version inside the pilot)",
        "changed_surface": [
            "queue_logic.js: per-stratum one-sided-80% Wilson stop rule, "
            "disagreement-first ordering, seeded 15% audit retention",
            "app.js: queue delegation, strata status strip, stop-state in exports",
            "review_data: efficient_queue block (ranks + config only; no route-B values)",
            "reviewer brief",
        ],
    }
    review["operational_revision"] = revision
    review["app_assets"] = {a: sha256(OUT / a) for a in
                            ("index.html", "queue_logic.js", "app.js", "styles.css")}
    review.pop("pack_sha256", None)
    review["pack_sha256"] = canonical(review)
    if scientific_hash(review) != RATIFIED_SCIENTIFIC:
        fail("scientific_content_changed_by_this_script")
    (OUT / "review_data.json").write_text(json.dumps(review, indent=2) + "\n")

    manifest = dict(parent_manifest)
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    manifest["reviser_path"] = "Article_Finder_v3_2_3/scripts/revise_kappa_r3_efficient.py"
    manifest["reviser_sha256"] = sha256(Path(__file__).resolve())
    manifest["operational_revision"] = revision
    manifest["artifacts"] = artifact_hashes(OUT)
    manifest["artifact_count"] = len(manifest["artifacts"])
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUT),
        "manifest_sha256": sha256(OUT / "manifest.json"),
        "pack_sha256": review["pack_sha256"],
        "parent_manifest_sha256": parent_manifest_sha,
        "scientific_content_sha256": sci,
        "scientific_inputs_changed": False,
        "artifact_count": manifest["artifact_count"],
    }, indent=2))

if __name__ == "__main__":
    main()
