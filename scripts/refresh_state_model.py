#!/usr/bin/env python3
"""Re-derive the VOLATILE section of docs/REPO_STATE_MODEL_AND_PLAN.md BY EXECUTION.

READ-ONLY -- every database is opened with mode=ro. Writes only the document's generated header.

WHY. A stale orientation document reads as current, which makes it worse than none. The Build Ledger
norm in the root CLAUDE.md gives the rule: status fields come from real runs, not claims.

THE MEASUREMENTS THAT EXIST TO CATCH A SPECIFIC LIE:

  1. THE TWO-DATABASE TRAP. articles.db sits at the repo root at 0 bytes while the real corpus is
     data/article_finder.db at ~529 MB. Resolve "the articles database" by name and you get the empty
     one. Both are measured every run, ADJACENTLY, with a -wal sidecar check on each -- because a
     0-byte SQLite file can also be a WAL-mode database whose content is in the sidecar
     (corpus CASE-019), and "empty" must be a measurement here, never an inference.

  2. THE OUTCOME-VOCABULARY TRIPLICATION. Outcome_Contractor is the declared canonical authority for
     human-side terms, and this repo ALSO carries utils/outcome_resolver.py plus
     config/outcome_taxonomy.yaml, and imports atlas_shared. Three definitions of one vocabulary is
     the exact divergence a controlled vocabulary exists to prevent. Their presence is re-checked so
     section 7.4 retires itself when the reconciliation lands.

  3. THE AF->AE CONTRACT SURFACE. Four AF_AE_* authority documents govern the handoff to
     Article_Eater. If one disappears or is renamed, section 2's chain and section 6-C's plan are
     describing a boundary that no longer has that governance.

BOUNDARY: every figure prints the command that produced it. A figure with no command is a defect.
Counts exclude venv/, .git and __pycache__ and SAY SO -- in the paired Outcome_Contractor, a walk
that included venv/ reported 643 TypeScript files where the true number is 3, and that error
inverted the description of the repo.
"""
import os
import re
import subprocess
import sys
import time

AF = "/Users/davidusa/REPOS/Article_Finder_v3_2_3"
DOC = os.path.join(AF, "docs", "REPO_STATE_MODEL_AND_PLAN.md")
OC_AF = "/Users/davidusa/REPOS/Outcome_Contractor/article_finder"

SKIP = ("venv", ".git", "__pycache__", "node_modules", ".egg-info", "dist", "build")

# Section 4 / 7.2. Listed adjacently and deliberately: the empty one and the real one.
DBS = ["articles.db", "data/article_finder.db"]

# Section 7.4. Presence, not content -- the point is that three definitions coexist.
OUTCOME_SITES = ["utils/outcome_resolver.py", "config/outcome_taxonomy.yaml",
                 "config/outcome_lookup.json"]


def run(cmd, cwd=AF, timeout=180):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, shell=isinstance(cmd, str))
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except Exception as exc:
        return -1, "", str(exc)[:120]


def walk_count(root, pred):
    n = 0
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if not any(k in d for k in SKIP)]
        n += sum(1 for f in fn if pred(f))
    return n


def measure():
    out = []
    rc, head, _ = run(["git", "rev-parse", "--short", "HEAD"])
    out.append(("HEAD", "git rev-parse --short HEAD", head if rc == 0 else "UNKNOWN"))
    rc, n, _ = run(["git", "rev-list", "--count", "HEAD"])
    rc2, last, _ = run(["git", "log", "-1", "--format=%ad %s", "--date=short"])
    out.append(("commits / last commit (section 7.7)", "git rev-list --count; git log -1",
                "%s commits; %s" % (n if rc == 0 else "?", (last or "?")[:70])))

    ver = os.path.join(AF, "VERSION")
    out.append(("declared VERSION", "cat VERSION",
                open(ver, encoding="utf-8").read().strip() if os.path.isfile(ver) else "ABSENT"))

    # 1. THE TWO-DATABASE TRAP -- adjacent, with sidecar checks.
    import sqlite3
    for rel in DBS:
        p = os.path.join(AF, rel)
        if not os.path.isfile(p):
            out.append((rel, "stat + -wal check", "not present"))
            continue
        size = os.path.getsize(p)
        wal = os.path.getsize(p + "-wal") if os.path.isfile(p + "-wal") else None
        desc = "%.1f MB" % (size / (1024.0 * 1024.0))
        desc += (", -wal %.1f MB" % (wal / (1024.0 * 1024.0))) if wal is not None else ", no -wal"
        if size == 0 and wal is None:
            desc += "  → genuinely zero-length (NOT WAL blindness) — section 7.2"
        elif size > 0:
            try:
                con = sqlite3.connect("file:%s?mode=ro" % p, uri=True)
                tabs = [r[0] for r in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")]
                con.close()
                desc += "; %d tables" % len(tabs)
            except Exception as exc:
                desc += "; OPEN FAILED: %s" % str(exc)[:45]
        out.append((rel, "stat + -wal check + sqlite_master (mode=ro)", desc))

    # 2. THE OUTCOME-VOCABULARY TRIPLICATION.
    present = [r for r in OUTCOME_SITES if os.path.exists(os.path.join(AF, r))]
    oc_auth = os.path.isdir("/Users/davidusa/REPOS/Outcome_Contractor/ontology/domains")
    out.append(("outcome vocabulary defined HERE as well as in Outcome_Contractor (section 7.4)",
                "stat %s" % ", ".join(OUTCOME_SITES),
                ("%d/%d present: %s" % (len(present), len(OUTCOME_SITES), ", ".join(present)))
                + ("; Outcome_Contractor ontology also present — still triplicated"
                   if oc_auth and present else
                   "; reconciled? re-read section 7.4" if not present else "")))

    # 3. THE AF->AE CONTRACT SURFACE.
    cdir = os.path.join(AF, "contracts")
    if os.path.isdir(cdir):
        cs = sorted(os.listdir(cdir))
        af_ae = [c for c in cs if c.startswith("AF_AE_")]
        out.append(("contracts/ total", "ls contracts", len(cs)))
        out.append(("...of which AF_AE_* handoff authorities (section 2, plan C)",
                    "ls contracts/AF_AE_*",
                    "%d: %s" % (len(af_ae), ", ".join(c[:46] for c in af_ae))
                    if af_ae else "*** NONE — section 2's governed boundary is gone"))
        out.append(("contracts/ports.json (README: source of truth for ports — section 7.3)",
                    "stat contracts/ports.json",
                    "present" if "ports.json" in cs else
                    "*** ABSENT — the README names it as authoritative; section 7.3 is now wrong"))
    else:
        out.append(("contracts/", "ls", "*** ABSENT"))

    sdir = os.path.join(AF, "schemas")
    if os.path.isdir(sdir):
        ae = sorted(f for f in os.listdir(sdir) if f.startswith("ae.") and f.endswith(".json"))
        out.append(("schemas/ae.*.v1 — the shared language with Article_Eater",
                    "ls schemas/ae.*.json", "%d: %s" % (len(ae), ", ".join(a[3:-13] for a in ae))))

    out.append(("python modules (venv/.git/__pycache__ EXCLUDED — section 7.1)",
                "walk minus %s" % (SKIP[:3],), walk_count(AF, lambda f: f.endswith(".py"))))
    out.append(("test files", "same walk, test_*.py",
                walk_count(AF, lambda f: f.startswith("test_") and f.endswith(".py"))))

    # Section 7.5: the OTHER article-finding implementation. Filename overlap, because the SIZE of
    # the overlap is what distinguishes "a fork we can diff" from "two implementations we cannot".
    if os.path.isdir(OC_AF):
        def names(root):
            s = set()
            for dp, dn, fn in os.walk(root):
                dn[:] = [d for d in dn if not any(k in d for k in SKIP)]
                s |= {f for f in fn if f.endswith(".py")}
            return s
        here, there = names(AF), names(OC_AF)
        out.append(("Outcome_Contractor/article_finder overlap (section 7.5)",
                    "walk both for *.py, compare basenames",
                    "%d here, %d there, %d shared — a SMALL shared count means independent "
                    "implementations, not a fork" % (len(here), len(there), len(here & there))))
    else:
        out.append(("Outcome_Contractor/article_finder", "stat",
                    "absent — section 7.5 is STALE, rewrite it"))

    rc3, sz, _ = run(["du", "-sh", AF])
    out.append(("total repo size (section 7.1 — almost none of it is source)", "du -sh .",
                sz.split()[0] if rc3 == 0 and sz else "?"))
    out.append(("zip files at repo root (section 7.1, 7.8)", "ls *.zip",
                len([f for f in os.listdir(AF) if f.endswith(".zip")])))
    return out


def rewrite_header(head):
    if not os.path.isfile(DOC):
        return False, "state model document absent at %s" % DOC
    text = open(DOC, encoding="utf-8").read()
    missing = [k for k in ("STATE_AS_OF", "HEAD") if not re.search(r"- `%s: [^`]*`" % k, text)]
    if missing:
        return False, "generated markers absent (%s)" % ", ".join(missing)
    stamp = time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime())
    new = re.sub(r"- `STATE_AS_OF: [^`]*`", "- `STATE_AS_OF: %s`" % stamp, text, count=1)
    new = re.sub(r"- `HEAD: [^`]*`", "- `HEAD: %s`" % head, new, count=1)
    if new == text:
        return True, stamp + " (already current)"
    open(DOC, "w", encoding="utf-8").write(new)
    return True, stamp


def main():
    rows = measure()
    print("ARTICLE_FINDER STATE REFRESH — every figure beside the command that produced it")
    print("=" * 94)
    head = "UNKNOWN"
    for label, cmd, val in rows:
        if label == "HEAD":
            head = str(val)
        print("  %-58s %s" % (label, val))
        print("  %-58s   <- %s" % ("", cmd))
    print("-" * 94)
    ok, info = rewrite_header(head)
    print("HEADER REWRITTEN — %s, HEAD %s" % (info, head) if ok else "NOT REWRITTEN: %s" % info)
    print()
    print("Sections 1-4 and 7 are hand-maintained. Transcribe the figures above into section 5.")
    print("Any line beginning '***' is a claim in the document that has just gone FALSE.")
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
