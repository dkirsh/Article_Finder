#!/usr/bin/env bash
# demo.sh — narrated, end-to-end Track 2 demo (Tasks 2 & 3).
#
#   ./demo.sh           # offline, deterministic (~15s)
#   ./demo.sh --live    # also downloads a REAL open-access PDF (needs network)
#
# Everything runs against an isolated temp DB/out ($TRACK2_DB/$TRACK2_OUT); the
# committed tree is restored on exit. atlas_shared is resolved via install or
# $KA_ATLAS_SHARED_SRC (see TRACK2_DELIVERABLE_MAP.md).
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
export KA_ATLAS_SHARED_SRC="${KA_ATLAS_SHARED_SRC:-../atlas_shared/src}"
W="$(mktemp -d /tmp/track2_demo.XXXXXX)"
export TRACK2_DB="$W/demo.db" TRACK2_OUT="$W"
PY=python3
LIVE=0; [ "${1:-}" = "--live" ] && LIVE=1
cleanup(){ git checkout -- query_results.json gap_results.json task3/data 2>/dev/null; rm -rf "$W"; }
trap cleanup EXIT
hr(){ printf '\n\033[1;36m━━ %s ━━\033[0m\n' "$1"; }

hr "TASK 2 · extract low-confidence mechanism gaps + score by VOI"
$PY gap_extractor.py --confidence-threshold 0.6 --output "$W/gaps.json" >/dev/null
$PY - "$W/gaps.json" <<'PY'
import json,sys
g=json.load(open(sys.argv[1])); top=max(g,key=lambda x:x.get("voi_score",0))
print(f"  {len(g)} gaps extracted; highest-VOI gap:")
print(f"    {top['template_id']} — {top['mechanism_name']} ({top['framework_name']})")
print(f"    confidence={top['confidence']}  VOI={top['voi_score']}  gap_type={top['gap_type']}")
print("    voi_breakdown (HONEST — structural/epistemic are null: Track 2 can't compute them):")
print("     ",json.dumps(top["voi_breakdown"]))
PY

hr "TASK 2 · turn the top gap into search queries"
$PY query_generator.py --gaps "$W/gaps.json" --top-n 5 --output "$W/queries.json" >/dev/null 2>&1
$PY - "$W/queries.json" <<'PY'
import json,sys
q=json.load(open(sys.argv[1])); top=q[0]
print(f"  {len(q)} queries generated. For {top['template_id']}:")
print(f"    AI-citation: {top['ai_citation_query'][:150]}...")
bq=top.get("boolean_query") or top.get("boolean") or ""
print(f"    Boolean    : {str(bq)[:150]}")
PY

hr "TASK 3 · run the full pipeline (search→triage→acquire→handoff) on an ISOLATED db"
cp "$W/queries.json" query_results.json
$PY task3/run_pipeline.py --backend mock --voi-threshold 0.50 2>&1 | grep -E "^── |Pipeline complete" | sed 's/^/  /'

hr "TASK 3 · what landed in article_references (provenance preserved)"
sqlite3 "$TRACK2_DB" "select triage_decision, count(*) from article_references group by triage_decision;" 2>/dev/null \
  | awk -F'|' '{printf "    %-14s %s\n",$1,$2}'
echo "  sample row:"
sqlite3 -line "$TRACK2_DB" "select reference_id, doi, triage_stage, discovered_via from article_references limit 1;" 2>/dev/null | sed 's/^/    /'

hr "TASK 3 · PRISMA funnel (computed from ONE SQL GROUP BY)"
[ -f "$W/prisma_funnel.json" ] && $PY -c "import json;d=json.load(open('$W/prisma_funnel.json'));[print(f'    {k:28} {v}') for k,v in d.items()]" || echo "    (no prisma_funnel.json emitted)"
echo "  note: synthetic mock candidates are conservatively triaged to EDGE_CASE (→ human review),"
echo "        so accept=0 here. The handoff below seeds a guaranteed ACCEPT to show the last mile."

hr "TASK 3 · LAST MILE — handoff artefact + REAL Article-Eater delivery seam"
# run from task3 so db_schema / ae_handoff imports resolve
( cd task3 && AE_INBOX="$W/ae_inbox" $PY - <<PY
import json
from pathlib import Path
import db_schema, ae_handoff
conn=db_schema.open_db(Path("$W/handoff.db"))
conn.execute("INSERT INTO article_references (reference_id,doi,title_raw,discovered_via,"
 "triage_stage,triage_decision,abstract,abstract_source,gap_template_id,voi_score,raw_citation,"
 "acquired_paper_id) VALUES ('REF-DEMO','10.1371/journal.pone.0173955','Daylight & attention demo',"
 "'mock_synthetic','acquired','ACCEPT','A real abstract long enough to pass the gate.','s2','GAP-DEMO',"
 "0.82,'Demo et al. 2026','paper:REF-DEMO')")
conn.commit()
res=ae_handoff.write_handoffs(conn,Path("$W/handoff")); conn.close()
art=Path("$W/handoff/REF-DEMO.json")
print("  handoff artefact the Eater reads (task3/docs/TASK3_CONTRACT.md §0.1 schema):")
obj=json.loads(art.read_text())
for k in ("handoff_id","article_id","doi","title","topic","handoff_status"): print(f"    {k:14} {obj[k]}")
out=ae_handoff.deliver_to_ae(art)
print(f"  deliver_to_ae → mode={out['mode']} delivered={out['delivered']} consumed={out['consumed']}")
print(f"    {out['detail']}")
PY
)
echo "  AE inbox now contains: $(ls "$W/ae_inbox" 2>/dev/null | tr '\n' ' ')"

hr "PROOF · labeled triage evaluation (does the classifier actually discriminate?)"
$PY task3/eval_triage.py 2>/dev/null | sed 's/^/  /'

if [ "$LIVE" = "1" ]; then
  hr "PROOF · LIVE — download a REAL open-access PDF (Unpaywall/OpenAlex, magic-byte + SHA gated)"
  T2_LIVE=1 $PY task3/tests_task2_task3.py 2>&1 | grep -iE "PLOS|BMC|pdf|sha|publisher|magic|[0-9]+/[0-9]+ checks" | head -8 | sed 's/^/  /'
fi

hr "DONE"
echo "  Offline suite: python3 task3/tests_task2_task3.py        (51/51)"
echo "  Live suite   : T2_LIVE=1 python3 task3/tests_task2_task3.py (55/55)"
echo "  Chain        : python3 scripts/verify_track2_workflow.py   (9/9)"
echo "  Task 1       : (in Knowledge_Atlas) python3 data/test_pdfs/validate_task1.py (42/42)"
