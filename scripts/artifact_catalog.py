#!/usr/bin/env python3
"""ATLAS Artifact Catalog — the parent 'what is genuinely in' registry.

Implements the core of docs/ARTIFACT_CATALOG_DESIGN_PROPOSAL_2026-06-15.md:
  * a generic `artifact` table (PROV 'entity') covering pipeline AND beside-pipeline objects
  * a `producer_activity` table (PROV 'activity')
  * register_artifact(...)  -> the push-registration API agents must call
  * crawl_repo(...)         -> the pull backstop (GOODS lesson) that catches anything unregistered

SAFETY: writes ONLY to its own catalog DB (default data/artifact_catalog.db).
It NEVER mutates web_persistence_v7.db or article_eater_lifecycle.db.
Folding this into lifecycle.db (the recommended single-store end state) is a separate, gated step.

Usage:
    python3 scripts/artifact_catalog.py crawl        # scan repo + (re)populate catalog
    python3 scripts/artifact_catalog.py show         # print canonical artifact per role
    python3 scripts/artifact_catalog.py export-json  # regenerate CANONICAL_ARTIFACTS.json from catalog
"""
from __future__ import annotations
import os, sys, json, glob, hashlib, sqlite3, datetime, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Display root for user-facing paths. Overridable so the script is portable across checkouts
# (improvement from the data-lake review: no hardcoded host literals).
HOST = os.environ.get("ARTIFACT_CATALOG_HOST", "/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery")
CATALOG = os.environ.get("ARTIFACT_CATALOG_DB", os.path.join(ROOT, "data", "artifact_catalog.db"))
CAP = 50 * 1024 * 1024  # skip hashing files larger than this (record size+mtime instead) for speed
NOW = lambda: datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

# Directories we never crawl (vendored, frozen, or transient backups).
SKIP_DIRS = (".venv", "node_modules", ".git", "archive", "quarantine",
             "data/backups", "_ballistic_backups", "__pycache__")

# Pinned canonical DBs (authority lives in code/contracts, not in mtime heuristics).
PINNED = {
    f"{ROOT}/data/rebuild/web_persistence_v7.db": ("web_db", "src/services/db_locator.py"),
    f"{ROOT}/data/article_eater_lifecycle.db": ("lifecycle_db", "contracts/LIFECYCLE_DB_DISCIPLINE_v1.md"),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS artifact (
    artifact_id        TEXT PRIMARY KEY,   -- content hash or role:path identity (FAIR id)
    role               TEXT,               -- web_db, lifecycle_db, substitution_graph_db, run_output, skill, contract, misc_db
    kind               TEXT,               -- file | directory | sqlite_db | skill
    path               TEXT,               -- host-form absolute path
    content_sha256     TEXT,
    size_bytes         INTEGER,
    mtime              TEXT,
    status             TEXT,               -- canonical | superseded | stray | active
    supersedes_id      TEXT,
    registered_at      TEXT,
    registered_by      TEXT,               -- agent/script that registered it
    note               TEXT
);
CREATE TABLE IF NOT EXISTS producer_activity (
    activity_id   TEXT PRIMARY KEY,
    name          TEXT,
    kind          TEXT,
    ran_at        TEXT,
    note          TEXT
);
CREATE TABLE IF NOT EXISTS lineage (
    produced_id   TEXT,                 -- artifact_id of the output
    consumed_id   TEXT,                 -- artifact_id of an input
    activity_id   TEXT,                 -- producer_activity that made the edge
    recorded_at   TEXT,
    PRIMARY KEY (produced_id, consumed_id)
);
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER, applied_at TEXT);
CREATE INDEX IF NOT EXISTS ix_artifact_role ON artifact(role, status);
CREATE INDEX IF NOT EXISTS ix_artifact_sha ON artifact(content_sha256);
"""

# Role cardinality (improvement I2): how many canonicals a role may have.
#   singleton -> exactly one canonical (web_db, lifecycle_db, ...)
#   family    -> one canonical per family-key (run_output, latest per lane)
#   set       -> no single canonical (skill, contract)
ROLE_CARDINALITY = {
    # singleton: exactly one canonical
    "web_db": "singleton", "lifecycle_db": "singleton", "pipeline_lifecycle_db": "singleton",
    "substitution_graph_db": "singleton", "registry_db": "singleton", "misc_db": "singleton",
    "article_finder_db": "singleton", "artifact_catalog_db": "singleton",
    "pipeline_state_db": "singleton",
    # family: one canonical per family-key
    "run_output": "family",
    # set: many legitimately-distinct members, no single canonical
    "skill": "set", "contract": "set", "deprecated_db": "set", "control_plane_db": "set",
    "orchestrator_db": "set", "execution_state_db": "set", "extraction_db": "set",
    "other_lifecycle_db": "set",
}
def cardinality(role): return ROLE_CARDINALITY.get(role, "singleton")

def host(p): return p if p.startswith("/Users/") else f"{HOST}/{os.path.relpath(p, ROOT)}"
def skip(p): return any(s in p for s in SKIP_DIRS)

def sha256(p):
    """Content identity. Full hash for files <= CAP; a content-sensitive fingerprint
    (size + first MB + last MB) for larger files so big DBs still get distinct, stable ids."""
    if not os.path.isfile(p): return None
    size = os.path.getsize(p)
    h = hashlib.sha256()
    if size <= CAP:
        with open(p, "rb") as fh:
            for c in iter(lambda: fh.read(1 << 20), b""): h.update(c)
        return h.hexdigest()
    # large file: fingerprint head+tail+size (cheap, still changes when content changes)
    h.update(str(size).encode())
    with open(p, "rb") as fh:
        h.update(fh.read(1 << 20))
        fh.seek(-(1 << 20), os.SEEK_END)
        h.update(fh.read(1 << 20))
    return "fp:" + h.hexdigest()

def connect():
    os.makedirs(os.path.dirname(CATALOG) or ".", exist_ok=True)
    db = sqlite3.connect(CATALOG, timeout=30)
    db.execute("PRAGMA journal_mode=WAL")      # concurrent readers + one writer
    db.execute("PRAGMA busy_timeout=30000")    # wait, don't error, under contention
    db.executescript(SCHEMA)
    return db

def register_artifact(db, *, role, path, kind, status="active",
                      registered_by="crawler", supersedes_id=None, note=""):
    """Push-registration API. Identity is the PATH (a location catalog tracks one row per
    location); content_sha256 is a duplicate-detection attribute, NOT the primary key — so a
    byte-identical copy can never overwrite the canonical's row."""
    sha = sha256(path) if os.path.isfile(path) else None
    aid = f"{role}:{os.path.relpath(path, ROOT)}"
    st = os.stat(path) if os.path.exists(path) else None
    db.execute(
        """INSERT INTO artifact(artifact_id,role,kind,path,content_sha256,size_bytes,mtime,
                                status,supersedes_id,registered_at,registered_by,note)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(artifact_id) DO UPDATE SET
             role=excluded.role, kind=excluded.kind, path=excluded.path,
             content_sha256=excluded.content_sha256,
             size_bytes=excluded.size_bytes, mtime=excluded.mtime, status=excluded.status,
             supersedes_id=excluded.supersedes_id, registered_at=excluded.registered_at,
             registered_by=excluded.registered_by, note=excluded.note""",
        (aid, role, kind, host(path), sha,
         st.st_size if st else None,
         datetime.datetime.utcfromtimestamp(st.st_mtime).strftime("%Y-%m-%dT%H:%M:%SZ") if st else None,
         status, supersedes_id, NOW(), registered_by, note))
    return aid

def role_for_db(p):
    """Map a DB file to its role. Precise: distinct databases get distinct roles so the
    catalog never claims one DB is a 'superseded' copy of an unrelated one. Covers the AF + AE
    pipeline so nothing legitimate lands in the misc catch-all."""
    if p in PINNED: return PINNED[p][0]
    b = os.path.basename(p)
    rp = os.path.relpath(p, ROOT)
    # deprecated / legacy stores — kept for history, explicitly NOT current ("living in the past")
    if ("legacy" in b or "legacy_from_deprecated/" in rp or "_backup_" in b
            or b in ("ae.db", "article_eater.db")):
        return "deprecated_db"
    if b.startswith("web_persistence"): return "web_db"
    if b.startswith("pipeline_lifecycle"): return "pipeline_lifecycle_db"   # distinct from lifecycle_db
    if b.startswith("article_eater_lifecycle") or b == "lifecycle.db": return "lifecycle_db"
    if "lifecycle" in b: return "other_lifecycle_db"
    if b.startswith("substitution_graph"): return "substitution_graph_db"
    if "registry" in b: return "registry_db"
    if "control_plane" in b: return "control_plane_db"
    if "orchestrator" in b: return "orchestrator_db"
    if "execution_state" in b: return "execution_state_db"
    if b.startswith("article_finder"): return "article_finder_db"
    if "extraction" in b or "mathpix/" in rp: return "extraction_db"
    if b.startswith("artifact_catalog"): return "artifact_catalog_db"
    if b == "pipeline_state.db": return "pipeline_state_db"
    return "misc_db"

# A DB at one of these locations is a backup/transient and may NEVER be the canonical
# for its role — only a pinned or top-level live file can be canonical.
NON_CANONICAL_LOCATIONS = ("/data/backups/", "/data/run_logs/", "/lifecycle_backups/",
                           "/_ballistic", "/recovery_snapshots/")

def _canonical_eligible(p):
    rp = "/" + os.path.relpath(p, ROOT)
    return not any(loc in rp for loc in NON_CANONICAL_LOCATIONS)

def verify_registered(db, paths):
    """Enforcement primitive: return the subset of `paths` NOT present in the catalog
    (by host-form path). A run whose outputs are unregistered fails this check."""
    known = {r[0] for r in db.execute("SELECT path FROM artifact").fetchall()}
    missing = []
    for p in paths:
        if host(p) not in known:
            missing.append(p)
    return missing

# ---------- I1: lineage (entity/activity/edges) ----------
def register_activity(db, *, name, kind="run", note=""):
    aid = f"act:{name}:{NOW()}"
    db.execute("INSERT OR REPLACE INTO producer_activity(activity_id,name,kind,ran_at,note) VALUES(?,?,?,?,?)",
               (aid, name, kind, NOW(), note))
    return aid

def record_lineage(db, *, produced_id, consumed_id, activity_id):
    db.execute("""INSERT OR REPLACE INTO lineage(produced_id,consumed_id,activity_id,recorded_at)
                  VALUES(?,?,?,?)""", (produced_id, consumed_id, activity_id, NOW()))

class run:
    """I5: low-friction registration. Usage:
        with run(db, lane='toulmin_v2', name='shadow_batch') as r:
            r.output('data/run_logs/.../proof.json', role='run_output', inputs=[claim_map_id])
    Auto-registers each output, links it to declared inputs, and stamps the activity."""
    def __init__(self, db, *, lane, name):
        self.db, self.lane, self.name = db, lane, name
    def __enter__(self):
        self.activity_id = register_activity(self.db, name=f"{self.lane}/{self.name}")
        return self
    def output(self, path, *, role, kind="file", status="active", inputs=()):
        aid = register_artifact(self.db, role=role, path=path, kind=kind, status=status,
                                registered_by=self.name)
        for src in inputs:
            record_lineage(self.db, produced_id=aid, consumed_id=src, activity_id=self.activity_id)
        return aid
    def __exit__(self, *exc):
        self.db.commit()
        return False

# ---------- I2: invariant checker ----------
def doctor(db):
    """Return a list of invariant violations. Empty list = healthy."""
    v = []
    for role, n in db.execute("""SELECT role, COUNT(*) FROM artifact WHERE status='canonical'
                                 GROUP BY role""").fetchall():
        card = cardinality(role)
        if card == "singleton" and n > 1:
            v.append(f"singleton role '{role}' has {n} canonicals (must be at most 1)")
        if card == "set" and n != 0:
            v.append(f"set role '{role}' has {n} canonicals (must be 0; sets have no single canonical)")
    # no SINGLETON canonical may live in a backup/transient location.
    # (family roles like run_output legitimately live under data/run_logs/.)
    for role, path in db.execute("SELECT role,path FROM artifact WHERE status='canonical'").fetchall():
        if cardinality(role) == "singleton" and any(loc in path for loc in NON_CANONICAL_LOCATIONS):
            v.append(f"singleton canonical '{role}' is in a non-canonical location: {path}")
    return v

# ---------- I3: duplicate-reclamation report ----------
def dupes(db):
    """Group by content hash to find byte-identical copies across paths; report reclaimable bytes."""
    rows = db.execute("""SELECT content_sha256, COUNT(*) c, SUM(size_bytes) tot, MAX(size_bytes) one
                         FROM artifact WHERE content_sha256 IS NOT NULL AND size_bytes>0
                         GROUP BY content_sha256 HAVING c>1 ORDER BY (tot-one) DESC""").fetchall()
    reclaimable = sum((r[2] or 0) - (r[3] or 0) for r in rows)
    return rows, reclaimable

def _walk(root):
    """os.walk with in-place pruning of heavy/frozen dirs (fast; never descends .venv)."""
    dbs, skills = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if not any(s in os.path.join(dirpath, d) for s in SKIP_DIRS)]
        for f in filenames:
            p = os.path.join(dirpath, f)
            if f.endswith(".db") and not re.search(r"\.(bak|tmp)", f) and "shadow" not in f:
                dbs.append(p)
            elif f == "SKILL.md":
                skills.append(p)
    return dbs, skills

def crawl_repo(db):
    counts = {}
    all_dbs, all_skills = _walk(ROOT)
    # 1) all real DBs
    dbs = all_dbs
    by_role = {}
    for p in dbs:
        by_role.setdefault(role_for_db(p), []).append(p)
    for role, paths in by_role.items():
        if cardinality(role) == "set":
            # set roles hold distinct members; none is 'the' canonical. Mark each truthfully.
            for p in paths:
                st = ("stray" if os.path.getsize(p) == 0
                      else "deprecated" if role == "deprecated_db" else "active")
                register_artifact(db, role=role, path=p, kind="sqlite_db", status=st)
            counts[f"db:{role}"] = len(paths)
            continue
        # singleton: canonical = pinned, else largest non-empty AMONG CANONICAL-ELIGIBLE
        # (a backup/run-log copy can never win, no matter how large or new).
        pinned = [p for p in paths if p in PINNED]
        eligible = [p for p in paths if _canonical_eligible(p)]
        nonempty = [p for p in eligible if os.path.getsize(p) > 0]
        # an empty file is NEVER canonical; a role with only empty/ineligible files has no canonical.
        canon = (pinned[0] if pinned else
                 (max(nonempty, key=os.path.getsize) if nonempty else None))
        for p in paths:
            if p == canon:
                st = "canonical"
            elif os.path.getsize(p) == 0:
                st = "stray"          # empty duplicate (e.g. data/substitution_graph.db)
            else:
                st = "superseded"
            register_artifact(db, role=role, path=p, kind="sqlite_db", status=st,
                              note="pinned by contract" if p in PINNED else "")
        counts[f"db:{role}"] = len(paths)
    # 2) skills (beside-pipeline artifacts — e.g. the SC editor skill)
    skills = all_skills
    for p in skills:
        register_artifact(db, role="skill", path=os.path.dirname(p), kind="skill", status="active")
    counts["skills"] = len(skills)
    # 3) run-output families: latest dated dir per family = current
    rl = f"{ROOT}/data/run_logs"
    fam = {}
    if os.path.isdir(rl):
        for d in glob.glob(f"{rl}/*"):
            if not os.path.isdir(d): continue
            key = re.sub(r"[_-]?\d{8}T?\d*Z?$", "", os.path.basename(d))
            fam.setdefault(key, []).append(d)
        for key, dirs in fam.items():
            cur = max(dirs, key=os.path.getmtime)
            for d in dirs:
                register_artifact(db, role="run_output", path=d, kind="directory",
                                  status="canonical" if d == cur else "superseded",
                                  note=f"family={key}")
        counts["run_output_families"] = len(fam)
        counts["run_output_dirs"] = sum(len(v) for v in fam.values())
    db.commit()
    return counts

def show(db):
    print(f"{'ROLE':22s} {'STATUS':11s} PATH")
    for r in db.execute("""SELECT role,status,path FROM artifact
                           WHERE status='canonical' ORDER BY role"""):
        print(f"{r[0]:22s} {r[1]:11s} {r[2].replace(HOST+'/','')}")
    tot = db.execute("SELECT COUNT(*) FROM artifact").fetchone()[0]
    sup = db.execute("SELECT COUNT(*) FROM artifact WHERE status IN('superseded','stray')").fetchone()[0]
    print(f"\nregistered artifacts: {tot}  (superseded/stray: {sup})")

def export_json(db):
    roles = {}
    for r in db.execute("SELECT role,status,path,content_sha256,size_bytes,mtime FROM artifact ORDER BY role,status"):
        e = {"path": r[2], "sha256": r[3], "size_bytes": r[4], "mtime": r[5]}
        roles.setdefault(r[0], {"canonical": None, "other": []})
        if r[1] == "canonical" and roles[r[0]]["canonical"] is None:
            roles[r[0]]["canonical"] = e
        else:
            roles[r[0]]["other"].append({**e, "status": r[1]})
    out = os.path.join(ROOT, "CANONICAL_ARTIFACTS.json")
    json.dump({"schema": "canonical_artifacts_v1", "generated_at": NOW(),
               "generated_by": "scripts/artifact_catalog.py export-json", "roles": roles},
              open(out, "w"), indent=2)
    print("wrote", host(out))

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "crawl"
    db = connect()
    if cmd == "crawl":
        c = crawl_repo(db)
        print("crawl complete:", json.dumps(c))
        show(db)
    elif cmd == "show":
        show(db)
    elif cmd == "export-json":
        export_json(db)
    elif cmd == "check":
        # Enforcement gate: `check <path> [<path> ...]` exits non-zero if any is unregistered.
        missing = verify_registered(db, sys.argv[2:])
        if missing:
            print("UNREGISTERED ARTIFACTS (register before producing):")
            for m in missing: print("  ", m)
            sys.exit(1)
        print("OK: all paths registered")
    elif cmd == "doctor":
        v = doctor(db)
        if v:
            print("CATALOG INVARIANT VIOLATIONS:")
            for x in v: print("  -", x)
            sys.exit(1)
        print("OK: catalog invariants hold")
    elif cmd == "dupes":
        rows, reclaimable = dupes(db)
        print(f"duplicate content groups: {len(rows)}   reclaimable: {reclaimable/1e9:.2f} GB")
        for sha, c, tot, one in rows[:15]:
            print(f"  {c:3d} copies  {(tot-one)/1e6:8.1f} MB reclaimable  sha={sha[:16]}")
    else:
        print(__doc__)
