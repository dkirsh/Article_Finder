#!/usr/bin/env python3
"""CHECK — is the repo's state model still describing THIS repo?

READ-ONLY. Detector for the stale-orientation-doc failure.

WHY. This repo already had a good onboarding map that went stale (docs/AI_ONBOARDING_README.md,
2026-07-10, written before an entire rebuild). Nothing announced the drift. A newcomer reading it
today would be confidently misinformed, which is worse than being uninformed, because a stale
document supplies false confidence along with the false facts. Writing a *replacement* solves nothing
unless something notices when the replacement ages -- otherwise this is the disclosure-instead-of-
remedy pattern applied to documentation (corpus CASE-028).

TWO FAILING CONDITIONS, both mechanical:
  1. AGE     -- the doc's STATE_AS_OF is older than its own declared STALE_AFTER_DAYS.
  2. DRIFT   -- the doc's recorded HEAD is not an ancestor of the current HEAD, i.e. it describes a
                repo state this one did not come from (a rewritten or diverged history), OR the
                recorded HEAD is unknown to git at all.
Age alone is soft: a repo nobody touched is not stale. So age is only reported as a finding when
commits have actually landed since the recorded HEAD -- otherwise the doc is old but still true.

POSITIVE CONTROL (exit 4 if it fails): a synthetic header dated far in the past with a bogus HEAD
MUST be judged stale. A freshness checker that cannot recognise a stale document is reporting its
own blindness.
NEGATIVE CONTROL (exit 5 if it fails): a synthetic header dated now, at the live HEAD, must be
judged fresh.

BOUNDARY: this checks WHEN the doc was refreshed and WHETHER the repo moved. It cannot tell whether
the doc's prose is TRUE — a refreshed timestamp on a wrong description passes. Freshness is
necessary, never sufficient.
"""
import os
import re
import subprocess
import sys
import time

DEFAULT_STALE_DAYS = 7

# REPO ROOT: argv[1], else the git root of the cwd, else this file's repo. Parameterised 2026-08-03
# so the check can be dropped into any of the eleven repos unchanged. It was hardcoded to
# Article_Eater, which is why propagation had not happened: the blocker was never the idea, it was
# one constant.
def _repo_root():
    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
        return os.path.abspath(sys.argv[1])
    try:
        p = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=10)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()
    except Exception:
        pass
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


AE = _repo_root()

# EXTENDED 2026-08-03: this checked exactly one document. A second orientation doc then landed
# (the Evidence Network subsystem model) and would have aged unwatched -- which is the very failure
# this file exists to detect, reproduced by the detector's own scope. Scope, not sensitivity, was
# the defect: the judging logic was already right. Add documents HERE as they are written; a state
# model with no row in this list is unwatched.
DOCS = [
    (os.path.join(AE, "docs", "REPO_STATE_MODEL_AND_PLAN.md"),
     "python3 scripts/refresh_state_model.py"),
    (os.path.join(AE, "docs", "SUBSYSTEM_STATE_MODEL_EVIDENCE_NETWORK.md"),
     "python3 scripts/refresh_en_state_model.py"),
    # ADDED 2026-08-03 the hour it was written, per section 9 of the state model: "the freshness
    # check should cover the human introduction too once it exists -- a stale introduction misleads
    # MORE people than a stale state model, because more people read it and fewer are equipped to
    # notice." Registering it at birth rather than later is the point: the previous two documents
    # were both added to this list retroactively, and between writing and registering they were
    # exactly the unwatched artifact this file exists to catch.
    #
    # No refresher script, deliberately. Its content is JUDGED, not derived by execution -- there is
    # no command that can re-derive "why a web rather than a table". The refresh instruction is
    # therefore addressed to a person, and the JUDGED arm is what actually watches this document.
    (os.path.join(AE, "docs", "INTRODUCTION_FOR_NEWCOMERS.md"),
     "re-read sections 1-6 (section 6's figures are the ones that rot), then set JUDGED_REVIEWED"),
]


# TYPED WATCH, added 2026-08-03 at David's direction: "define them as file types in the sense that a
# contract is a type. So a list of key files always gets stale. But that TYPE of file is one that
# grows when a new file of that type is created."
#
# The enumerated DOCS list above is exactly the failure he described. It has already been wrong twice:
# the Evidence Network model and the newcomers' introduction were both written and then, separately,
# remembered. Between writing and remembering, each was the unwatched artifact this file exists to
# catch.
#
# So membership is now a PROPERTY, not a list: any markdown file under docs/ carrying a
# `STATE_AS_OF:` header line IS a state model and IS watched, from the moment it is saved. The list
# above is kept only to supply each doc's specific refresh command, and a doc absent from it is still
# watched -- with a generic instruction rather than none.
HEADER_MARK = re.compile(r"^- `STATE_AS_OF: ", re.M)


def discovered_docs(root):
    """(path, refresh_cmd) for every docs/*.md carrying a STATE_AS_OF header. Never raises."""
    known = {p: c for p, c in DOCS}
    found = []
    docs_dir = os.path.join(root, "docs")
    try:
        names = sorted(os.listdir(docs_dir))
    except OSError:
        return [(p, c) for p, c in DOCS if os.path.isfile(p)]
    for fn in names:
        if not fn.endswith(".md"):
            continue
        p = os.path.join(docs_dir, fn)
        try:
            if not HEADER_MARK.search(open(p, encoding="utf-8", errors="replace").read(4096)):
                continue
        except OSError:
            continue
        found.append((p, known.get(p, "re-derive this document's generated header, then set "
                                     "JUDGED_REVIEWED after re-reading its judgements")))
    # A DOCS entry that is MISSING or has lost its header is a finding -- but ONLY in the repo the
    # list was written for.
    #
    # CORRECTED 2026-08-03 during propagation, caught by running each install in place rather than
    # assuming it. DOCS is built with os.path.join(AE, ...), so once AE became the local repo root,
    # every repo was told to watch Article_Eater's three specific documents -- including
    # SUBSYSTEM_STATE_MODEL_EVIDENCE_NETWORK.md, which is AE-only and will never exist elsewhere.
    # Ten repos each reported a phantom absent document. Generalising the ROOT without generalising
    # the LIST was half a fix, and the half that was missing produced a false finding in every repo
    # it was installed into.
    #
    # In any other repo, discovery-by-header is the sole mechanism: whatever carries the header is
    # watched, and nothing is demanded that the repo never had.
    if os.path.basename(root) == "Article_Eater_PostQuinean_v1_recovery":
        for p, c in DOCS:
            if p not in {x for x, _ in found}:
                found.append((p, c))

    # THE SILENT ZERO. Added 2026-08-03 immediately after propagation exposed it: New_VR_Platform HAS
    # a docs/REPO_STATE_MODEL_AND_PLAN.md, but it carries no `STATE_AS_OF:` header, so the typed watch
    # could not see it and the check reported a quiet "watched: 0" with every control green.
    #
    # A repo whose state model is invisible to the watcher is EXACTLY the unwatched-artifact failure
    # this file exists to detect -- arriving as an absence of output. Silence is the one result a
    # detector must never be allowed to return for its own target class. So a conventionally-named
    # state model that lacks the header is included deliberately, and judge() will report its missing
    # header as unparseable rather than skipping it.
    conventional = os.path.join(root, "docs", "REPO_STATE_MODEL_AND_PLAN.md")
    if os.path.isfile(conventional) and conventional not in {x for x, _ in found}:
        found.append((conventional,
                      "ADD THE GENERATED HEADER (`- `STATE_AS_OF: ...``, HEAD, STALE_AFTER_DAYS, "
                      "JUDGED_REVIEWED) — without it this state model is invisible to the watcher"))
    return found


def git(args):
    try:
        p = subprocess.run(["git"] + args, cwd=AE, capture_output=True, text=True, timeout=30)
        return p.returncode, p.stdout.strip()
    except Exception:
        return -1, ""


def parse_header(text):
    def grab(key, default=None):
        m = re.search(r"- `%s: ([^`]*)`" % key, text)
        return m.group(1).strip() if m else default
    return {
        "as_of": grab("STATE_AS_OF"),
        "head": grab("HEAD"),
        "stale_days": grab("STALE_AFTER_DAYS", str(DEFAULT_STALE_DAYS)),
        # THE THIRD CLASS. Added 2026-08-03, closing a defect the Image_Tagger reviewer named
        # and neither of us then fixed: this check watched DERIVED and MEASURED content only,
        # so a repo could pass indefinitely while section 1 described a system it had stopped
        # being. Header green, document confidently wrong about the most important thing in
        # it -- the exact failure the state models exist to prevent, inside their own remedy.
        "judged_reviewed": grab("JUDGED_REVIEWED"),
        "judged_interval": grab("JUDGED_REVIEW_INTERVAL_DAYS", "90"),
    }


def age_days(stamp):
    for fmt in ("%Y-%m-%dT%H:%MZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            t = time.strptime(stamp, fmt)
            return (time.time() - time.mktime(t) + time.timezone) / 86400.0
        except (ValueError, TypeError):
            continue
    return None


def judge(hdr, cur_head, commits_since):
    """Return (is_stale, reasons). Pure, so the controls can exercise it directly."""
    reasons = []
    try:
        limit = float(hdr.get("stale_days") or DEFAULT_STALE_DAYS)
    except ValueError:
        limit = DEFAULT_STALE_DAYS
    a = age_days(hdr.get("as_of"))
    if a is None:
        reasons.append("STATE_AS_OF unparseable (%r)" % hdr.get("as_of"))
    elif a > limit and commits_since > 0:
        reasons.append("refreshed %.1f days ago (limit %.0f) AND %d commit(s) landed since"
                       % (a, limit, commits_since))
    # JUDGED arm: the claims no execution can settle (what the system is FOR, a part's real
    # objective, which trap actually cost time). Unlike the MEASURED arm this does NOT require
    # commits to have landed -- judgements rot with the world, not with the repo.
    try:
        jlimit = float(hdr.get("judged_interval") or 90)
    except ValueError:
        jlimit = 90.0
    jr = hdr.get("judged_reviewed")
    if not jr:
        reasons.append("JUDGED_REVIEWED absent — section 1-4/7 judgements are unwatched")
    else:
        ja = age_days(jr)
        if ja is None:
            reasons.append("JUDGED_REVIEWED unparseable (%r)" % jr)
        elif ja > jlimit:
            reasons.append("judgements unreviewed for %.0f days (limit %.0f) — re-read sections "
                           "1-4 and 7, then set JUDGED_REVIEWED" % (ja, jlimit))
    if not hdr.get("head"):
        reasons.append("no HEAD recorded")
    elif cur_head and hdr["head"] not in ("UNKNOWN", cur_head) and commits_since < 0:
        reasons.append("recorded HEAD %s is not an ancestor of current HEAD %s"
                       % (hdr["head"], cur_head))
    return bool(reasons), reasons


def controls():
    today = time.strftime("%Y-%m-%d", time.gmtime())
    now = time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime())
    stale_hdr = {"as_of": "2020-01-01T00:00Z", "head": "deadbee", "stale_days": "7",
                 "judged_reviewed": today, "judged_interval": "90"}
    fresh_hdr = {"as_of": now, "head": "abc1234", "stale_days": "7",
                 "judged_reviewed": today, "judged_interval": "90"}
    # THIRD CONTROL: numbers current, judgements ancient. Must be flagged -- this is the exact
    # blind spot the JUDGED arm was added to close, so it gets its own control rather than
    # riding on the other two.
    judged_hdr = {"as_of": now, "head": "abc1234", "stale_days": "7",
                  "judged_reviewed": "2020-01-01", "judged_interval": "90"}
    pos, _ = judge(stale_hdr, "abc1234", commits_since=5)
    neg, _ = judge(fresh_hdr, "abc1234", commits_since=0)
    jud, _ = judge(judged_hdr, "abc1234", commits_since=0)
    return pos, (not neg), jud


def main():
    pos_ok, neg_ok, jud_ok = controls()
    print("STATE MODEL FRESHNESS CHECK -- read-only")
    print("=" * 76)
    print("POSITIVE CONTROL (an old header at a bogus HEAD must read STALE) : %s"
          % ("FIRED" if pos_ok else "MISSED -- CHECK IS BLIND, IGNORE ITS VERDICT"))
    print("NEGATIVE CONTROL (a header dated now at live HEAD must read fresh): %s"
          % ("PASS" if neg_ok else "FAIL -- flags fresh documents"))
    print("-" * 76)
    print("JUDGED CONTROL (fresh numbers + ancient judgements must read STALE) : %s"
          % ("FIRED" if jud_ok else "MISSED -- the JUDGED arm is blind"))
    print("-" * 76)
    if not pos_ok:
        return 4
    if not neg_ok:
        return 5
    if not jud_ok:
        return 6

    rc, cur_head = git(["rev-parse", "--short", "HEAD"])
    cur_head = cur_head if rc == 0 else ""
    any_stale = False

    watched = discovered_docs(AE)
    print("  repo    : %s" % AE)
    print("  watched : %d document(s) — membership is by HEADER, not by list" % len(watched))
    print("-" * 76)

    for doc, refresh_cmd in watched:
        rel = os.path.relpath(doc, AE)
        print("  document      : %s" % rel)
        if not os.path.isfile(doc):
            print("     STATE MODEL ABSENT at %s" % doc)
            print("     A repo area with no state model cannot be judged fresh or stale — it has")
            print("     nothing to orient a newcomer at all. That is a finding, not a pass.")
            print("-" * 76)
            any_stale = True
            continue

        hdr = parse_header(open(doc, encoding="utf-8").read())
        commits_since = 0
        if hdr.get("head") and hdr["head"] != "UNKNOWN":
            rc2, out = git(["rev-list", "--count", "%s..HEAD" % hdr["head"]])
            commits_since = int(out) if (rc2 == 0 and out.isdigit()) else -1

        stale, reasons = judge(hdr, cur_head, commits_since)
        print("     STATE_AS_OF   : %s" % hdr.get("as_of"))
        print("     recorded HEAD : %s   current HEAD: %s" % (hdr.get("head"), cur_head or "?"))
        print("     commits since : %s" % ("unknown (recorded HEAD not in this history)"
                                           if commits_since < 0 else commits_since))
        if stale:
            any_stale = True
            print("     VERDICT: STALE")
            for r in reasons:
                print("        - %s" % r)
            print("     Refresh with: %s" % refresh_cmd)
        else:
            print("     VERDICT: fresh")
        print("-" * 76)

    stale = any_stale
    print()
    print("BOUNDARY: this checks WHEN the doc was refreshed and WHETHER the repo moved. It cannot")
    print("tell whether the prose is TRUE — a refreshed timestamp on a wrong description passes.")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
