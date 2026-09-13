"use strict";

/* R3 efficient queue logic — supersedes the R2 queue_logic.js at pack-build time.
 * Adds, on top of the R2 expansion logic (kept verbatim below):
 *   - a per-stratum sequential stop rule (one-sided 80% Wilson upper bound on the
 *     observed extraction-error rate; thresholds per stratum class), and
 *   - route-B disagreement-first ordering read from review_data.efficient_queue
 *     (rank integers only; no route-B values ship in the pack), and
 *   - seeded audit retention: a released stratum keeps a deterministic ~15% of its
 *     remaining items in the required queue as a standing spot-audit; any error
 *     there raises the bound and re-opens the stratum automatically.
 * Pure functions only; node-testable (see scripts/test_kappa_r3_queue_logic.js).
 * David Kirsh's budget intuition (3-5 checks for mechanical fields, 10-15 for
 * semantic ones) calibrates to the one-sided 80% bound; the stricter 95%/n~50
 * certification belongs to registry write-back, not this triage instrument. */

(function exposeQueueLogic(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.AEHITLQueueLogic = api;
})(globalThis, function buildQueueLogic() {

  /* ---------- R2 logic, unchanged ---------- */

  function responseTriggersExpansion(response) {
    return Boolean(response) && (
      response.confidence <= 2 ||
      response.context_sufficient === false ||
      [
        "substantively_correct_needs_wording",
        "incorrect",
        "source_does_not_answer",
        "cannot_decide",
      ].includes(response.verdict)
    );
  }

  function activeStrataFromResponses(items, responses) {
    const itemById = new Map(items.map((item) => [item.item_id, item]));
    return [...new Set(
      Object.entries(responses)
        .filter(([itemId, response]) => {
          const item = itemById.get(itemId);
          return item && ["core", "reliability"].includes(item.phase) &&
            responseTriggersExpansion(response);
        })
        .map(([itemId]) => itemById.get(itemId).stratum)
    )].sort();
  }

  /* ---------- R3 additions ---------- */

  const DEFAULT_STOP_CONFIG = {
    z_one_sided_80: 0.8416,
    audit_fraction: 0.15,
    audit_minimum: 1,
    // Fail-fast (the symmetric release): when the Wilson LOWER bound on a
    // stratum's error rate clears this, the field is certified BROKEN — its
    // remedy is re-extraction, not more human confirmations. Skipping the
    // rest of a condemned stratum saves the reviewer exactly as much as
    // skipping a settled one.
    fail_threshold: 0.35,
    classes: {
      mechanical: {threshold: 0.15, min_n: 4,
        strata: ["apa_citation", "article_type", "sample_n", "p_value", "effect_size"]},
      semantic: {threshold: 0.10, min_n: 10,
        strata: ["main_conclusion", "independent_variables", "dependent_variables",
          "construct_pair", "direction", "stimulus_description",
          "methods_surface_summary", "measurement_inventory"]},
    },
  };

  // An extraction the human had to correct, or that claimed a value the paper
  // does not establish, counts as an error. cannot_decide is neither success
  // nor error: it routes to expansion and stays out of the bound's n. An
  // UNRECOGNISED verdict is likewise excluded — it must never count as a
  // success and quietly help release a stratum (reviewer amendment A6).
  const SUCCESS_VERDICTS = ["exactly_correct"];
  const ERROR_VERDICTS = ["incorrect", "source_does_not_answer",
    "substantively_correct_needs_wording"];
  function verdictClass(verdict) {
    if (SUCCESS_VERDICTS.includes(verdict)) return "success";
    if (ERROR_VERDICTS.includes(verdict)) return "error";
    return "excluded";
  }
  function isErrorVerdict(verdict) { return verdictClass(verdict) === "error"; }

  function wilsonUpperBound(errors, n, z) {
    if (n <= 0) return 1;
    const p = errors / n;
    const z2 = z * z;
    const centre = p + z2 / (2 * n);
    const spread = z * Math.sqrt((p * (1 - p)) / n + z2 / (4 * n * n));
    return (centre + spread) / (1 + z2 / n);
  }

  function wilsonLowerBound(errors, n, z) {
    if (n <= 0) return 0;
    const p = errors / n;
    const z2 = z * z;
    const centre = p + z2 / (2 * n);
    const spread = z * Math.sqrt((p * (1 - p)) / n + z2 / (4 * n * n));
    return Math.max(0, (centre - spread) / (1 + z2 / n));
  }

  function stratumClass(stratum, config) {
    for (const [name, cls] of Object.entries(config.classes)) {
      if (cls.strata.includes(stratum)) return {name, ...cls};
    }
    return {name: "semantic", ...config.classes.semantic};
  }

  // Per-stratum stop state from evaluation responses only (demo items never
  // count; machine-resolved items are outside the human measurement entirely).
  function strataStopState(items, responses, config, resolvedIds) {
    const resolved = resolvedIds || new Set();
    const state = {};
    for (const item of items) {
      if (item.evaluation_role !== "human_kappa_evaluation") continue;
      if (!["core", "reliability"].includes(item.phase)) continue;
      if (resolved.has(item.item_id)) continue;
      const s = state[item.stratum] = state[item.stratum] ||
        {n: 0, errors: 0, undecided: 0, total_items: 0};
      s.total_items += 1;
      const response = responses[item.item_id];
      if (!response) continue;
      const cls = verdictClass(response.verdict);
      if (cls === "excluded") { s.undecided += 1; continue; }
      s.n += 1;
      if (cls === "error") s.errors += 1;
    }
    for (const [stratum, s] of Object.entries(state)) {
      const cls = stratumClass(stratum, config);
      s.class = cls.name;
      s.threshold = cls.threshold;
      s.fail_threshold = (config.fail_threshold === undefined) ? 0.35 : config.fail_threshold;
      s.upper_bound = wilsonUpperBound(s.errors, s.n, config.z_one_sided_80);
      s.lower_bound = wilsonLowerBound(s.errors, s.n, config.z_one_sided_80);
      s.released = s.n >= cls.min_n && s.upper_bound <= cls.threshold;
      s.condemned = s.n >= cls.min_n && s.lower_bound >= s.fail_threshold;
      s.settled = s.released || s.condemned;
    }
    return state;
  }

  // Deterministic per-item audit selection so the queue is stable across
  // rebuilds: an item is an audit keeper iff hash(seed, item_id) mod 1000
  // falls under audit_fraction. No RNG state, no ordering dependence.
  function hashString(text) {
    let h = 2166136261 >>> 0;
    for (let i = 0; i < text.length; i += 1) {
      h ^= text.charCodeAt(i);
      h = Math.imul(h, 16777619) >>> 0;
    }
    return h;
  }

  function isAuditKeeper(itemId, seed, fraction) {
    return (hashString(`${seed}:${itemId}`) % 1000) < Math.round(fraction * 1000);
  }

  /* The audit set is STATIC: a pure function of the pack (items + seed +
   * config), never of responses. Per stratum it holds the hash keepers,
   * backfilled to audit_minimum by rank when the hash keeps none. A settled
   * stratum requires exactly its answered items plus its audit-set members —
   * once those are answered the stratum asks for nothing more. (Second
   * review round: a response-dependent top-up dripped skipped items back one
   * per save until every stratum was fully asked, destroying the design.) */
  function staticAuditSet(items, eq, config) {
    const minimum = (config.audit_minimum === undefined) ? 1 : config.audit_minimum;
    const rank = eq.item_rank || {};
    const resolved = new Set(eq.machine_resolved_items || []);
    const byStratum = new Map();
    for (const item of items) {
      if (item.evaluation_role !== "human_kappa_evaluation") continue;
      if (!["core", "reliability"].includes(item.phase)) continue;
      if (resolved.has(item.item_id)) continue;
      if (!byStratum.has(item.stratum)) byStratum.set(item.stratum, []);
      byStratum.get(item.stratum).push(item);
    }
    const set = new Set();
    for (const list of byStratum.values()) {
      const keepers = list.filter((i) =>
        isAuditKeeper(i.item_id, eq.seed || "r3", config.audit_fraction));
      for (const i of keepers) set.add(i.item_id);
      if (keepers.length < minimum) {
        const backfill = list.filter((i) => !set.has(i.item_id))
          .sort((a, b) => (((rank[a.item_id] === undefined ? 999 : rank[a.item_id]) -
                            (rank[b.item_id] === undefined ? 999 : rank[b.item_id])) ||
                           a.item_id.localeCompare(b.item_id)))
          .slice(0, minimum - keepers.length);
        for (const i of backfill) set.add(i.item_id);
      }
    }
    return set;
  }

  /* The R3 queue.
   * Papers are visited whole (reading a paper is the expensive act), ordered by
   * route-B disagreement mass; within a paper, items run disagreement-first.
   * Demo papers stay first, always fully required (they are training).
   * A released stratum's unanswered items drop to optional EXCEPT its audit
   * keepers (plus at least audit_minimum of them, by rank, when the hash keeps
   * none). Answered items always remain in the queue. Falls back to the R2
   * ordering when review_data carries no efficient_queue block. */
  function efficientQueue(data, responses) {
    const items = data.items;
    const eq = data.efficient_queue;
    const activeStrata = new Set(activeStrataFromResponses(items, responses));
    const base = items.filter((item) => ["core", "reliability"].includes(item.phase));
    const extensions = items.filter(
      (item) => item.phase === "extension" && activeStrata.has(item.stratum)
    );
    if (!eq) {
      const paperOrder = [...new Set(items.map((item) => item.paper_id))];
      return {
        queue: [...base, ...extensions].sort((a, b) =>
          (paperOrder.indexOf(a.paper_id) - paperOrder.indexOf(b.paper_id)) ||
          (a.priority - b.priority)).map((item) => item.item_id),
        stopState: null, skipped: [],
      };
    }
    const config = eq.stop_rule || DEFAULT_STOP_CONFIG;
    // Machine-resolved items (David Kirsh descope ruling 2026-09-13: APA is a
    // lookup problem) never reach the human: not queued, not skipped, not
    // audited, and outside every stop-rule count.
    const resolved = new Set(eq.machine_resolved_items || []);
    const stopState = strataStopState(items, responses, config, resolved);
    const rank = eq.item_rank || {};
    const paperPos = new Map((eq.paper_order || []).map((pid, i) => [pid, i]));
    const pos = (item) => {
      const paper = paperPos.has(item.paper_id) ? paperPos.get(item.paper_id) : 999;
      const within = rank[item.item_id] !== undefined ? rank[item.item_id] : 999;
      return paper * 1000 + within;
    };
    // Pure recompute on every call: no input mutated, and audit membership
    // is the STATIC set above — response-independent, so the workload of a
    // settled stratum is bounded by (already answered + audit members).
    const auditIds = staticAuditSet(items, eq, config);
    const required = [];
    const skipped = [];
    for (const item of [...base, ...extensions]) {
      if (resolved.has(item.item_id)) continue;
      const answered = Boolean(responses[item.item_id]);
      const demo = item.evaluation_role !== "human_kappa_evaluation";
      const settled = stopState[item.stratum] && stopState[item.stratum].settled;
      if (answered || demo || !settled || auditIds.has(item.item_id)) {
        required.push(item);
      } else {
        skipped.push(item);
      }
    }
    return {
      queue: required.sort((a, b) => pos(a) - pos(b)).map((item) => item.item_id),
      stopState,
      skipped: skipped.map((item) => item.item_id),
      audit: [...auditIds].filter((id) => required.some((i) => i.item_id === id)),
    };
  }

  return {
    activeStrataFromResponses, responseTriggersExpansion,
    isErrorVerdict, verdictClass, wilsonUpperBound, wilsonLowerBound,
    strataStopState, efficientQueue, isAuditKeeper, staticAuditSet,
    DEFAULT_STOP_CONFIG,
  };
});
