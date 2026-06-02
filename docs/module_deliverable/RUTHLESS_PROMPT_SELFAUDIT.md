# Self-audit against the instructor's ruthless prompt (Dhruv's Article Finder)

The instructor's review supplied a 10-point ruthless prompt for this branch.
Each point below is answered with current evidence (file + how to reproduce).
Commands run from the `Article_Finder` repo root unless noted.

| # | Ruthless-prompt question | Status | Evidence / how to reproduce |
|---|---|---|---|
| 1 | Does PDF acquisition actually retrieve a PDF (Unpaywall/OpenAlex) vs always `miss`? | **REAL (proven)** | `task3/pdf_acquirer.py` real fetchers behind `--enable-network`; downloads + `%PDF`-validates + SHA-256 + `acquired` transition. Proven: `T2_LIVE=1 python3 task3/tests_task2_task3.py` downloads PLOS `10.1371/journal.pone.0173955` → 829,365-byte PDF, sha `616f6081…`, via Unpaywall. |
| 2 | Can the scidownl gate ever safely open; is it legal, logged, non-default? | **Gated, default-closed, logged** | `pdf_acquirer.scidownl_gate()` requires 4 conditions (flag + countersigned `policy_clearance.json` + DOI + prior cascade exhausted); default denies `gated:config_flag_off`; every attempt logged to `lifecycle_transitions`. Not implemented as a live downloader. |
| 3 | Does abstract collection work with real S2/CrossRef/PubMed/OpenAlex? | **REAL (proven)** | `T2_LIVE=1` test records sources: Crossref/OpenAlex/S2 all return the real 1377-char abstract for `10.3390/ijerph20085576`; all fetchers return `str|None` on junk (never raise). |
| 4 | Is the Article Eater handoff a real integration or a local stub? | **Stub — clearly labeled** | `ae_handoff.py` writes `data/handoff/*.json`; `ae_inbox_stub.py` is explicitly the AE-side **stub** (consumes/validates). Labeled as a substitute in `task3/docs/TASK3_CONTRACT.md §0/§0.1` and `ATTRIBUTION`/README. No claim of real AE integration. |
| 5 | Does dedup work across DOI, title, hash, AND downstream AE inventory? | **DOI+title+hash yes; AE-inventory = local probe** | `article_references` has `UNIQUE(doi)` (duplicate DOIs impossible in buffer); `search_runner` dedups on insert (DOI + normalized title); handoff is idempotent via `handoff_log UNIQUE(reference_id)`; `probe_pdf_against_article_eater` checks the local inventory (documented substitute for real AE). |
| 6 | Are tests portable from a clean checkout, or do they need sibling repos / absolute paths? | **Portable** | `gap_extractor` no longer `sys.exit`s on missing data; `tests_task2_task3.py` SKIPs the data-dependent checks when `mechanisms.json` is absent; `validate_task1.py` locates `atlas_shared` via install→`$KA_ATLAS_SHARED_SRC`→sibling and SKIPs cleanly (exit 0) if absent; constitutions are repo-bundled. No `/private/tmp` paths. |
| 7 | Does any module call `sys.exit` during import or pytest collection? | **No** | `gap_extractor.extract_gaps` raises `FileNotFoundError`; `tests_task2_task3.py` guards `sys.exit` under `__main__` and exposes `test_task2_task3_suite`. `pytest task3/tests_task2_task3.py` → 1 passed (was: collection abort). |
| 8 | Are PRISMA counts reconstructed from DB state, not hand-authored JSON? | **DB-derived** | `prisma_dashboard.PRISMA_SQL` is a single `GROUP BY` over `article_references`; tests assert funnel identity + completeness (15 fields, 5 disjoint buckets) against a separate manual `GROUP BY`. |
| 9 | Does the query generator produce papers, not just plausible query strings? | **Honest scope** | `query_generator.py` produces query *pairs* (AI-Citation + Boolean) with closed-enum quality flags; *paper retrieval* is `search_runner.py` (mock backend by default; SerpAPI/scholarly/paperscraper wired). Queries → candidates, not papers directly — stated plainly, not overclaimed. |
| 10 | Are all documentation claims strictly supported by runnable evidence? | **Yes** | Every claim here maps to a command. Suites: Task 1 `42/42`, Task 2+3 `44/44` (offline) / `47/47` (`T2_LIVE=1`), chain `9/9`. Stubs (AE, scidownl) are labeled as stubs, not integrations. |

## Reproduce everything
```bash
# Article_Finder root
python3 -m pytest task3/tests_task2_task3.py -q          # pytest-collectable, passes
python3 task3/tests_task2_task3.py                       # 44/44 offline
T2_LIVE=1 python3 task3/tests_task2_task3.py             # 47/47 incl. real abstract + real OA PDF
python3 scripts/verify_track2_workflow.py                # CHAIN 9/9 (incl. AE-consume)
python3 task3/pdf_acquirer.py --enable-network           # real OA download on the live queue

# Knowledge_Atlas root
python3 data/test_pdfs/validate_task1.py                 # 42/42 (graceful SKIP if atlas_shared absent)
```

## Honest limits (unchanged, deliberate)
- Article Eater is **not** on this checkout; the handoff sink + dedup probe are documented local substitutes (drop-in when AE is mounted).
- scidownl is a gated, default-closed stub — not a live downloader.
- Live abstract + live PDF tests are **opt-in** (`T2_LIVE=1`) so default CI stays offline/deterministic.
