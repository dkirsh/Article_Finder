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

# Machine-line patches (queue delegation, neutral strip, neutral texts,
# stop-state exports) are NOT in this list: they already live inside the R33
# base assets this script now builds on. This list holds only the layer David
# ruled on during his walkthrough: the field guide (i button + definitions),
# the candidate-value hint, 'Also applies', and choose-from-alternatives
# correction controls for closed-vocabulary fields.
APP_PATCHES = [
    ("fieldGuidePanel",
     """  byId("stratum").textContent = item.stratum_label;""",
     """  byId("stratum").textContent = item.stratum_label;
  renderFieldGuide(item);"""),
    ("fieldGuideFns",
     """function setRadio(name, value) {""",
     """function renderFieldGuide(item) {
  const host = byId("fieldGuide");
  const guide = (state.data.field_guide || {}).strata || {};
  const entry = guide[item.stratum];
  if (!host) return;
  const values = (entry && entry.values) || {};
  if (!entry) { host.classList.add("hidden"); byId("fieldInfoBtn").style.display = "none"; }
  else {
    byId("fieldInfoBtn").style.display = "";
    const parts = [`<p><strong>What you are judging.</strong> ${entry.definition}</p>`];
    if (Object.keys(values).length) {
      parts.push("<p><strong>The values and what they mean:</strong></p><ul>" +
        Object.entries(values).map(([v, d]) => `<li><code>${v}</code> — ${d}</li>`).join("") + "</ul>");
    }
    if (entry.multi) parts.push(`<p><strong>More than one can be true.</strong> ${entry.multi}</p>`);
    host.innerHTML = parts.join("");
  }
  // inline definition for the machine's own value, right where it is judged
  const cand = item.candidate_display && item.candidate_display.value;
  const hint = byId("candidateValueHint");
  if (hint) {
    const d = typeof cand === "string" ? values[cand.trim().toLowerCase()] : null;
    hint.textContent = d ? `${cand}: ${d}` : "";
    hint.classList.toggle("hidden", !d);
  }
  // Corrections are a CHOICE among the field's defined values, never a guess
  // into thin air (David's ruling 2026-09-14). Fields without a closed
  // vocabulary keep the free-text box.
  const choice = byId("correctedChoice");
  const dl = byId("valueOptions");
  const hasVocab = Object.keys(values).length > 0;
  if (choice) {
    choice.replaceChildren();
    if (hasVocab) {
      const ph = document.createElement("option");
      ph.value = ""; ph.textContent = "choose the correct value…";
      choice.append(ph);
      for (const v of Object.keys(values)) {
        const o = document.createElement("option"); o.value = v; o.textContent = v; choice.append(o);
      }
      const other = document.createElement("option");
      other.value = "__other"; other.textContent = "other — type it below";
      choice.append(other);
    }
    choice.classList.toggle("hidden", !hasVocab);
    byId("correctedValue").classList.toggle("hidden", hasVocab);
  }
  if (dl) {
    dl.replaceChildren();
    if (hasVocab) for (const v of Object.keys(values)) {
      const o = document.createElement("option"); o.value = v; dl.append(o);
    }
  }
}

function collectCorrectedValue() {
  const choice = byId("correctedChoice");
  if (choice && !choice.classList.contains("hidden") && choice.value && choice.value !== "__other")
    return choice.value;
  return byId("correctedValue").value.trim();
}

function setRadio(name, value) {"""),
    ("alsoAppliesCollect",
     """    corrected_value: byId("correctedValue").value.trim(),""",
     """    corrected_value: collectCorrectedValue(),
    also_applies: byId("alsoApplies").value.trim(),"""),
    ("alsoAppliesRestore",
     """    byId("correctedValue").value = response.corrected_value || "";""",
     """    byId("correctedValue").value = response.corrected_value || "";
    byId("alsoApplies").value = response.also_applies || "";
    const cc = byId("correctedChoice");
    if (cc && !cc.classList.contains("hidden") && response.corrected_value) {
      const match = [...cc.options].some((o) => o.value === response.corrected_value);
      cc.value = match ? response.corrected_value : "__other";
      byId("correctedValue").classList.toggle("hidden", match);
    }"""),
    ("fieldInfoToggle",
     """byId("markTextButton").addEventListener("click", markSelectedText);""",
     """byId("markTextButton").addEventListener("click", markSelectedText);
byId("fieldInfoBtn").addEventListener("click", () => byId("fieldGuide").classList.toggle("hidden"));
byId("correctedChoice").addEventListener("change", () => {
  byId("correctedValue").classList.toggle("hidden", byId("correctedChoice").value !== "__other");
});"""),
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
    # 'note' is NOT accepted from the payload — this script injects a fixed
    # literal after validation, so free text can never carry route values in.
    ALLOWED_TOP = {"schema", "seed", "paper_order", "item_rank", "stop_rule"}
    extra = set(efficient_queue) - ALLOWED_TOP
    if extra: fail(f"efficient_queue_unexpected_keys:{sorted(extra)}")
    if not re.fullmatch(r"[a-z0-9-]{1,40}", str(efficient_queue.get("seed", ""))):
        fail("seed_format_invalid")
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
    KNOWN_STRATA = {"apa_citation", "article_type", "main_conclusion",
        "independent_variables", "dependent_variables", "construct_pair",
        "direction", "sample_n", "p_value", "effect_size",
        "stimulus_description", "methods_surface_summary", "measurement_inventory"}
    for cname, cls in sr["classes"].items():
        if set(cls) - {"threshold", "min_n", "strata"}:
            fail(f"stop_rule_class_unexpected_keys:{cname}")
        if not set(cls["strata"]) <= KNOWN_STRATA:
            fail(f"stop_rule_strata_outside_known_set:{cname}")

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
    alien_rank = set(efficient_queue["item_rank"]) - item_ids
    if alien_rank: fail(f"item_rank_keys_not_pack_items:{sorted(alien_rank)[:5]}")
    paper_ids = {i["paper_id"] for i in parent_review["items"]}
    if paper_ids - set(efficient_queue["paper_order"]): fail("paper_order_incomplete")

    shutil.copytree(PACK, OUT)
    # Base UI = the R33 hand-edited interface (David's ruling 2026-09-14:
    # "8783 is the right version"), preserved under version control at
    # r33_hand_edits/. It already carries the machine-line queue features
    # (delegated buildQueue, neutral strata strip, stop-state exports), so the
    # patch list below holds ONLY the field-guide/choice layer.
    HAND = R3_ASSETS / "r33_hand_edits"
    for asset in ("app.js", "index.html", "styles.css", "stephan.html"):
        src = HAND / asset
        if not src.is_file(): fail(f"r33_hand_edit_missing:{asset}")
        (OUT / asset).write_text(src.read_text())
    (OUT / "queue_logic.js").write_text((R3_ASSETS / "queue_logic.js").read_text())
    app = (OUT / "app.js").read_text()
    for label, old, new in APP_PATCHES:
        app = patch(app, old, new, label)
    (OUT / "app.js").write_text(app)
    html = (OUT / "index.html").read_text()
    # (no strataStatus insertion: the R33 base index already carries it)
    html = patch(html, '<span id="stratum"></span>',
                 '<span id="stratum"></span> <button id="fieldInfoBtn" type="button" '
                 'class="info-btn" title="What am I judging? What do the values mean?">i</button>',
                 "fieldInfoBtn")
    html = patch(html, '<div id="candidateValue" class="candidate-values"></div>',
                 '<div id="candidateValue" class="candidate-values"></div>'
                 '<div id="candidateValueHint" class="cand-hint hidden"></div>'
                 '<div id="fieldGuide" class="field-guide hidden"></div>',
                 "fieldGuidePanelDiv")
    html = patch(html, '<textarea id="correctedValue"',
                 '<select id="correctedChoice" class="hidden"></select>'
                 '<textarea id="correctedValue"',
                 "correctedChoiceSelect")
    html = patch(html, '<div id="rationaleWrap" class="form-row hidden">',
                 '<div class="form-row"><label for="alsoApplies">Also applies '
                 '(optional) — when more than one value is truly right, add the '
                 'others here, e.g. "empirical_quantitative"</label>'
                 '<input id="alsoApplies" type="text" list="valueOptions" '
                 'placeholder="second true label, if any">'
                 '<datalist id="valueOptions"></datalist></div>\n'
                 '          <div id="rationaleWrap" class="form-row hidden">',
                 "alsoAppliesRow")
    (OUT / "index.html").write_text(html)
    css = (OUT / "styles.css").read_text()
    css += ("\n.strata-status{display:flex;flex-wrap:wrap;gap:4px;margin:6px 0;}\n"
            ".stratum-chip{font-size:11px;padding:2px 8px;border-radius:10px;"
            "background:#eee7d9;color:#4a4234;}\n"
            ".info-btn{display:inline-flex;align-items:center;justify-content:center;"
            "width:18px;height:18px;border-radius:50%;border:1px solid #7a5c2e;"
            "background:#fff;color:#7a5c2e;font:600 12px/1 Georgia,serif;cursor:pointer;"
            "vertical-align:middle;}\n"
            ".field-guide{background:#f7f4ec;border:1px solid #d8d4cc;border-radius:8px;"
            "padding:10px 14px;margin:8px 0;font-size:13px;line-height:1.5;}\n"
            ".field-guide code{background:#eee7d9;padding:0 4px;border-radius:4px;}\n"
            ".field-guide ul{margin:4px 0 4px 18px;padding:0;}\n"
            ".cand-hint{font-size:12px;color:#555;background:#f7f4ec;border-left:3px solid #7a5c2e;"
            "padding:4px 10px;margin:4px 0;}\n")
    (OUT / "styles.css").write_text(css)
    (OUT / "START_REVIEW.command").chmod(0o755)

    review = json.loads((OUT / "review_data.json").read_text())
    # Machine-resolved items (David's descope ruling 2026-09-13): injected from
    # the adjudication receipt's id list, validated against pack item ids.
    mr_path = R3_ASSETS / "machine_resolved_items.json"
    if mr_path.is_file():
        mr = json.loads(mr_path.read_text()).get("machine_resolved_items", [])
        if not (isinstance(mr, list) and all(isinstance(x, str) for x in mr)):
            fail("machine_resolved_items_malformed")
        alien = set(mr) - item_ids
        if alien: fail(f"machine_resolved_items_not_pack_items:{sorted(alien)[:5]}")
        # F6: only the stratum David's ruling covers may be machine-resolved.
        stratum_of = {i["item_id"]: i["stratum"] for i in parent_review["items"]}
        off_ruling = [x for x in mr if stratum_of.get(x) != "apa_citation"]
        if off_ruling: fail(f"machine_resolved_outside_apa_ruling:{off_ruling[:5]}")
        # P9 (round-5 review): the id list must equal the adjudication
        # receipt's machine subset — a stale or hand-edited list cannot
        # silently undo a lineage-based human_review disposition.
        receipt = json.loads((R3_ASSETS / "receipts/apa_machine_adjudication.json").read_text())
        receipt_machine = sorted(r["item_id"] for r in receipt["items"]
                                 if r["disposition"] == "machine_adjudicated")
        if sorted(mr) != receipt_machine:
            fail("machine_resolved_items_disagree_with_adjudication_receipt")
        efficient_queue["machine_resolved_items"] = sorted(mr)

    # Field guide (David's walkthrough ruling 2026-09-13: no value the human
    # must judge may go undefined). Injected from the authored repo file;
    # strict shape validation — strings only, strata within the known set.
    fg_path = R3_ASSETS / "field_guide.json"
    field_guide = None
    if fg_path.is_file():
        fg = json.loads(fg_path.read_text())
        # Round-6 gap fix: allowlist the WHOLE guide object, not only strata.
        if set(fg) - {"schema", "note", "strata"}: fail("field_guide_unexpected_top_keys")
        if not isinstance(fg.get("note", ""), str): fail("field_guide_note_not_string")
        strata_map = fg.get("strata")
        if not isinstance(strata_map, dict): fail("field_guide_malformed")
        KNOWN_STRATA_FG = {"apa_citation", "article_type", "main_conclusion",
            "independent_variables", "dependent_variables", "construct_pair",
            "direction", "sample_n", "p_value", "effect_size",
            "stimulus_description", "methods_surface_summary", "measurement_inventory"}
        if set(strata_map) - KNOWN_STRATA_FG: fail("field_guide_unknown_strata")
        for sname, entry in strata_map.items():
            if set(entry) - {"definition", "values", "multi"}:
                fail(f"field_guide_unexpected_keys:{sname}")
            if not isinstance(entry.get("definition"), str): fail(f"field_guide_definition_missing:{sname}")
            if "multi" in entry and not isinstance(entry["multi"], str):
                fail(f"field_guide_multi_not_string:{sname}")
            for k, v in (entry.get("values") or {}).items():
                if not (isinstance(k, str) and isinstance(v, str)):
                    fail(f"field_guide_values_not_strings:{sname}")
        field_guide = fg

    # A1(b): the brief must not describe per-field verdict mechanics to the
    # person whose unanchored judgment is the measurement.
    efficient_queue["note"] = (
        "Presentation-layer ordering and sequential sampling; frozen scientific "
        "content unchanged. Full method receipt: Article_Finder "
        "apps/kappa_review_r3/receipts/.")
    review["efficient_queue"] = efficient_queue
    # Start-screen copy, human-first (David's ruling 2026-09-14: the reader
    # must be told the objective plainly; no machine-compressed mashups).
    review["title"] = "Checking the machine's reading of 20 papers"
    review["purpose"] = (
        "The objective of this review is to measure how accurately our "
        "extraction system reads scientific papers, and to catch exactly where "
        "it goes wrong. The machine has already pulled a set of facts from each "
        "paper: the citation, the kind of paper it is, who was studied, what "
        "was measured, what was found. One question at a time, you will check "
        "one extracted fact against the paper itself and say whether the "
        "machine got it right. The first three papers are labeled demonstration "
        "papers - use them to get comfortable; they are excluded from the "
        "measurement. The other twenty are the evaluation sample, frozen since "
        "August so that nothing can quietly change what is being measured.")
    if field_guide is not None:
        review["field_guide"] = field_guide
    review["reviewer_brief"] = (
        "Judge independently against the complete paper. Questions arrive in an "
        "order we computed, and the queue adjusts as you work, so the required "
        "count changes along the way. Progress is saved in this browser; download "
        "a portable backup whenever you stop.")
    descoped = sorted(efficient_queue.get("machine_resolved_items", []))
    revision = {
        "revision_id": ("kappa-20-hitl-operational-r3.5-merged-ui-2026-09-14"
                        if descoped else "kappa-20-hitl-operational-r3.1-amended-2026-09-13"),
        "amends": ("kappa-20-hitl-operational-r3.2-apa-descope-2026-09-13"
                   if descoped else "kappa-20-hitl-operational-r3-efficient-2026-09-11"),
        "ui_base": ("R33 hand-edited interface (per-reviewer storage, draft "
                    "autosave, gate control, field navigator, responsive), "
                    "archived at AF apps/kappa_review_r3/r33_hand_edits/, "
                    "merged on David's ruling 2026-09-14" if descoped else None),
        "amendment_basis": ("David Kirsh descope ruling 2026-09-13 (apa_citation is a lookup "
                            "problem) + round-4 review fixes; earlier basis: "
                            "REVIEW_VERDICT_R3_EFFICIENT/R3_AMENDMENT/R3_1_2026-09-13_claude_opus.md"
                            if descoped else
                            "REVIEW_VERDICT_R3_EFFICIENT_2026-09-13_claude_opus.md A1-A6; "
                            "second-round refusal fixed A1(b) brief and static audit set"),
        "machine_resolved_count": len(descoped),
        "parent_pack_sha256": parent_review["pack_sha256"],
        "parent_manifest_sha256": parent_manifest_sha,
        "scientific_content_sha256": sci,
        "scientific_inputs_changed": False,
        "built_by": "fable, Article_Finder scripts/revise_kappa_r3_efficient.py",
        "authority": "David Kirsh chat ruling 2026-09-11 (efficient version inside the pilot)",
        "changed_surface": [
            "queue_logic.js: per-stratum one-sided-80% Wilson stop rule with "
            "fail-fast, disagreement-first ordering, STATIC seeded audit set",
            "app.js: queue delegation, progress-count-only strata strip (no "
            "verdicts shown during review), stop-state in exports only",
            "review_data: efficient_queue block (ranks + config only; no route-B "
            "values), neutral reviewer brief",
        ] + ([f"apa_citation descoped: {len(descoped)} items machine-adjudicated "
              "against DOI-anchored pipeline APAs (ids only in pack; verdicts in "
              "AF receipts/apa_machine_adjudication.json)"] if descoped else []),
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
