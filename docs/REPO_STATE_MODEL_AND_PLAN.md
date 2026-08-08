# Article_Finder v3.2.3 — State Model and Plan

**THE DOCUMENT A NEW AI READS FIRST.**

**Generated-state header — the refresher rewrites `STATE_AS_OF`/`HEAD`; the JUDGED pair is set by a
person after re-reading §1–4/§7 (the refresher preserves it verbatim).**
- `STATE_AS_OF: 2026-08-05T06:16Z`
- `HEAD: 10f0e83`
- `STALE_AFTER_DAYS: 7`
- `JUDGED_REVIEWED: 2026-08-06`
- `JUDGED_REVIEW_INTERVAL_DAYS: 90`
- `VERIFIED_BY: scripts/refresh_state_model.py`

> **Judged re-review 2026-08-06 (evidence in the session log):** every §1–4/§7 claim was re-verified
> against the repo by execution. Corrections applied in this pass: §7.7 git history (17→21 commits,
> now current to 2026-08-04), §7.4 (the "`atlas_shared` is imported here" claim was FALSE — zero
> import statements exist; it is a stated preference in `AGENTS.md`), the 529 MB figure (actual
> 516 MB) in four places, §7.1/§7.5 file counts (128 `.py` / 19 test files), the §1 contract count,
> and — the substantive addition — §1/§4 now record the **inbound uncontracted coupling**: Article_Eater
> hardcodes this repo's absolute path in ≥8 scripts and reads `data/article_finder.db` and
> `data/pdfs/` directly, bypassing `eater_interface/` and every `AF_AE_*` contract.

---

## 1. What this is for — the front door of the whole stack

**Article_Finder is where papers come from.** Everything downstream — Article_Eater's claim
extraction, the web of belief, the Bayesian network, the Knowledge_Atlas payload students read —
operates on a corpus this repo assembled. If acquisition is biased, incomplete or duplicated, no
amount of epistemic machinery downstream can repair it.

Its README calls it *"a comprehensive tool for managing and analyzing neuroarchitecture research
literature."* In practice it does four things that are harder than they sound:

- **Find** candidate papers across sources (`search/`, `candidate_discovery/`)
- **Decide** which ones belong (`triage/`, the venue allowlists, PRISMA accounting)
- **Acquire** the PDFs — including paywalled ones, via a two-way Zotero bridge and the UCSD library
  proxy (`zotero_export/`, `docs/ZOTERO_UCSD_SETUP.md`)
- **Hand off** to Article_Eater under signed contracts (`eater_interface/`, `contracts/AF_AE_*`)

**The handoff is the part to respect.** This is not an ad-hoc export. `contracts/` holds three
`AF_AE_*` authority documents governing the AF→AE boundary — corpus dedupe, handoff, and result
ingestion — plus a machine-readable dedupe success-conditions JSON; shared intake classification has
its own `AF_`-prefixed authority with its own success-conditions file. That is unusually disciplined
for a data-acquisition tool, and it exists because a duplicate or misclassified paper crossing that
boundary corrupts the corpus identity that every downstream ID depends on.

**But the contracted door is not the only door — and the other one is ungoverned.** Article_Eater
also reads this repository **directly**: ≥8 AE scripts hardcode
`/Users/davidusa/REPOS/Article_Finder_v3_2_3` (e.g. AE's `scripts/triage_papers_keywords.py:24`) and
consume `data/article_finder.db` and `data/pdfs/` without passing through `eater_interface/` or any
`AF_AE_*` contract. AF declares no interface of its own; AE's cross-repo matrix marks AE-AF-002/003
"active / 100%" on `ae.claim.v2`/`ae.rule.v2` while this repo carries **v1 schemas only**. The
contracted path is real; the traffic is on the uncontracted one.

**Where it sits:**

```
   sources: Scholar · Semantic Scholar · Zotero · venue allowlists · citation chasing
        │
        ▼
   ARTICLE_FINDER  ─── find → triage → acquire → dedupe ───┐
   (this repo)                                             │  contracts/AF_AE_*
        │                                                  │  schemas/ae.*.v1.schema.json
        │  516 MB corpus DB                                ▼
        └──────────────────────────────────────▶  ARTICLE_EATER / ATLAS
                                                   extraction → claims → web of belief
                                                          │
                                                          ▼
                                                   BN_graphical · Knowledge_Atlas
```

---

## 2. The chain of calls

```
   DISCOVERY        candidate_discovery/ · search/     find candidates
        │                                             citation chasing, Scholar, Semantic Scholar
        ▼
   TRIAGE           triage/                           does this belong in the corpus?
        │           config/hbe_journals_allowlist.txt
        │           config/neuroscience_venues_allowlist.txt
        │           → PRISMA accounting: every excluded paper has a recorded reason
        ▼
   ACQUISITION      zotero_export/ · ingest/          get the PDF
        │           two-way Zotero bridge; UCSD library proxy for paywalled papers
        │           `python cli/main.py zotero export|import|stats`
        ▼
   DEDUPE           core/ae_corpus_dedupe.py          one work, one identity
        │           governed by contracts/AF_AE_CORPUS_DEDUPE_AUTHORITY_2026-05-10.md
        ▼
   CORPUS DB        data/article_finder.db  (516 MB)  ← §7.2, and NOT articles.db
        │
        ▼
   HANDOFF          eater_interface/                  cross the boundary to Article_Eater
                    schemas/ae.paper.v1 · ae.claim.v1 · ae.result.v1 · ae.provenance.v1 ·
                            ae.rule.v1 · ae.review_item.v1 · ae.audit_event.v1
                    contracts/AF_AE_HANDOFF_AUTHORITY · AF_AE_RESULT_INGESTION_AUTHORITY

   PORTS            contracts/ports.json              ← the README names this the source of truth
                                                        for every service port. Do not hard-code.
```

**The `ae.*` schemas are the shared language.** This repo carries Article_Eater's own contract
schemas — paper, claim, result, provenance, rule, review item, audit event — so both sides validate
against the same definitions rather than two drifting copies.

---

## 3. The parts and their real objectives

| Part | Its real objective | Success condition (observable) | Lives in |
|---|---|---|---|
| **Discovery** | find what exists, not what is easy to find | recall measured against a known set, not just a count of hits | `candidate_discovery/`, `search/` |
| **Triage** | a defensible corpus boundary | **every exclusion has a recorded reason** (PRISMA); the allowlists are auditable | `triage/`, `config/*allowlist*` |
| **Acquisition** | get the PDF, including paywalled | acquisition rate reported *with* its failure modes; Zotero round-trip works | `zotero_export/`, `ingest/` |
| **Dedupe** | one work → one identity | two records of the same work merge; two genuinely different works never do | `core/ae_corpus_dedupe.py` |
| **Handoff** | AE receives a corpus it can trust | payload validates against `schemas/ae.*.v1`; the AF_AE authority contracts' success conditions hold | `eater_interface/`, `contracts/` |
| **Outcome resolution** | map outcome phrasings to canonical terms | agrees with `Outcome_Contractor` — **which is the canonical authority (§7.4)** | `utils/outcome_resolver.py`, `config/outcome_taxonomy.yaml` |

**The cross-cutting success condition.** Acquisition succeeds when the corpus is *defensible*: you
can say why each paper is in, why each candidate is out, and that no work appears twice under two
identities. A larger corpus is not a better one.

---

## 4. Where things live — and the size traps

| Path | What |
|---|---|
| `data/article_finder.db` | **the corpus — 516 MB.** The live store |
| `data/pdfs/` | **638 entries — Article_Eater's actual read surface** (reached by AE's hardcoded paths, §1) |
| `articles.db` (repo root) | **0 bytes** — see §7.2 |
| `data/article_finder.pre_integrity_repair_2026-05-10.db` | 38 MB pre-repair snapshot — do not delete (RULE 0) |
| `contracts/` | the AF↔AE authority documents + `ports.json` |
| `schemas/ae.*.v1.schema.json` | Article_Eater's contract schemas, seven of them |
| `eater_interface/` | the handoff implementation |
| `config/` | venue allowlists, outcome + environment lookups, taxonomy |
| `core/`, `search/`, `triage/`, `ingest/`, `knowledge/`, `utils/`, `cli/`, `ui/`, `ops/` | the working code |
| `venv/`, 5 root `.zip` files, `new_claude_files_to_chase_articles/` | **not source — §7.1** |

---

## 5. Current state — VOLATILE

| Area | State |
|---|---|
| Version | **directory and README say 3.2.3; `VERSION` says 3.2.4** — §7.9 |
| Repo size | **6.0 GB** — dominated by data, PDFs, `venv/` and zips (§7.1) |
| Python | **128** `.py` · **19** test files — BOUNDARY: `venv/`, `.git`, `__pycache__` excluded |
| Git | **21 commits**; last `81a61f5` 2026-08-04 *"docs: refresh state model header metadata"* |
| Remote | `github.com/dkirsh/Article_Finder_v3_2_3.git` |
| Corpus DB | `data/article_finder.db` **516 MB, 13 tables**, no `-wal` |
| `articles.db` | **0 bytes, no `-wal`** → genuinely zero-length, not WAL blindness (§7.2) |
| Contracts | **19** files, of which **4** are `AF_AE_*` authorities; `ports.json` present |
| Schemas | **7** `ae.*.v1.schema.json` — audit_event, claim, paper, provenance, result, review_item, rule |
| Outcome vocabulary | **3/3 local definition sites still present** alongside `Outcome_Contractor` — still triplicated (§7.4) |
| Root zips | **5** |
| Governance | `GOVERNANCE_REPORT.md` at root — read before working |

---

## 6. The plan

**A — Resolve the outcome-vocabulary triplication.** §7.4. Three places define outcome terms;
`Outcome_Contractor` is the declared canonical authority. Until they are reconciled or one is
declared derived, a claim's outcome term means different things depending on which code path
produced it.

**B — Resolve the two article-finding implementations.** §7.5. `Outcome_Contractor/article_finder/`
independently implements this repo's job. Neither is a fork of the other, so this must be settled by
comparing behaviour, not filenames — and under RULE 0, nothing is retired without that proof.

**C — Prove the AF→AE handoff contracts can fail.** `AF_AE_CORPUS_DEDUPE_SUCCESS_CONDITIONS_2026-05-10.json`
is machine-readable, which is exactly right — now show it rejecting a deliberately bad handoff. Same
defect class flagged in `Outcome_Contractor` §6-C and `BN_graphical` §6-B: a contract that has never
rejected anything is not yet known to be a gate.

**D — Establish what `articles.db` is.** §7.2. A 0-byte database at the repo root with an
almost-canonical name is an accident waiting to be pointed at.

**E — Report acquisition with its denominator.** The valuable number is not "papers acquired" but
"acquired / eligible, with the failure modes of the remainder." That is what tells you whether the
corpus is biased toward the openly accessible.

**F — Characterise the 6 GB.** Measure and propose under RULE 0. The 4 root zips
(`AF_v3_2_3.zip`, `AF_v3_2_3_for Claude.zip`, `AF_v3_2_3_minus_data.zip`, `AF_Data_no_pdfs.zip`) are
unmeasured, therefore potentially unique. Retire nothing without containment proof.

---

## 7. Traps

**7.1 — 6.0 GB, and almost none of it is source.** `venv/`, the PDF corpus, `data/*.db`, four root
zips, `new_claude_files_to_chase_articles/` and its zip. Any repo-wide grep or file count that does
not state its exclusions is unusable — the corrected figures are 128 `.py` and 19 test files. (This is not
hypothetical: in the paired `Outcome_Contractor`, a first pass that walked `venv/` reported 643
TypeScript files where the real number is 3, and drew a false conclusion about what that repo *is*.)

**7.2 — There are two databases and the obvious-looking one is empty.** `articles.db` sits at the
repo root at **0 bytes**; the real corpus is `data/article_finder.db` at **516 MB**. A newcomer
resolving "the articles database" by name picks the wrong one. **Check the size and the table
contents, not the filename** — and note that a 0-byte SQLite file can also be WAL-mode with its
content in a `-wal` sidecar, so check for the sidecar before concluding "empty" either
(corpus CASE-019). *(The same two-files-one-plausible-name trap exists in Article_Eater with
`web_persistence_v7.db`.)*

**7.3 — `contracts/ports.json` is the source of truth for ports**, per the README (line 3).
Hard-coding a port anywhere else will work until it doesn't. And note
`contracts/ports.json.bak_20260102_113731` sits beside it — the two-files-one-plausible-name trap of
§7.2, reproduced inside the ports authority itself. The `.bak` is not the source of truth.

**7.4 — Outcome vocabulary is defined in three places.** `Outcome_Contractor` is the declared
canonical authority for human-side terms; this repo also has `utils/outcome_resolver.py`,
`config/outcome_taxonomy.yaml` and `config/outcome_lookup.json`. (*Corrected 2026-08-06: an earlier
version of this trap said "`atlas_shared` is imported here too" — that is FALSE. Zero
`import atlas_shared` statements exist in any AF `.py`; the 43 grep hits are a stated preference in
`AGENTS.md:16-21` and one migration-function name. The triplication claim stands on the three local
definition sites alone.*) Three definitions of the same vocabulary is exactly the divergence a
controlled vocabulary exists to prevent. §6-A.

**7.5 — A second, independent article-finding pipeline exists in `Outcome_Contractor/article_finder/`**
— 39 Python modules against this repo's 128 files (112 unique basenames), with a measured filename overlap of **2**. They are not
copies and not a fork; they are two implementations of one job, which is harder to reconcile than a
duplicate because there is no shared history to diff. §6-B.

**7.6 — `Oops.rej` is checked in at the repo root.** A rejected-patch artifact. Something did not
apply cleanly and the evidence was left in the tree — worth reading before assuming the working tree
is what someone intended.

**7.7 — The git history is thin (21 commits) but no longer dormant.** *(Corrected 2026-08-06: this
trap previously said "17 commits, last 2026-06-19" — four substantive commits have landed since,
through `81a61f5` 2026-08-04, including the armed repo-root-wipe hook fix and the prevention check.)*
The earlier judgement softens accordingly: the deep reasoning still lives in `contracts/` and
`docs/`, but recent git history *is* now a real development record and should be read.

**7.8 — `AF_v3_2_3_for Claude.zip`** — a snapshot prepared for an agent, with a space in the
filename. Unmeasured, so under RULE 0 it is potentially unique. Do not tidy it away.

**7.9 — The repo disagrees with itself about its own version.** The directory is
`Article_Finder_v3_2_3`, the README's first line is `<!-- Version: 3.2.3 -->` and its heading says
*"Article Finder v3.2.3"* — but the `VERSION` file says **3.2.4**. Three declarations, two answers.
Whichever is right, something shipped without updating the others, so **do not cite a version from
any single one of them**; and note that a handoff or a bug report carrying the wrong version number
is worse than one carrying none. The refresher prints `VERSION` every run so the gap stays visible.

---

## 8. How to verify anything

```bash
python3 cli/main.py zotero stats        # acquisition state
python3 -m pytest tests/ -q             # 20 test files
python3 scripts/refresh_state_model.py  # re-derives §5 by execution
```
Read first: `README.md` (version + Zotero bridge) · **`contracts/AF_AE_HANDOFF_AUTHORITY_2026-05-10.md`
before touching anything that crosses to Article_Eater** · `contracts/ports.json` ·
`CANONICAL_ARTIFACTS.json` · `GOVERNANCE_REPORT.md`. Then read `Outcome_Contractor`'s state model —
§7.4 and §7.5 are joint problems, not local ones.

---

## 9. The companion human introduction

**OWED — this file does not exist yet.** *(Corrected 2026-08-06: this section previously described
`docs/INTRODUCTION_FOR_NEWCOMERS.md` as though present; it has never been written here.)* When
written, it should cover: why finding the papers is a research problem and not a
plumbing problem — that a literature search which returns what is easy to reach produces a corpus
biased toward open access and toward whatever the search engine ranks well, and that PRISMA's
discipline of recording *why each paper was excluded* is what makes the resulting corpus arguable
rather than merely large. One worked example of a near-duplicate pair that must not merge.

---

## 10. Freshness contract

§5 is machine-refreshed, including the corpus DB size and the contract inventory. §1–§4 and §7 are
hand-maintained: change the handoff contracts, the ports file, or the outcome-resolution path, and
update them in the same commit.
