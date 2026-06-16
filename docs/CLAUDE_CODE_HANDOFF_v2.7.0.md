# Claude Code Handoff: Article Finder v2.7.0 — Unified PDF Acquisition Service

**Author:** David Kirsh, Cognitive Science, UC San Diego
**Date:** April 25, 2026
**Target version:** Article Finder v2.7.0
**Estimated effort:** 6 days for one engineer, paced as below
**Streamlit port:** 8502 (existing convention)

---

## 0. How to use this document

Paste this entire file into a Claude Code terminal session at the root of your Article Finder repo. Claude Code should read it top to bottom before writing any code. Sections 1–3 are context; sections 4–14 are specifications; section 15 is the build sequence; section 16 is the acceptance criteria.

**Build in stages.** Do not attempt the whole thing in one shot. After completing each numbered Day in section 15, stop, run the tests for that day, present the results, and wait for human review before proceeding. The cost of building the foundation wrong is high, and the value of human review at each stage is correspondingly high.

**Increment the version number on every code change** (2.7.0 → 2.7.1 → 2.7.2 ...). David maintains version-number-stamped zip files as his change trace. Every commit message should include the version.

**Never ask David for a credential value in the chat.** Credentials are entered via the setup CLI which uses `getpass.getpass()` to suppress terminal echo. If you find yourself about to ask "please paste your API key," stop and instead provide instructions for running the setup CLI.

---

## 1. Project context

Article Finder is a neuroarchitecture literature management tool used by Prof. David Kirsh's research group at UCSD Cognitive Science. It supports search, acquisition, classification, and downstream extraction of academic papers spanning lighting, acoustics, biophilic design, thermal comfort, spatial cognition, air quality, color psychology, privacy, and research methods.

The current state (v2.6.2) has three disjoint PDF acquisition scripts that do related but non-overlapping work:

- `scripts/acquire_pdfs_unpaywall.py` — single-source (Unpaywall only), `urllib`-based, reads work list from JSON file
- `scripts/acquire_foundational_papers.py` — five-source cascade (OpenAlex Content → Unpaywall → CORE → PMC → OpenAlex OA fallback), `requests`-based, hand-curated paper list of 53 theoretical foundations
- `scripts/run_acquisition_pipeline.py` — orchestrator that chains queue refresh, S2 search, query expansion, snowball expansion, enrichment, Zotero push, digest generation; does NOT call either of the other two scripts

**Read all three scripts before writing any new code.** They contain useful patterns (DOI normalization, magic-bytes validation, the cascade pattern) that should be lifted rather than reinvented. They also contain bugs that need fixing during the migration (see section 14).

The goal of v2.7.0 is to replace these three scripts with a single, unified, well-tested, observable, securely-credentialed PDF acquisition service that:

1. Accepts six input modes (DOI, citation string, title, abstract, plus list variants)
2. Tries up to 15 sources in cost-and-effort order, stopping at the first validated PDF
3. Surfaces human-actionable URLs from every tier, even on download failure
4. Validates PDFs at three levels (bytes, text, content match)
5. Classifies retrieved papers by topic and article type
6. Persists everything to a unified `pdf_lifecycle.db` SQLite database
7. Presents results through a five-page Streamlit interface
8. Supports modular addition of new APIs via a YAML registry plus a single Python class
9. Stores all credentials in the OS keyring (or encrypted vault, never plain `.env` in production)

---

## 2. Critical principles, in priority order

These supersede every other instruction in this document if they conflict.

**Security first.** No credentials in code, in logs, in chat, in commits, in URLs persisted to the database, or in Streamlit UI output. Setup CLI uses `getpass.getpass()`. Logs pass through `CredentialRedactingFormatter`. URLs are stripped of `?api_key=...` before persistence.

**Observability second.** Every cascade attempt, success or failure, is logged to the `attempts` table. Every credential read writes to a separate audit log. Every source has its success rate visible in the Operations UI page. The cost of the always-log-everything pattern is a few KB per request; the value is the ability to answer "why isn't this working" without trawling stdout.

**Modularity third.** Adding a new API source is a two-file change: one YAML entry plus one Python class. No changes to cascade, persister, validator, or UI required. This is enforced by the `Source` abstract base class contract and the `sources_registry.yaml` schema.

**Validation everywhere.** Bytes-level (magic, size). Text-level (extractable, sufficient length). Content-level (DOI, title fragment, or first-author surname appears in the PDF text). A PDF that fails any of these three is discarded and the cascade continues. Silent corpus pollution from accepting non-matching PDFs is a known failure mode in retrieval pipelines and must be prevented.

**Graceful degradation.** Sources with missing credentials are skipped with a warning, not an error. Sources past their declared `expires_at` raise a startup warning. Paid sources past their monthly quota fall through to their declared `degrades_to` tier. The system always produces *some* useful output, even when most sources are unavailable.

**Idempotence and resumability.** Re-running an acquisition request for a paper that already has a validated PDF returns the existing record without re-fetching. Interrupted multi-paper runs resume from the last completed request. The `requests` table is append-only; the `papers` and `files` tables deduplicate by canonical identifier.

---

## 3. APIs and citation systems available

These were extracted from the three uploaded scripts plus the architectural discussion. The `requires_credentials` column tells you which environment variables the source needs; missing credentials cause the source to be auto-disabled with a warning.

| Tier | Source | Type | Cost | Required credentials | Notes |
|------|--------|------|------|--------------------|-------|
| 0 | Local Zotero SQLite | Free | None | `ZOTERO_PATH` (default `~/Zotero`) | Read-only; check before any network call |
| 1 | Internal database | Free | None | None | Already-acquired papers via fuzzy DOI/title match |
| 2 | Unpaywall | Free | Email | `UNPAYWALL_EMAIL` | 100K/day; polite-pool email header required |
| 3 | Semantic Scholar | Free | Optional key | `SEMANTIC_SCHOLAR_API_KEY` | Key already in old code (line 52) but unused; use it |
| 4 | OpenAlex (oa_url) | Free | Email | `CROSSREF_MAILTO` | Use `mailto` parameter for polite pool |
| 5a | CrossRef TDM | Free | Token | `CROSSREF_PLUS_TOKEN` (optional) | Text-and-data-mining links via UCSD agreement |
| 5b | CrossRef publisher links | Free | Email | `CROSSREF_MAILTO` | ALWAYS records publisher landing as human URL |
| 6 | CORE | Free | API key | `CORE_API_KEY` | **OLD KEY EXPIRED 2026-04-02. Get new key at core.ac.uk before implementing** |
| 7 | PubMed Central | Free | API key | `NCBI_API_KEY` | Fix URL bug from foundational script line 332 |
| 8 | arXiv | Free | None | None | Atom XML response; search by ID or title |
| 9 | bioRxiv / medRxiv | Free | None | None | `api.biorxiv.org/details/biorxiv/{doi}` |
| 10 | OSF Preprints | Free | None | None | `api.osf.io/v2/preprints/?filter[doi]={doi}` |
| 11 | OpenAlex Content | Paid (~$0.01/PDF) | API key | `OPENALEX_API_KEY` | Gated behind `enable_paid_sources` config flag |
| 12 | SerpAPI Google Scholar | Paid (~$75/mo) | API key | `SERPAPI_KEY` | Implements `no_pdf_but_url` outcome — cluster URL is valuable even when no direct PDF |
| 13 | AI agent (Claude) | Paid (per call) | API key | `ANTHROPIC_API_KEY` | Most failure-prone; strict validation gate |
| 14 | Internet Archive | Free | None | None | Books only; respect controlled-digital-lending limits |
| 15 | Manual targets aggregator | Free | None | None | Always runs; consolidates all human-actionable URLs from upstream tiers |

---

## 4. Repository layout (target)

```
article_finder/                     # repo root
├── VERSION                         # bump on every change (2.7.0 → 2.7.1 → ...)
├── README.md                       # quick-start; rewrite for v2.7.0
├── pyproject.toml                  # add new deps: requests, keyring, pyyaml,
│                                   #   python-dotenv, pydantic, streamlit,
│                                   #   habanero, scholarly (optional),
│                                   #   anthropic, pypdf, sqlite-utils
├── config/
│   ├── sources_registry.yaml       # NEW: declarative source registration
│   ├── credentials.py              # NEW: 3-tier credential loader
│   ├── redaction.py                # NEW: log redaction
│   ├── settings.yaml               # existing config; merge into here
│   ├── taxonomy.yaml               # existing 9-facet taxonomy
│   └── .env.example                # NEW: documents var names, no values
├── src/
│   └── acquisition/                # NEW: the entire unified service lives here
│       ├── __init__.py
│       ├── service.py              # AcquisitionService (entry point)
│       ├── resolver.py             # input → CanonicalIdentifiers
│       ├── cascade.py              # MultiSourceCascade runner
│       ├── validator.py            # 3-stage PDF validation
│       ├── classifier.py           # topic + article_type
│       ├── persister.py            # writes to pdf_lifecycle.db
│       ├── library_proxy.py        # UCSD proxy URL generation
│       ├── manual_targets.py       # Tier 15 finalizer
│       ├── audit.py                # credential access audit log
│       └── sources/
│           ├── __init__.py
│           ├── base.py             # Source ABC + SourceResult
│           ├── registry.py         # loads sources_registry.yaml
│           ├── zotero_local.py
│           ├── internal_db.py
│           ├── unpaywall.py
│           ├── semantic_scholar.py
│           ├── openalex.py         # Tiers 4 AND 11
│           ├── crossref.py         # Tiers 5a AND 5b
│           ├── core_api.py
│           ├── pmc.py
│           ├── arxiv.py
│           ├── biorxiv.py
│           ├── osf.py
│           ├── serpapi_scholar.py
│           ├── ai_agent.py
│           └── internet_archive.py
├── db/
│   ├── schema.sql                  # full pdf_lifecycle.db schema
│   └── migrations/                 # future schema changes
├── ui/
│   ├── main.py                     # Streamlit entry; runs on :8502
│   └── pages/
│       ├── 1_Submit.py
│       ├── 2_Current_Session.py
│       ├── 3_History.py
│       ├── 4_Manual_Queue.py
│       └── 5_Operations.py
├── cli/
│   └── __main__.py                 # `python -m article_finder ...`
│                                   # commands: setup, verify, list, run
├── tests/
│   ├── unit/                       # mocked HTTP per source
│   ├── integration/                # live API; run on demand
│   ├── e2e/                        # Streamlit + db end-to-end
│   └── fixtures/                   # canned API responses
├── scripts/                        # OLD scripts kept but deprecated
│   ├── acquire_pdfs_unpaywall.py   # add deprecation header; route to service
│   ├── acquire_foundational_papers.py  # same
│   └── run_acquisition_pipeline.py # same
└── data/
    ├── pdfs/                       # existing; do NOT delete
    └── pdf_lifecycle.db            # NEW; created by schema.sql
```

---

## 5. The credential architecture (build this FIRST, on Day 1)

Three layers. No code that needs credentials runs before this is in place.

### 5.1 Schema layer: `config/sources_registry.yaml`

Committed to git. Contains no secret values. Declares every source.

```yaml
# config/sources_registry.yaml
# Adding a new source: add an entry here + write one Python class.
# No core code changes required.

version: 1
defaults:
  timeout_seconds: 15
  rate_limit_per_second: 1.0
  enabled: true

sources:
  - name: zotero_local
    tier: 0
    module: src.acquisition.sources.zotero_local
    class: ZoteroLocalSource
    required_credentials:
      - name: ZOTERO_PATH
        description: "Path to Zotero data dir"
        sensitive: false
        default: "~/Zotero"

  - name: unpaywall
    tier: 2
    module: src.acquisition.sources.unpaywall
    class: UnpaywallSource
    endpoint: https://api.unpaywall.org/v2
    required_credentials:
      - name: UNPAYWALL_EMAIL
        description: "Email for polite-pool header"
        sensitive: false
    rate_limit_per_second: 0.9   # Unpaywall asks ≤1/sec

  - name: semantic_scholar
    tier: 3
    module: src.acquisition.sources.semantic_scholar
    class: SemanticScholarSource
    endpoint: https://api.semanticscholar.org/graph/v1
    required_credentials:
      - name: SEMANTIC_SCHOLAR_API_KEY
        description: "S2 API key (optional; raises rate limit)"
        sensitive: true
        rotation_url: https://www.semanticscholar.org/product/api
    rate_limit_per_second: 0.3   # 100/5min unauth; higher with key

  - name: core
    tier: 6
    module: src.acquisition.sources.core_api
    class: CoreSource
    endpoint: https://api.core.ac.uk/v3
    required_credentials:
      - name: CORE_API_KEY
        description: "CORE Bearer token"
        sensitive: true
        rotation_url: https://core.ac.uk/services/api
        expires_at: "2027-04-02"   # set when key created/rotated
    rate_limit_per_second: 8.0

  - name: serpapi_scholar
    tier: 12
    module: src.acquisition.sources.serpapi_scholar
    class: SerpApiScholarSource
    endpoint: https://serpapi.com/search.json
    required_credentials:
      - name: SERPAPI_KEY
        description: "SerpAPI key (paid)"
        sensitive: true
        rotation_url: https://serpapi.com/manage-api-key
        cost_warning: "Paid; check quota before bulk runs"
    rate_limit_per_second: 1.0
    monthly_quota: 5000
    cost_per_call_usd: 0.015
    degrades_to: ai_agent

  # ... entries for all 14 active sources
```

### 5.2 Vault layer: three options, ordered by security

```python
# config/credentials.py

import os
import warnings
import keyring
import keyring.errors
from pathlib import Path
from typing import Optional

KEYRING_SERVICE = "article_finder"

def store_credential(name: str, value: str) -> None:
    """Store via OS keyring. Called by setup CLI only."""
    keyring.set_password(KEYRING_SERVICE, name, value)
    _audit_log("store", name, success=True)

def get_credential(name: str) -> Optional[str]:
    """Three-tier lookup: keyring → encrypted vault → plain .env (dev only)."""
    # Tier 1: OS keyring (encrypted by OS, user-scoped)
    try:
        v = keyring.get_password(KEYRING_SERVICE, name)
        if v:
            _audit_log("read", name, source="keyring", success=True)
            return v
    except keyring.errors.KeyringError as e:
        _audit_log("read", name, source="keyring", success=False, error=str(e))

    # Tier 2: encrypted vault file (age or sops)
    v = _read_encrypted_vault(name)
    if v:
        _audit_log("read", name, source="vault_file", success=True)
        return v

    # Tier 3: plain .env (development only, with warning)
    v = os.getenv(name)
    if v:
        if _is_production_like():
            warnings.warn(
                f"Credential {name} loaded from plaintext .env. "
                f"Move to OS keyring with: "
                f"python -m article_finder setup credential {name}"
            )
        _audit_log("read", name, source="env_plain", success=True)
        return v

    _audit_log("read", name, source=None, success=False, error="not_found")
    return None

def delete_credential(name: str) -> None:
    """Remove from keyring. Called by setup CLI."""
    try:
        keyring.delete_password(KEYRING_SERVICE, name)
        _audit_log("delete", name, success=True)
    except keyring.errors.PasswordDeleteError:
        pass

def _is_production_like() -> bool:
    """Detect if we should warn about plaintext credentials."""
    return os.getenv("ARTICLE_FINDER_ENV", "dev").lower() != "dev"

def _read_encrypted_vault(name: str) -> Optional[str]:
    """Read from age-encrypted vault file if present.
    Returns None if no vault, no key, or name not in vault."""
    vault_path = Path("config/.env.vault")
    if not vault_path.exists():
        return None
    # Implementation: shell out to `age -d` with key from
    # ~/.config/article_finder/age.key. If anything fails, return None.
    # Detailed implementation follows the `age` CLI conventions.
    ...
```

### 5.3 Setup CLI: `cli/__main__.py`

```python
# Usage:
#   python -m article_finder setup credentials       # interactive wizard
#   python -m article_finder setup credential NAME   # single credential
#   python -m article_finder verify credentials      # test all
#   python -m article_finder list sources            # show enabled/disabled
#   python -m article_finder run [args]              # run acquisition

import getpass
import sys
import yaml
from config.credentials import store_credential, get_credential
from src.acquisition.sources.registry import load_registry

def cmd_setup_credentials():
    """Interactive wizard. Walks through every source's credentials."""
    registry = load_registry()
    print("\nArticle Finder Credential Setup")
    print("=" * 40)
    print("Credentials stored in OS keyring; never written to disk in plaintext.\n")

    for i, src in enumerate(registry.sources, 1):
        print(f"[{i}/{len(registry.sources)}] {src.name} (tier {src.tier})")
        for cred in src.required_credentials:
            existing = get_credential(cred.name)
            status = "✓ already configured" if existing else "(not set)"
            print(f"  {cred.name}: {status}")
            print(f"    {cred.description}")
            if cred.cost_warning:
                print(f"    ⚠️  {cred.cost_warning}")
            if cred.rotation_url:
                print(f"    Rotate at: {cred.rotation_url}")

            prompt = "    New value (Enter to skip): "
            if cred.sensitive:
                value = getpass.getpass(prompt)   # NO ECHO
            else:
                value = input(prompt)

            if value:
                store_credential(cred.name, value)
                print(f"    ✓ Stored in keychain.")
        print()

    print("Setup complete. Run `python -m article_finder verify credentials`.")

def cmd_verify_credentials():
    """Non-interactive: test each configured credential against its API."""
    # For each source, attempt a lightweight test call (HEAD request,
    # cheap query, etc.). Report status without ever printing the key.
    ...
```

### 5.4 Redaction: `config/redaction.py`

```python
import re
import logging

CREDENTIAL_PATTERNS = [
    re.compile(r'(?i)(api[_-]?key|token|secret|password)["\']?\s*[:=]\s*["\']?([^\s"\',}]+)'),
    re.compile(r'(?i)Bearer\s+[A-Za-z0-9_\-\.]+'),
    re.compile(r'\?api_key=[^&\s]+'),
    re.compile(r'&api_key=[^&\s]+'),
    re.compile(r'\?key=[^&\s]+'),
]

class CredentialRedactingFormatter(logging.Formatter):
    def format(self, record):
        msg = super().format(record)
        for pat in CREDENTIAL_PATTERNS:
            msg = pat.sub(r'\1=***REDACTED***', msg)
        return msg

def install_redaction():
    """Apply the redacting formatter to ALL handlers on the root logger."""
    fmt = CredentialRedactingFormatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    root = logging.getLogger()
    for handler in root.handlers:
        handler.setFormatter(fmt)

def strip_credentials_from_url(url: str) -> str:
    """Remove ?api_key=... and similar before persisting URLs."""
    for pat in [r'\?api_key=[^&]*', r'&api_key=[^&]*',
                r'\?key=[^&]*', r'&key=[^&]*']:
        url = re.sub(pat, '', url)
    return url
```

### 5.5 Audit log: `src/acquisition/audit.py`

```python
import json
import os
from datetime import datetime
from pathlib import Path

AUDIT_LOG = Path("config/credential_access.log")

def _audit_log(action: str, credential_name: str, **kwargs):
    """Append-only log of every credential access. NEVER stores values."""
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "action": action,
        "credential_name": credential_name,    # name only, never value
        "caller_module": _detect_caller_module(),
        **kwargs,
    }
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    os.chmod(AUDIT_LOG, 0o600)
```

---

## 6. Database schema (`db/schema.sql`)

```sql
-- pdf_lifecycle.db schema for Article Finder v2.7.0
-- Six tables. SQLite. Foreign keys ON. Append-only requests/attempts.

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS sessions (
    session_id      TEXT PRIMARY KEY,
    submitted_by    TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    note            TEXT
);

CREATE TABLE IF NOT EXISTS requests (
    request_id          TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL REFERENCES sessions(session_id),
    submitted_by        TEXT NOT NULL,
    submitted_at        TEXT NOT NULL,
    input_mode          TEXT NOT NULL CHECK(input_mode IN
        ('doi','citation','title','abstract',
         'doi_list','citation_list','title_list','abstract_list')),
    raw_input           TEXT NOT NULL,
    parsed_canonical    TEXT,                  -- JSON CanonicalIdentifiers
    paper_id            TEXT REFERENCES papers(paper_id),
    status              TEXT NOT NULL CHECK(status IN
        ('pending','resolving','acquiring','classifying','complete','failed')),
    failure_reason      TEXT,
    completed_at        TEXT
);

CREATE INDEX idx_requests_session ON requests(session_id);
CREATE INDEX idx_requests_user    ON requests(submitted_by);
CREATE INDEX idx_requests_status  ON requests(status);

CREATE TABLE IF NOT EXISTS papers (
    paper_id                TEXT PRIMARY KEY,  -- canonical DOI when avail
    doi                     TEXT UNIQUE,
    openalex_id             TEXT,
    s2_paper_id             TEXT,
    pmid                    TEXT,
    pmcid                   TEXT,
    arxiv_id                TEXT,
    title                   TEXT NOT NULL,
    authors_json            TEXT,
    year                    INTEGER,
    venue                   TEXT,
    abstract                TEXT,
    resolution_method       TEXT,
    resolution_confidence   REAL,
    first_seen_at           TEXT NOT NULL,
    last_updated_at         TEXT NOT NULL
);

CREATE INDEX idx_papers_doi   ON papers(doi);
CREATE INDEX idx_papers_title ON papers(title);

CREATE TABLE IF NOT EXISTS attempts (
    attempt_id              TEXT PRIMARY KEY,
    request_id              TEXT NOT NULL REFERENCES requests(request_id),
    paper_id                TEXT REFERENCES papers(paper_id),
    source                  TEXT NOT NULL,
    tier                    REAL NOT NULL,
    attempted_at            TEXT NOT NULL,
    http_status             INTEGER,
    bytes_received          INTEGER,
    validation_result       TEXT CHECK(validation_result IN
        ('pdf_ok','too_small','not_pdf','text_too_sparse',
         'content_mismatch','extraction_failed',
         'paywall_html','login_redirect','timeout','error',NULL)),
    error_message           TEXT,
    duration_ms             INTEGER,
    human_actionable_url    TEXT,              -- credentials stripped
    human_action_type       TEXT
);

CREATE INDEX idx_attempts_request ON attempts(request_id);
CREATE INDEX idx_attempts_source  ON attempts(source);
CREATE INDEX idx_attempts_paper   ON attempts(paper_id);

CREATE TABLE IF NOT EXISTS files (
    file_id                 TEXT PRIMARY KEY,
    paper_id                TEXT NOT NULL REFERENCES papers(paper_id),
    file_path               TEXT NOT NULL UNIQUE,
    sha256                  TEXT NOT NULL UNIQUE,
    size_bytes              INTEGER NOT NULL,
    page_count              INTEGER,
    text_extractable        INTEGER NOT NULL,  -- 0/1
    word_count              INTEGER,
    acquired_from_source    TEXT NOT NULL,
    acquired_at             TEXT NOT NULL
);

CREATE INDEX idx_files_paper ON files(paper_id);

CREATE TABLE IF NOT EXISTS classifications (
    classification_id       TEXT PRIMARY KEY,
    paper_id                TEXT NOT NULL REFERENCES papers(paper_id),
    topic_ids_json          TEXT NOT NULL,
    topic_scores_json       TEXT NOT NULL,
    article_type            TEXT NOT NULL CHECK(article_type IN
        ('rct','field_experiment','observational','review','meta_analysis',
         'theoretical','simulation','qualitative','case_study',
         'methodological','other')),
    article_type_confidence REAL NOT NULL,
    classified_at           TEXT NOT NULL,
    classifier_method       TEXT NOT NULL CHECK(classifier_method IN
        ('centroid','embedding','llm','publisher_metadata'))
);

CREATE INDEX idx_classifications_paper ON classifications(paper_id);

CREATE TABLE IF NOT EXISTS manual_acquisition_targets (
    target_id               TEXT PRIMARY KEY,
    paper_id                TEXT NOT NULL REFERENCES papers(paper_id),
    request_id              TEXT NOT NULL REFERENCES requests(request_id),
    primary_url             TEXT NOT NULL,
    primary_action_type     TEXT NOT NULL,
    fallback_urls_json      TEXT,
    library_proxy_url       TEXT,
    cost_to_acquire         TEXT CHECK(cost_to_acquire IN
        ('free','subscription','paywalled','unknown')),
    estimated_minutes       INTEGER,
    priority                REAL,
    created_at              TEXT NOT NULL,
    resolved_at             TEXT,
    resolved_via            TEXT
);

CREATE INDEX idx_manual_paper    ON manual_acquisition_targets(paper_id);
CREATE INDEX idx_manual_resolved ON manual_acquisition_targets(resolved_at);
```

---

## 7. The Source ABC contract (`src/acquisition/sources/base.py`)

This is the contract every source must satisfy. The ABC enforces it; the cascade depends on it.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from enum import Enum

class SourceOutcome(Enum):
    FOUND               = "found"               # PDF retrieved AND validated
    FOUND_URL_ONLY      = "found_url_only"      # got URL but DL/validate failed
    NO_MATCH            = "no_match"            # source has no record
    NO_PDF              = "no_pdf"              # has paper, no PDF
    URL_ONLY_HUMAN      = "url_only_human"      # human-actionable URL only
    RATE_LIMITED        = "rate_limited"
    AUTH_ERROR          = "auth_error"
    TIMEOUT             = "timeout"
    ERROR               = "error"

@dataclass
class SourceResult:
    outcome: SourceOutcome
    pdf_url: Optional[str] = None
    pdf_bytes: Optional[bytes] = None
    human_actionable_url: Optional[str] = None
    human_action_type: Optional[str] = None
    fallback_urls: List[Tuple[str, str]] = field(default_factory=list)
    error_message: Optional[str] = None
    duration_ms: int = 0
    raw_response: Optional[dict] = None       # debugging only; not persisted

    @classmethod
    def found(cls, pdf_url, pdf_bytes=None, **kw):
        return cls(SourceOutcome.FOUND, pdf_url=pdf_url, pdf_bytes=pdf_bytes, **kw)

    @classmethod
    def url_only_human(cls, human_url, action_type, **kw):
        return cls(SourceOutcome.URL_ONLY_HUMAN,
                   human_actionable_url=human_url,
                   human_action_type=action_type, **kw)

    @classmethod
    def no_match(cls, **kw):
        return cls(SourceOutcome.NO_MATCH, **kw)

    @classmethod
    def auth_error(cls, msg, **kw):
        return cls(SourceOutcome.AUTH_ERROR, error_message=msg, **kw)

    # ... etc for each outcome

@dataclass
class CanonicalIdentifiers:
    doi: Optional[str] = None
    openalex_id: Optional[str] = None
    s2_paper_id: Optional[str] = None
    pmid: Optional[str] = None
    pmcid: Optional[str] = None
    arxiv_id: Optional[str] = None
    title: str = ""
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    resolution_method: str = ""
    resolution_confidence: float = 0.0

class Source(ABC):
    """Abstract base. Every source in sources_registry.yaml subclasses this."""
    name: str                                  # set by subclass
    tier: float                                # set by subclass
    requires_credentials: List[str] = []
    rate_limit_per_second: float = 1.0
    timeout_seconds: int = 15

    def __init__(self, config: dict):
        self.config = config
        self._last_call_at: float = 0.0

    def is_available(self) -> bool:
        """Returns True iff all required credentials are present."""
        from config.credentials import get_credential
        return all(get_credential(c) for c in self.requires_credentials)

    @abstractmethod
    def find_pdf(self, ids: CanonicalIdentifiers) -> SourceResult:
        """
        Look up a paper. ALWAYS returns a SourceResult — never raises.
        Catches all exceptions internally and returns SourceResult(ERROR, ...).
        Honors rate_limit_per_second via _wait_for_rate_limit().
        """

    def _wait_for_rate_limit(self):
        import time
        elapsed = time.monotonic() - self._last_call_at
        min_interval = 1.0 / self.rate_limit_per_second
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_call_at = time.monotonic()
```

---

## 8. The cascade (`src/acquisition/cascade.py`)

```python
import time
from typing import List, Optional
from src.acquisition.sources.base import Source, SourceOutcome, CanonicalIdentifiers
from src.acquisition.validator import Validator
from src.acquisition.manual_targets import ManualTargetsAggregator
from src.acquisition.library_proxy import ucsd_library_proxy_url

class MultiSourceCascade:
    """
    Iterates Source list in tier order. Stops at first FOUND (after validation).
    ALWAYS logs every attempt. ALWAYS runs Tier 15 finalizer.
    """

    def __init__(self, sources: List[Source], validator: Validator):
        self.sources = sorted(
            [s for s in sources if s.is_available()],
            key=lambda s: s.tier
        )
        self.validator = validator
        self.aggregator = ManualTargetsAggregator()

    def run(self, ids: CanonicalIdentifiers, request_id: str) -> "CascadeResult":
        attempts = []
        collected_human_urls: List[Tuple[str, str]] = []
        successful_file = None

        for source in self.sources:
            t0 = time.monotonic()
            try:
                result = source.find_pdf(ids)
            except Exception as e:
                # Belt-and-suspenders: contract says no raises, but if a source
                # violates it, log and continue rather than crash the cascade.
                result = SourceResult.error(f"unhandled: {e}")
            duration_ms = int((time.monotonic() - t0) * 1000)
            result.duration_ms = duration_ms

            attempt = self._build_attempt(source, result, request_id, ids)
            attempts.append(attempt)

            # Collect human-actionable URLs from EVERY tier
            if result.human_actionable_url:
                collected_human_urls.append(
                    (result.human_actionable_url, result.human_action_type)
                )
            collected_human_urls.extend(result.fallback_urls)

            # Stop at first validated PDF
            if result.outcome == SourceOutcome.FOUND:
                pdf_bytes = result.pdf_bytes or self._fetch(result.pdf_url)
                if pdf_bytes is None:
                    attempt.validation_result = "timeout"
                    continue
                validation = self.validator.validate(pdf_bytes, ids)
                if validation.ok:
                    successful_file = self._persist_file(
                        pdf_bytes, ids, source.name
                    )
                    attempt.validation_result = "pdf_ok"
                    break
                else:
                    attempt.validation_result = validation.reason
                    # Validation failed: surface the URL as human-actionable
                    collected_human_urls.append(
                        (result.pdf_url, "validation_failed")
                    )

        # Tier 15: always-run finalizer
        manual_target = self.aggregator.build(
            ids=ids,
            request_id=request_id,
            collected_urls=collected_human_urls,
            library_proxy_url=ucsd_library_proxy_url(ids.doi) if ids.doi else None,
        )

        return CascadeResult(
            attempts=attempts,
            file=successful_file,
            manual_target=manual_target,
        )
```

---

## 9. The validator (`src/acquisition/validator.py`)

```python
from dataclasses import dataclass
from typing import Optional
import io

@dataclass
class ValidationResult:
    ok: bool
    reason: str

    @classmethod
    def fail(cls, reason): return cls(False, reason)
    @classmethod
    def ok_(cls, reason="ok"): return cls(True, reason)

class Validator:
    """Three-stage. Reject early."""
    MIN_PDF_BYTES = 50_000
    MIN_TEXT_WORDS = 200
    MIN_TITLE_TOKEN_LEN = 4
    MAX_TITLE_TOKENS_TO_CHECK = 5

    def validate(self, pdf_bytes: bytes, ids: CanonicalIdentifiers) -> ValidationResult:
        # Stage 1: bytes-level
        if len(pdf_bytes) < self.MIN_PDF_BYTES:
            return ValidationResult.fail("too_small")
        if not pdf_bytes.startswith(b"%PDF-"):
            return ValidationResult.fail("not_pdf")

        # Stage 2: extractable text
        try:
            text = self._extract_first_pages(pdf_bytes, n=3)
        except Exception as e:
            return ValidationResult.fail(f"extraction_failed:{type(e).__name__}")
        if len(text.split()) < self.MIN_TEXT_WORDS:
            return ValidationResult.fail("text_too_sparse")

        # Stage 3: content matches request
        text_lower = text.lower()
        if ids.doi and ids.doi.lower() in text_lower:
            return ValidationResult.ok_("doi_match")
        if ids.title:
            tokens = [t for t in ids.title.lower().split()
                      if len(t) > self.MIN_TITLE_TOKEN_LEN]
            tokens = tokens[:self.MAX_TITLE_TOKENS_TO_CHECK]
            if tokens and all(t in text_lower for t in tokens):
                return ValidationResult.ok_("title_match")
        if ids.authors:
            first_surname = ids.authors[0].split()[-1].lower()
            if first_surname and first_surname in text_lower:
                return ValidationResult.ok_("author_match")
        return ValidationResult.fail("content_mismatch")

    def _extract_first_pages(self, pdf_bytes: bytes, n: int) -> str:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = reader.pages[:n]
        return "\n".join(p.extract_text() or "" for p in pages)
```

---

## 10. The resolver (`src/acquisition/resolver.py`)

Six input modes. Each returns CanonicalIdentifiers with confidence. Confidence < 0.85 triggers human-review flag rather than auto-commit.

```python
class Resolver:
    HUMAN_REVIEW_THRESHOLD = 0.85

    def resolve(self, raw_input: str, mode: str) -> CanonicalIdentifiers:
        method = {
            "doi":             self._resolve_doi,
            "citation":        self._resolve_citation,
            "title":           self._resolve_title,
            "abstract":        self._resolve_abstract,
        }[mode]
        return method(raw_input)

    def _resolve_doi(self, raw: str) -> CanonicalIdentifiers:
        # Normalize: strip https://doi.org/, doi:, whitespace.
        # Lift filesystem-encoded form (underscores) from
        # acquire_pdfs_unpaywall.py:72-86. Validate against CrossRef.
        ...

    def _resolve_citation(self, raw: str) -> CanonicalIdentifiers:
        # CrossRef /works?query.bibliographic=...
        # Use habanero. Top-1 match score = confidence.
        ...

    def _resolve_title(self, raw: str) -> CanonicalIdentifiers:
        # CrossRef /works?query.title=...
        # Cross-validate with author tokens if extractable.
        ...

    def _resolve_abstract(self, raw: str) -> CanonicalIdentifiers:
        # Semantic Scholar /paper/search/match
        # Embedding similarity = confidence.
        ...
```

For list inputs (`doi_list`, etc.), the service iterates and submits each as a separate request.

---

## 11. Topic and article-type classification (`src/acquisition/classifier.py`)

Two outputs per paper: topic IDs (multi-label, from existing 9-facet taxonomy in `config/taxonomy.yaml`) and article type (single-label from the enumeration in the schema).

Use the existing TF-IDF centroid classifier from v2.6.x as the default `classifier_method='centroid'`. Add an optional LLM-based classifier (`classifier_method='llm'`) gated on `ANTHROPIC_API_KEY` for higher-confidence classification. Article type is derived from a combination of S2 `publicationTypes`, MeSH (when from PMC), and abstract-level pattern matching.

If confidence < 0.6 on either dimension, write the classification anyway but flag it for human review in the UI.

---

## 12. The Streamlit UI

Five pages, all read-only against `pdf_lifecycle.db` except for Submit (writes requests) and Manual Queue (updates resolved_at).

### Page 1 — Submit
- Single textarea for raw input
- Radio for mode (DOI / Citation / Title / Abstract / Auto-detect)
- Process button
- Submitted requests appear immediately in Page 2

### Page 2 — Current Session
- Live-updating dataframe (refresh every 2s while requests in-flight)
- Columns: requested_as (truncated), resolved_title, resolved_doi,
  retrieved (Y/N + source on Y), file_path, manual_url (clickable link),
  topic, article_type, status (L0–L3 layer reached)
- Sortable, filterable, exportable to CSV

### Page 3 — History
- Same as Page 2 but joined across all sessions for current `submitted_by`
- Adds session column and started_at

### Page 4 — Manual Queue
- Only rows where automated acquisition failed (no row in `files`) but
  `manual_acquisition_targets` has a primary_url
- Sorted by priority (methodology-weighted, descending)
- Each row: paper title, all clickable links (library_proxy_url first,
  then primary_url, then fallback_urls), checkbox to mark resolved,
  file uploader to back-fill PDF after manual download

### Page 5 — Operations
- Per-source success rate over the last 7 / 30 / all days
- Failure-reason histogram per source
- Credential status table (configured / verified / expired / missing)
- Specifically warns when CORE key within 30 days of `expires_at`

---

## 13. CLI: `python -m article_finder ...`

```
Usage: python -m article_finder COMMAND [args]

Commands:
  setup credentials        Interactive wizard for all credentials
  setup credential NAME    Set/update a single credential
  verify credentials       Test all configured credentials against APIs
  list sources             Show enabled/disabled sources and reasons
  run --doi DOI            Acquire a single paper
  run --file PATH          Acquire from file (one per line)
  run --citation TEXT      Acquire from citation string
  ui                       Launch Streamlit UI on :8502
  migrate                  Run schema migrations + backfill from data/pdfs/
```

---

## 14. Bugs to fix while migrating

These are real bugs in the existing scripts. Fix during migration; do not propagate.

1. **`acquire_pdfs_unpaywall.py` lines 308–314:** when `pdf_url` is None but `is_oa` is True, the script stores the landing-page URL as `result.pdf_url`. In v2.7.0, this case must populate `human_actionable_url` instead, with `human_action_type='publisher_landing'`.

2. **`acquire_foundational_papers.py` line 332:** the PMC fallback URL `https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/` is a directory listing, not a PDF. Parse the OA service response (`oa.fcgi`) for the actual PDF URL. If only an HTML abstract page is available, return `URL_ONLY_HUMAN` with `human_action_type='pmc_abstract_only'`.

3. **`acquire_foundational_papers.py` lines 50–57:** all credentials hardcoded in plaintext. CORE key declared as expired 2026-04-02 (today is 2026-04-25, 23 days past). Migrate ALL of these to keychain via setup CLI before running anything live. Get a new CORE key at https://core.ac.uk/services/api before implementing Tier 6.

4. **`acquire_foundational_papers.py` line 52:** Semantic Scholar API key is defined but never used. Tier 3 implementation must use it.

5. **`acquire_foundational_papers.py` log strings around lines 384–451:** step labels read `[1/3]`, `[2/3]`, then `[3/5]`, `[4/5]`, `[5/5]`. Inconsistent. In v2.7.0 the cascade reports tier numbers from the registry rather than hand-counted strings.

6. **`acquire_foundational_papers.py` lines 369–371:** books with no DOI are abandoned. v2.7.0 routes book-typed entries to Tier 14 (Internet Archive) before giving up.

7. **`run_acquisition_pipeline.py` lines 47–53:** uses `subprocess.run(..., capture_output=True)` which buffers all output until completion. Long-running steps appear hung. Switch to `subprocess.Popen` with line-by-line streaming.

8. **`run_acquisition_pipeline.py`:** has no dependency model. If `search` fails, `expand` still runs against stale data. Add `requires` field per step; auto-skip downstream steps when prerequisites failed.

---

## 15. Build sequence — six days

**Stop at the end of each day, run the day's tests, present results, and wait for human review before proceeding.**

### Day 1 — Foundation (security + schema + base contracts)

Build:
- `config/credentials.py` (3-tier loader with keyring)
- `config/redaction.py` (log redaction + URL stripping)
- `config/sources_registry.yaml` (all source declarations, no values)
- `config/.env.example` (variable names only, comments explaining each)
- `src/acquisition/audit.py` (credential access log)
- `src/acquisition/sources/base.py` (Source ABC, SourceResult, CanonicalIdentifiers)
- `src/acquisition/sources/registry.py` (loads YAML, instantiates classes)
- `src/acquisition/library_proxy.py` (UCSD URL generator)
- `src/acquisition/validator.py` (3-stage validation)
- `db/schema.sql` (full 6-table schema)
- `src/acquisition/persister.py` (writes to all 6 tables, idempotent)
- `cli/__main__.py` (setup, verify, list commands; NO `run` yet)
- `tests/unit/test_credentials.py`
- `tests/unit/test_redaction.py`
- `tests/unit/test_validator.py`
- `tests/unit/test_persister.py`
- Bump VERSION to 2.7.0

**Day 1 acceptance:** `python -m article_finder setup credentials` walks through all credentials with `getpass`. `python -m article_finder verify credentials` produces a credential status table. `python -m article_finder list sources` shows sources tagged enabled/disabled per credential availability. All Day 1 unit tests pass. Schema applies cleanly; backfill from existing `data/pdfs/` works. **No source implementations yet.**

### Day 2 — Free sources (Tiers 0–7)

Build:
- `src/acquisition/sources/zotero_local.py`
- `src/acquisition/sources/internal_db.py`
- `src/acquisition/sources/unpaywall.py` (lift DOI normalizer from old script)
- `src/acquisition/sources/semantic_scholar.py` (use the unused key!)
- `src/acquisition/sources/openalex.py` (Tier 4 only this day; Tier 11 Day 3)
- `src/acquisition/sources/crossref.py` (5a + 5b)
- `src/acquisition/sources/core_api.py` (require new key)
- `src/acquisition/sources/pmc.py` (FIX line 332 bug)
- `tests/unit/test_*_source.py` for each (mocked HTTP, fixture per outcome)
- `tests/fixtures/` with canned API responses

**Day 2 acceptance:** every Tier 0–7 source has a mocked-HTTP unit test covering FOUND, NO_MATCH, AUTH_ERROR, RATE_LIMITED, ERROR, and (where applicable) URL_ONLY_HUMAN outcomes. All pass. No live API calls in unit tests.

### Day 3 — Remaining sources (Tiers 8–14)

Build:
- `src/acquisition/sources/arxiv.py`
- `src/acquisition/sources/biorxiv.py`
- `src/acquisition/sources/osf.py`
- `src/acquisition/sources/openalex.py` Tier 11 (Content API, paid, gated)
- `src/acquisition/sources/serpapi_scholar.py` (URL_ONLY_HUMAN outcome critical)
- `src/acquisition/sources/ai_agent.py` (Anthropic SDK; strict validation)
- `src/acquisition/sources/internet_archive.py` (books via title+author)
- `src/acquisition/manual_targets.py` (Tier 15 finalizer)
- Unit tests for each new source

**Day 3 acceptance:** all 14 sources implemented. All have unit tests. Tier 15 aggregator collects URLs from every preceding tier into one `ManualAcquisitionTarget` record with library-proxy URL always populated.

### Day 4 — Resolver, cascade, service

Build:
- `src/acquisition/resolver.py` (six input modes)
- `src/acquisition/cascade.py` (MultiSourceCascade)
- `src/acquisition/classifier.py` (TF-IDF centroid + optional LLM)
- `src/acquisition/service.py` (AcquisitionService.acquire(request))
- `cli/__main__.py` add `run` command
- `tests/integration/test_live_apis.py` with the six DOIs from §16

**Day 4 acceptance:** `python -m article_finder run --doi 10.7717/peerj.4375` retrieves and validates the PDF, classifies it, persists to db. Re-running returns the existing record without re-fetching. Live integration tests pass against the six known-good DOIs.

### Day 5 — Streamlit UI

Build:
- `ui/main.py`
- `ui/pages/1_Submit.py` through `ui/pages/5_Operations.py`
- Background worker so submit doesn't block UI thread
- `tests/e2e/test_streamlit.py` (submit → verify db row → verify file)

**Day 5 acceptance:** `streamlit run ui/main.py --server.port 8502` launches all five pages. Submit form processes a DOI, watches progress in Current Session, sees row appear in History after completion, sees Manual Queue populate when acquisition fails, sees Operations stats update. E2E tests pass.

### Day 6 — Migration, deprecation, polish

Build:
- Migration script: import existing `data/pdfs/` files into new db
- Deprecation headers on the three old scripts
- Old scripts route to new service internally so existing workflows still work
- `README.md` rewrite for v2.7.0
- Final test pass: unit + integration + e2e all green
- Create v2.7.0 zip

**Day 6 acceptance:** old scripts work but print deprecation notice. New service is the canonical path. Final zip ready for distribution.

---

## 16. Acceptance criteria (must hold at the end of every day)

1. **Security:** no credential value appears in: code, logs (after redaction), git history, db rows, UI output, audit log, or chat. Setup CLI uses `getpass`.

2. **Test coverage:** unit tests for every Source mock the HTTP layer and cover all SourceOutcome values that source can produce. Integration tests run against these six known-good DOIs:
   - `10.7717/peerj.4375` (Piwowar 2018, gold OA — must succeed at Unpaywall)
   - `10.1146/annurev.psych.59.103006.093639` (Barsalou 2008, hybrid — should hit Tier 2 or 3)
   - `10.1038/nrn2787` (Friston 2010, neuroscience — should hit Tier 2/3/7)
   - `10.1126/science.6143402` (Ulrich 1984 — should fail to manual queue with library_proxy_url populated)
   - arXiv:2403.07183 (Liang 2024 — must succeed at Tier 8)
   - `10.1101/2024.01.15.575234` (recent bioRxiv — must succeed at Tier 9)

3. **Idempotence:** running the same request twice does not create duplicate `papers` or `files` rows. Does create two `requests` rows (history is append-only).

4. **Observability:** every cascade run produces one `attempts` row per source tried, including the ones that succeeded. The Operations page shows per-source success rate.

5. **Modularity:** adding a new source requires editing exactly two files: `config/sources_registry.yaml` (one entry) and `src/acquisition/sources/<newname>.py` (one class). No changes to cascade, persister, validator, UI, or any existing source file. Verify by adding a stub `LensOrgSource` that returns NO_MATCH for everything; it must appear in `list sources` and be exercised by the cascade.

6. **Graceful degradation:** with no API keys configured at all, the system still works for Tier 0 (Zotero local) and Tier 1 (internal db) and produces useful manual_acquisition_targets entries with library-proxy URLs for everything else.

7. **Validation rigor:** a PDF that arrives via Unpaywall but is actually a paywall HTML page is rejected (Stage 1: not_pdf), the cascade continues, and the URL is recorded as human-actionable with `validation_failed` action type.

8. **Backward compatibility:** `python scripts/acquire_pdfs_unpaywall.py --check-only` still works (prints deprecation notice, routes to new service).

---

## 17. References for the design decisions in this document

- Christen, P. (2012). *Data matching: Concepts and techniques for record linkage, entity resolution, and duplicate detection*. Springer. — informs the deduplication-by-canonical-id pattern in the papers table.
- Hendricks, G., Tkaczyk, D., Lin, J., & Feeney, P. (2020). Crossref: The sustainable source of community-owned scholarly metadata. *Quantitative Science Studies*, 1(1), 414–427. — informs the CrossRef fuzzy resolution accuracy expectations.
- Higgins, J. P. T., et al. (Eds.). (2019). *Cochrane Handbook for Systematic Reviews of Interventions* (2nd ed.). Wiley. — informs the methodology-weighted priority scoring for the Manual Queue.
- Lampson, B. W. (2004). Computer security in the real world. *Computer*, 37(6), 37–46. — informs the keyring-first credential architecture.
- Marshall, I. J., & Wallace, B. C. (2019). Toward systematic review automation. *Systematic Reviews*, 8, 163. — informs the staged-build-with-human-review approach.
- Piwowar, H., et al. (2018). The state of OA. *PeerJ*, 6, e4375. — empirical baseline for OA coverage estimates underpinning the cascade design.
- Saltzer, J. H., & Schroeder, M. D. (1975). The protection of information in computer systems. *Proc. IEEE*, 63(9), 1278–1308. — canonical reference for principle of least privilege.
- Tsafnat, G., et al. (2014). Systematic review automation technologies. *Systematic Reviews*, 3, 74. — informs the always-log-everything observability pattern.

---

## 18. End of handoff

If anything in this document is unclear, ambiguous, or appears to contradict another section, stop and ask before writing code. Do not guess. The cost of asking is low; the cost of building the wrong thing is high.

Begin with Day 1.
