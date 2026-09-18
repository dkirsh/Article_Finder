#!/usr/bin/env python3
"""write_bibliographic_tables.py — land the recovered bibliographic metadata in
the canonical databases (David 2026-09-09: "are you adding that metadata in all
the places we expect to find it such as AF, and an AE dbase?").

Additive only, one new table in each DB (drop to undo), provenance per row:

  paper_bibliographic(paper_id PK, title, venue, year, doi, authors_json,
                      abstract, source, imported_at)

  - Article_Eater lifecycle DB (via db_locator, per DB_REGISTRY)
  - article_finder.db (schema registry is add-if-missing; new table safe)

Sources merged with precedence bib-export > unified registry, abstracts also
falling back to AF's own matched rows. One-example-first before each batch."""
import sqlite3, json, re, sys, datetime
from pathlib import Path

AE = "/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery"
AF = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3")
BIB = Path("/Users/davidusa/REPOS/__Zotero whole bibliography/__Zotero whole bibliography.bib")
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

def bibfield(e, name):
    m = re.search(name + r"\s*=\s*[{\"](.+?)[}\"]\s*,?\s*\n", e, re.I | re.S)
    return re.sub(r"[{}]", "", m.group(1)).replace("\n", " ").strip() if m else None

# build per-folder records from the export
byn = {}
for e in re.split(r"\n@", BIB.read_text(errors="replace")):
    f = bibfield(e, "file")
    if not f: continue
    date = bibfield(e, "year") or bibfield(e, "date") or ""
    ym = re.search(r"(19|20)\d\d", date)
    auth = bibfield(e, "author")
    rec = {"title": bibfield(e, "title"),
           "venue": bibfield(e, "journal") or bibfield(e, "journaltitle")
                    or bibfield(e, "booktitle") or bibfield(e, "publisher"),
           "year": int(ym.group(0)) if ym else None,
           "doi": bibfield(e, "doi"),
           "authors": [a.strip() for a in auth.split(" and ")][:6] if auth else [],
           "abstract": bibfield(e, "abstract")}
    for n in set(re.findall(r"files[/\\](\d+)[/\\]", f)): byn[n] = rec

uni = sqlite3.connect(f"file:{AE}/data/pipeline_registry_unified.db?mode=ro", uri=True)
rows = {}
for pid, zf, ut, ua, uy, uv, uab in uni.execute(
        "SELECT paper_id, zotero_folder, title, authors, year, venue, abstract FROM papers"):
    b = byn.get(zf or "")
    if b and (b["title"] or b["year"]):
        r = dict(b); r["source"] = "zotero_bib_export"
    elif ut or uy:
        r = {"title": ut, "venue": uv, "year": uy, "doi": None,
             "authors": [s.strip() for s in re.split(r";|,(?=\s*[A-Z][a-z])", ua)][:6] if ua else [],
             "abstract": uab, "source": "pipeline_registry_unified"}
    else:
        continue
    rows[pid] = r
print(f"bibliographic rows assembled: {len(rows)}")

DDL = """CREATE TABLE IF NOT EXISTS paper_bibliographic (
    paper_id TEXT PRIMARY KEY, title TEXT, venue TEXT, year INTEGER, doi TEXT,
    authors_json TEXT, abstract TEXT, source TEXT NOT NULL, imported_at TEXT NOT NULL)"""
INS = """INSERT OR REPLACE INTO paper_bibliographic
         (paper_id,title,venue,year,doi,authors_json,abstract,source,imported_at)
         VALUES (?,?,?,?,?,?,?,?,?)"""
def payload(pid, r):
    return (pid, r.get("title"), r.get("venue"), r.get("year"), r.get("doi"),
            json.dumps(r.get("authors") or []), (r.get("abstract") or "")[:4000] or None,
            r["source"], NOW)

# AE lifecycle via db_locator
sys.path.insert(0, AE)
from src.services.db_locator import get_lifecycle_db_connection  # noqa: E402
con = get_lifecycle_db_connection()
con.execute("PRAGMA busy_timeout=15000")
con.execute(DDL)
first = sorted(rows)[0]
con.execute(INS, payload(first, rows[first])); con.commit()
back = con.execute("SELECT paper_id,title,year,source FROM paper_bibliographic WHERE paper_id=?",(first,)).fetchone()
print("AE one-example:", tuple(back)); assert back and back[1]
con.executemany(INS, [payload(p, r) for p, r in rows.items()]); con.commit()
n = con.execute("SELECT COUNT(*), SUM(year IS NOT NULL), SUM(abstract IS NOT NULL) FROM paper_bibliographic").fetchone()
print(f"AE paper_bibliographic: rows={n[0]} with_year={n[1]} with_abstract={n[2]}")
con.close()

# AF
af = sqlite3.connect(str(AF / "data/article_finder.db"))
af.execute("PRAGMA busy_timeout=15000")
af.execute(DDL)
af.execute(INS, payload(first, rows[first])); af.commit()
back = af.execute("SELECT paper_id,title,year FROM paper_bibliographic WHERE paper_id=?",(first,)).fetchone()
print("AF one-example:", tuple(back)); assert back and back[1]
af.executemany(INS, [payload(p, r) for p, r in rows.items()]); af.commit()
n = af.execute("SELECT COUNT(*) FROM paper_bibliographic").fetchone()[0]
print(f"AF paper_bibliographic: rows={n}")
af.close()
print("BIB_TABLES_OK")
