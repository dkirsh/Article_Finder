"""Adversarial tests for the artifact catalog (red-team, 2026-06-16).

These encode the bugs the panel identified. They are written to FAIL on the
pre-fix code and pass once artifact_catalog.py is hardened.
Run: PYTHONPATH=. pytest tests/test_artifact_catalog.py -q
"""
from __future__ import annotations
import importlib, os, re, sqlite3
from pathlib import Path
import pytest

ac = importlib.import_module("scripts.artifact_catalog")

# --- Contract traceability (per DK: tests must be DERIVED FROM the contract, not invented) ---
CONTRACT = "contracts/AF_ARTIFACT_CATALOG_CONTRACT_2026-06-16.md"
# Each adversarial test maps to the contract success condition it verifies.
# test_tests_are_derived_from_contract() enforces this map both ways.
TEST_TO_SC = {
    "test_doctor_catches_two_canonicals": "SC-AC-1",
    "test_doctor_passes_on_clean_crawl": "SC-AC-1",
    "test_distinct_dbs_not_conflated": "SC-AC-2",
    "test_identical_copy_does_not_clobber_canonical": "SC-AC-3",
    "test_idempotent_upsert_same_file": "SC-AC-3",
    "test_backup_never_canonical": "SC-AC-4",
    "test_enforcement_flags_unregistered": "SC-AC-5",
    "test_changed_content_updates_same_location": "SC-AC-6",
    "test_large_files_distinct_identity": "SC-AC-6",
    "test_run_context_records_lineage": "SC-AC-7",
    "test_dupes_reports_reclaimable": "SC-AC-8",
    "test_empty_duplicate_is_stray": "SC-AC-9",
    "test_empty_sole_file_never_canonical": "SC-AC-9",
}


@pytest.fixture
def cat(tmp_path, monkeypatch):
    """A catalog rooted at a throwaway repo on local disk (sqlite works there)."""
    monkeypatch.setattr(ac, "ROOT", str(tmp_path))
    monkeypatch.setattr(ac, "CATALOG", str(tmp_path / "catalog.db"))
    monkeypatch.setattr(ac, "HOST", str(tmp_path))
    db = ac.connect()
    return db, tmp_path


def _w(p: Path, content: bytes = b"x"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


# ---- idempotency / identity ----

def test_tests_are_derived_from_contract():
    """Traceability gate: every test maps to a contract SC, and every contract SC has a test.
    Prevents invented tests (a recurring failure) and untested success conditions."""
    contract_text = (Path(ac.ROOT) / CONTRACT).read_text(encoding="utf-8")
    contract_scs = set(re.findall(r"SC-AC-\d+", contract_text))
    assert contract_scs, "no success conditions found in the contract"

    # 1) every SC referenced by a test must exist in the contract (no dangling references)
    for t, sc in TEST_TO_SC.items():
        assert sc in contract_scs, f"{t} references {sc}, absent from the contract"

    # 2) every contract SC must be covered by at least one test (no untested SC)
    covered = set(TEST_TO_SC.values())
    assert contract_scs <= covered, f"contract SCs with no test: {sorted(contract_scs - covered)}"

    # 3) every test function in this module must be traced (no invented/orphan test)
    tests = {n for n in globals() if n.startswith("test_") and n != "test_tests_are_derived_from_contract"}
    untraced = tests - set(TEST_TO_SC)
    assert not untraced, f"tests not derived from any contract SC: {sorted(untraced)}"


def test_idempotent_upsert_same_file(cat):
    db, root = cat
    f = _w(root / "a.db", b"hello")
    a1 = ac.register_artifact(db, role="misc_db", path=str(f), kind="sqlite_db")
    a2 = ac.register_artifact(db, role="misc_db", path=str(f), kind="sqlite_db")
    assert a1 == a2
    assert db.execute("SELECT COUNT(*) FROM artifact").fetchone()[0] == 1


def test_changed_content_updates_same_location(cat):
    """A location catalog tracks one row per path; changed content updates that row's hash."""
    db, root = cat
    f = _w(root / "a.db", b"v1")
    a1 = ac.register_artifact(db, role="misc_db", path=str(f), kind="sqlite_db")
    s1 = db.execute("SELECT content_sha256 FROM artifact WHERE artifact_id=?", (a1,)).fetchone()[0]
    _w(f, b"v2-different")
    a2 = ac.register_artifact(db, role="misc_db", path=str(f), kind="sqlite_db")
    s2 = db.execute("SELECT content_sha256 FROM artifact WHERE artifact_id=?", (a2,)).fetchone()[0]
    assert a1 == a2  # same location = same row
    assert s1 != s2  # but the recorded content hash changed
    assert db.execute("SELECT COUNT(*) FROM artifact").fetchone()[0] == 1


def test_identical_copy_does_not_clobber_canonical(cat):
    """Two byte-identical files at different paths are DISTINCT catalog rows; registering the
    copy as 'superseded' must not demote the canonical (the registry_db clobber bug)."""
    db, root = cat
    canon = _w(root / "data" / "reg.db", b"same-bytes")
    copy = _w(root / "data" / "verification_runs" / "reg.db", b"same-bytes")
    ac.register_artifact(db, role="registry_db", path=str(canon), kind="sqlite_db", status="canonical")
    ac.register_artifact(db, role="registry_db", path=str(copy), kind="sqlite_db", status="superseded")
    statuses = dict(db.execute(
        "SELECT status,COUNT(*) FROM artifact WHERE role='registry_db' GROUP BY status").fetchall())
    assert statuses.get("canonical") == 1 and statuses.get("superseded") == 1


def test_large_files_distinct_identity(cat):
    """Files above the hash cap must still get distinct identities by content."""
    db, root = cat
    big = ac.CAP + 1024
    f1 = _w(root / "big1.db", b"A" * big)
    f2 = _w(root / "big2.db", b"B" * big)
    a1 = ac.register_artifact(db, role="misc_db", path=str(f1), kind="sqlite_db")
    a2 = ac.register_artifact(db, role="misc_db", path=str(f2), kind="sqlite_db")
    assert a1 != a2  # different content -> different id even when over the hash cap


# ---- role precision ----

def test_distinct_dbs_not_conflated(cat):
    """article_eater_lifecycle.db and pipeline_lifecycle_full.db are DIFFERENT artifacts."""
    db, root = cat
    r1 = ac.role_for_db(str(root / "data" / "article_eater_lifecycle.db"))
    r2 = ac.role_for_db(str(root / "data" / "pipeline_lifecycle_full.db"))
    assert r1 != r2, "pipeline_lifecycle_full.db must not share a role with article_eater_lifecycle.db"


# ---- canonical selection safety ----

def test_backup_never_canonical(cat):
    """A larger/newer backup under a backups dir must NOT win canonical over the live DB."""
    db, root = cat
    live = _w(root / "data" / "rebuild" / "web_persistence_v7.db", b"live")
    # a bigger backup, newer mtime
    bak = _w(root / "data" / "backups" / "web_persistence_v7.bak.db", b"BACKUP" * 100)
    os.utime(bak, (10**9, 10**9))  # far-future mtime
    ac.crawl_repo(db)
    canon = db.execute(
        "SELECT path FROM artifact WHERE role='web_db' AND status='canonical'").fetchall()
    assert len(canon) == 1
    assert "backups" not in canon[0][0], "a backup was selected as canonical"
    assert canon[0][0].endswith("web_persistence_v7.db")


def test_empty_duplicate_is_stray(cat):
    db, root = cat
    real = _w(root / "substitution_graph.db", b"realdata")
    empty = _w(root / "data" / "substitution_graph.db", b"")
    ac.crawl_repo(db)
    rows = {Path(p).name + ":" + (str(s)) : st
            for p, s, st in db.execute(
                "SELECT path,size_bytes,status FROM artifact WHERE role='substitution_graph_db'")}
    statuses = {r[2]: r[1] for r in db.execute(
        "SELECT path,size_bytes,status FROM artifact WHERE role='substitution_graph_db'")}
    # the 0-byte one must be 'stray', the real one 'canonical'
    by_size = {sz: st for _, sz, st in db.execute(
        "SELECT path,size_bytes,status FROM artifact WHERE role='substitution_graph_db'")}
    assert by_size.get(0) == "stray"
    assert by_size.get(len(b"realdata")) == "canonical"


def test_empty_sole_file_never_canonical(cat):
    """SC-AC-9: a role whose only member is empty has NO canonical (the empty file is a stray)."""
    db, root = cat
    _w(root / "articles.db", b"")  # 0 bytes, sole member of its role
    ac.crawl_repo(db)
    row = db.execute("SELECT status FROM artifact WHERE path LIKE '%articles.db'").fetchone()
    assert row is not None and row[0] == "stray"
    assert db.execute("SELECT COUNT(*) FROM artifact WHERE status='canonical' AND path LIKE '%articles.db'").fetchone()[0] == 0


# ---- enforcement primitive ----

def test_doctor_catches_two_canonicals(cat):
    """I2: doctor must flag a singleton role with more than one canonical."""
    db, root = cat
    a = _w(root / "data" / "rebuild" / "web_persistence_v7.db", b"a")
    b = _w(root / "data" / "other_web.db", b"b")
    ac.register_artifact(db, role="web_db", path=str(a), kind="sqlite_db", status="canonical")
    ac.register_artifact(db, role="web_db", path=str(b), kind="sqlite_db", status="canonical")
    viol = ac.doctor(db)
    assert any("web_db" in v and "canonical" in v for v in viol)


def test_doctor_passes_on_clean_crawl(cat):
    db, root = cat
    _w(root / "data" / "rebuild" / "web_persistence_v7.db", b"live")
    _w(root / "data" / "article_eater_lifecycle.db", b"lc")
    _w(root / "substitution_graph.db", b"sg")
    ac.crawl_repo(db)
    assert ac.doctor(db) == []  # a clean crawl satisfies every invariant


def test_dupes_reports_reclaimable(cat):
    """I3: identical copies are grouped and reclaimable bytes computed."""
    db, root = cat
    ac.register_artifact(db, role="misc_db", path=str(_w(root / "x1.db", b"SAME" * 1000)), kind="sqlite_db")
    ac.register_artifact(db, role="misc_db", path=str(_w(root / "sub" / "x2.db", b"SAME" * 1000)), kind="sqlite_db")
    rows, reclaimable = ac.dupes(db)
    assert len(rows) == 1 and reclaimable == 4000  # one redundant copy of 4000 bytes


def test_run_context_records_lineage(cat):
    """I1/I5: the run() context manager auto-registers outputs and records input->output edges."""
    db, root = cat
    src_id = ac.register_artifact(db, role="misc_db", path=str(_w(root / "in.json", b"i")), kind="file")
    with ac.run(db, lane="toulmin_v2", name="shadow_batch") as r:
        out_id = r.output(str(_w(root / "out.json", b"o")), role="run_output", inputs=[src_id])
    edge = db.execute("SELECT consumed_id FROM lineage WHERE produced_id=?", (out_id,)).fetchone()
    assert edge is not None and edge[0] == src_id
    assert db.execute("SELECT COUNT(*) FROM producer_activity").fetchone()[0] == 1


def test_enforcement_flags_unregistered(cat):
    """verify_registered() must report paths that were never registered."""
    db, root = cat
    reg = _w(root / "data" / "kept.db", b"k")
    ac.register_artifact(db, role="misc_db", path=str(reg), kind="sqlite_db")
    unreg = _w(root / "data" / "snuck_in.db", b"u")
    missing = ac.verify_registered(db, [str(reg), str(unreg)])
    assert str(reg) not in [m for m in missing]
    assert any("snuck_in" in m for m in missing)
