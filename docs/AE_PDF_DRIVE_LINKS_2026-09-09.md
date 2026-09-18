# AE PDF drive links — where they live and why this file exists

2026-09-09, recorded by Fable at David's direction.

The corpus databases do not travel by git: `.gitignore` line 15 excludes all of
`data/`, so `data/article_finder.db` never syncs. This tracked file is the pointer
that does.

## Per-paper links in the database

`data/article_finder.db` now holds the table **`ae_pdf_drive_links`** — one row per
Article Eater paper (1,760 rows; 1,758 with a working browser URL):

    ae_paper_id  (PDF-XXXX, primary key)
    af_paper_id  (this DB's own paper key; filled for 708 rows — the AE-matched
                  papers whose AE id appears in the current drive release)
    drive_file_id, drive_url          (https://drive.google.com/file/d/<id>/view)
    object_sha256, drive_object_path, availability, size_bytes
    release_id, imported_at

Rows were imported from the lifecycle DB's `pdf_drive_mirror` table in
`/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery/data/article_eater_lifecycle.db`,
which was itself built from the drive release's own catalogue. Both tables are
additive; drop them to undo.

## The corpus itself

Google Drive folder **`AE_Canonical_PDF_Corpus`** (root folder id
`18YkSfZHOdDnwvoEmtWSwxvmf0-UtCKTp`) — a versioned release
(`current_release/CURRENT.json` + `manifest.json`, schema `ae_pdf_corpus_current.v1`).
The links above point at release **2026-09-08-r1**. When a new release is cut, both
link tables need a re-import (codex-ae has been asked, via the AE taskboard, to fold
this into the release-cut step).

Whole-corpus fetch for a machine with rclone configured:

    rclone copy "gdrive:AE_Canonical_PDF_Corpus/current_release" <dest>

## Database snapshots on Drive

The git-excluded databases themselves (this repo's `article_finder.db` and the five
AE truth-surface DBs) have dated, checksummed snapshots at
`gdrive:ATLAS_DB_Snapshots/<YYYY-MM-DD>/` (first: 2026-09-09; `LATEST.txt` at the
folder root names the newest). Each folder carries a `manifest.json` with per-file
sha256. These are read-only reference copies made with `sqlite3 .backup`; the
single-writer homes stay on David's Mac — never write to a downloaded copy.

    rclone copy "gdrive:ATLAS_DB_Snapshots/2026-09-09" <dest>

Fuller documentation: `data/DB_REGISTRY.md` §PDF Corpus and §Off-machine DB
snapshots, and `docs/coordination/CANONICAL_ARTIFACT_LOCATION_REGISTRY_2026-06-14.md`
(PDF binaries row), all in the AE recovery repo.
