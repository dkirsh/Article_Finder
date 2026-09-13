"use strict";
/* Negative-control test suite for the R3 queue logic. Run: node test_kappa_r3_queue_logic.js
 * A checker that passes both good and broken input checks nothing — half of these
 * fixtures MUST be caught (not released / re-opened / refused). */
const path = require("path");
const QL = require(path.join(__dirname, "../apps/kappa_review_r3/queue_logic.js"));

let passed = 0, failed = 0;
function check(name, condition) {
  if (condition) { passed += 1; console.log(`  ok  ${name}`); }
  else { failed += 1; console.log(`FAIL  ${name}`); }
}

const CFG = QL.DEFAULT_STOP_CONFIG;

function mkItems(stratum, count, role = "human_kappa_evaluation") {
  return Array.from({length: count}, (_, i) => ({
    item_id: `P${String(i).padStart(2, "0")}-${stratum}`, paper_id: `P${String(i).padStart(2, "0")}`,
    evaluation_role: role, phase: "core", priority: 1, stratum,
  }));
}
function respond(items, verdicts) {
  const out = {};
  verdicts.forEach((v, i) => { if (v) out[items[i].item_id] = {verdict: v, confidence: 4, context_sufficient: true}; });
  return out;
}

// --- Wilson bounds at the calibrated budgets ---
check("mechanical releases at n=5 zero errors (UB<=0.15)",
  QL.wilsonUpperBound(0, 5, CFG.z_one_sided_80) <= 0.15 + 1e-9);
check("NEGATIVE: n=4 zero errors does not quite clear 0.15 (UB=0.1504)",
  QL.wilsonUpperBound(0, 4, CFG.z_one_sided_80) > 0.15);
check("semantic bound clears 0.10 by n=7 zero errors (math)",
  QL.wilsonUpperBound(0, 7, CFG.z_one_sided_80) <= 0.10 + 1e-9);
check("semantic min_n is 10 — release waits for David's 10-15 band (A5)",
  CFG.classes.semantic.min_n === 10);
check("NEGATIVE: 1 error in 8 does not clear 0.10",
  QL.wilsonUpperBound(1, 8, CFG.z_one_sided_80) > 0.10);
check("fail-fast: 4 errors in 5 condemns (LB>=0.35)",
  QL.wilsonLowerBound(4, 5, CFG.z_one_sided_80) >= 0.35);
check("NEGATIVE: 2 errors in 10 neither releases nor condemns",
  QL.wilsonUpperBound(2, 10, CFG.z_one_sided_80) > 0.15 &&
  QL.wilsonLowerBound(2, 10, CFG.z_one_sided_80) < 0.35);

// --- stop state ---
{
  const items = mkItems("sample_n", 18);
  const good = respond(items, ["exactly_correct", "exactly_correct", "exactly_correct", "exactly_correct", "exactly_correct"]);
  const st = QL.strataStopState(items, good, CFG).sample_n;
  check("5 clean judgments release a mechanical stratum", st.released && st.settled && !st.condemned);
  const bad = respond(items, ["incorrect", "incorrect", "incorrect", "source_does_not_answer", "exactly_correct"]);
  const st2 = QL.strataStopState(items, bad, CFG).sample_n;
  check("4 errors in 5 condemn the stratum", st2.condemned && st2.settled && !st2.released);
  const mixed = respond(items, ["incorrect", "exactly_correct", "incorrect", "exactly_correct",
    "exactly_correct", "exactly_correct", "exactly_correct", "exactly_correct", "exactly_correct", "exactly_correct"]);
  const st3 = QL.strataStopState(items, mixed, CFG).sample_n;
  check("NEGATIVE: 2 errors in 10 stays open", !st3.settled);
  const undec = respond(items, ["cannot_decide", "cannot_decide", "exactly_correct"]);
  const st4 = QL.strataStopState(items, undec, CFG).sample_n;
  check("cannot_decide stays out of the bound's n", st4.n === 1 && st4.undecided === 2);
  const weird = respond(items, ["banana", "exactly_correct", "totally_new_verdict",
    "exactly_correct", "exactly_correct", "exactly_correct", "exactly_correct"]);
  const st6 = QL.strataStopState(items, weird, CFG).sample_n;
  check("NEGATIVE (A6): unrecognised verdicts are excluded, never successes",
    st6.n === 5 && st6.undecided === 2 && st6.errors === 0);
  check("verdictClass triage", QL.verdictClass("incorrect") === "error" &&
    QL.verdictClass("exactly_correct") === "success" && QL.verdictClass("banana") === "excluded");
  const demoItems = mkItems("sample_n", 6, "demo_only_non_evaluation");
  const st5 = QL.strataStopState(demoItems, respond(demoItems,
    ["exactly_correct", "exactly_correct", "exactly_correct", "exactly_correct"]), CFG);
  check("demo items feed no stop state", Object.keys(st5).length === 0);
}

// --- audit re-open (the guard must bite) ---
{
  const items = mkItems("p_value", 20);
  const responses = respond(items, ["exactly_correct", "exactly_correct", "exactly_correct", "exactly_correct", "exactly_correct"]);
  const before = QL.strataStopState(items, responses, CFG).p_value;
  responses[items[10].item_id] = {verdict: "incorrect", confidence: 4, context_sufficient: true};
  const after = QL.strataStopState(items, responses, CFG).p_value;
  check("an audit error RE-OPENS a released stratum", before.released && !after.released && !after.settled);
}

// --- efficient queue behavior ---
{
  const strata = ["sample_n", "direction"];
  const items = [];
  for (const s of strata) items.push(...mkItems(s, 12));
  const demo = mkItems("sample_n", 2, "demo_only_non_evaluation")
    .map((it, i) => ({...it, item_id: `DEMO${i}-sample_n`, paper_id: `DEMO${i}`}));
  items.push(...demo);
  const data = {items, efficient_queue: {
    seed: "t", stop_rule: CFG,
    paper_order: [...new Set(items.map((i) => i.paper_id))],
    item_rank: Object.fromEntries(items.map((i, n) => [i.item_id, n])),
  }};
  const sampleItems = items.filter((i) => i.stratum === "sample_n" && i.evaluation_role === "human_kappa_evaluation");
  const responses = respond(sampleItems, ["exactly_correct", "exactly_correct", "exactly_correct", "exactly_correct", "exactly_correct"]);
  const snapshot = JSON.stringify(items);
  const result = QL.efficientQueue(data, responses);
  check("PURITY (A4): efficientQueue mutates no input item", JSON.stringify(items) === snapshot);
  check("audit membership is returned, not smuggled via flags",
    Array.isArray(result.audit) && result.audit.length >= 1 &&
    result.audit.every((id) => result.queue.includes(id)));
  const inQueue = new Set(result.queue);
  check("released stratum sheds unanswered items", result.skipped.length > 0);
  const fullAudit = QL.staticAuditSet(items, data.efficient_queue, CFG);
  check("audit obligation: every audit member is answered or queued, never skipped",
    [...fullAudit].every((id) => responses[id] || inQueue.has(id)) &&
    fullAudit.size >= 1);
  check("answered items never leave the queue", sampleItems.slice(0, 5).every((i) => inQueue.has(i.item_id)));
  check("demo items always required", demo.every((i) => inQueue.has(i.item_id)));
  check("open stratum keeps all items",
    items.filter((i) => i.stratum === "direction").every((i) => inQueue.has(i.item_id)));
  check("queue+skipped partition the base set",
    result.queue.length + result.skipped.length === items.length);
  const again = QL.efficientQueue(data, responses);
  check("queue is deterministic across rebuilds", JSON.stringify(again.queue) === JSON.stringify(result.queue));
  check("audit set is static: identical across rebuilds",
    JSON.stringify(again.audit.sort()) === JSON.stringify(result.audit.sort()));
  check("no audit member is ever skipped",
    result.skipped.every((id) => !new Set(result.audit).has(id)));

  // THE DRIP REGRESSION (second review round): answer everything the queue
  // ever asks; the process must terminate with items still skipped, not
  // trickle the whole pack back one item per save.
  const drip = {};
  let asked = 0, guard = 0;
  for (;;) {
    const r = QL.efficientQueue(data, drip);
    const next = r.queue.find((id) => !drip[id]);
    if (!next) break;
    drip[next] = {verdict: "exactly_correct", confidence: 4, context_sufficient: true};
    asked += 1;
    guard += 1;
    if (guard > items.length + 5) break;
  }
  const finalState = QL.efficientQueue(data, drip);
  check("NEGATIVE (drip): perfect reviewer is never asked the full pack",
    asked < items.length && finalState.skipped.length > 0);
  check("drip loop terminates within item count", guard <= items.length);
}

// --- machine-resolved items are invisible to the human machinery ---
{
  const items = [...mkItems("apa_citation", 8), ...mkItems("direction", 6)];
  const resolvedIds = items.slice(0, 5).map((i) => i.item_id); // 5 of 8 apa items
  const data = {items, efficient_queue: {
    seed: "t2", stop_rule: CFG, machine_resolved_items: resolvedIds,
    paper_order: [...new Set(items.map((i) => i.paper_id))],
    item_rank: Object.fromEntries(items.map((i, n) => [i.item_id, n])),
  }};
  const result = QL.efficientQueue(data, {});
  const everywhere = new Set([...result.queue, ...result.skipped, ...result.audit]);
  check("resolved items appear nowhere (queue/skipped/audit)",
    resolvedIds.every((id) => !everywhere.has(id)));
  const st = QL.strataStopState(items, {}, CFG, new Set(resolvedIds));
  check("stop-rule counts exclude resolved items", st.apa_citation.total_items === 3);
  check("unresolved apa items remain fully required", result.queue.length === 3 + 6);
}

// --- fallback without overlay reproduces R2 ordering ---
{
  const items = [
    {item_id: "B-x", paper_id: "B", evaluation_role: "human_kappa_evaluation", phase: "core", priority: 2, stratum: "s"},
    {item_id: "A-y", paper_id: "A", evaluation_role: "human_kappa_evaluation", phase: "core", priority: 1, stratum: "s"},
    {item_id: "A-x", paper_id: "A", evaluation_role: "human_kappa_evaluation", phase: "core", priority: 2, stratum: "s"},
  ];
  const result = QL.efficientQueue({items}, {});
  // R2 paper order is order of first appearance in items (B before A here),
  // then priority within a paper.
  check("no-overlay fallback = R2 paper-major/priority order",
    JSON.stringify(result.queue) === JSON.stringify(["B-x", "A-y", "A-x"]) && result.stopState === null);
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
