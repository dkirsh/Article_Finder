"""
DOI-first ingestion pipeline.

Separates metadata extraction from physical PDF retrieval so paywall or PDF
download failures do not block citation, abstract, and classification metadata.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.parse import quote

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.loader import get
from core.database import Database


StatusCallback = Callable[[Dict[str, Any]], None]


def normalize_doi(doi: str) -> Optional[str]:
    """Normalize a DOI string from raw input, URL, or DOI-prefixed text."""
    if not doi:
        return None
    value = str(doi).strip().strip(",;")
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/", "doi:"):
        if value.lower().startswith(prefix):
            value = value[len(prefix) :]
            break
    value = value.strip()
    return value.lower() if value.lower().startswith("10.") else None


def parse_dois(raw: str) -> List[str]:
    """Parse a single DOI or a comma/newline-separated DOI list."""
    values = re.split(r"[\s,]+", raw or "")
    dois: List[str] = []
    seen = set()
    for value in values:
        doi = normalize_doi(value)
        if doi and doi not in seen:
            seen.add(doi)
            dois.append(doi)
    return dois


def doi_to_filename_stem(doi: str) -> str:
    """Convert DOI to a filename-safe stem used by manual ZIP fallback."""
    return normalize_doi(doi).replace("/", "_").replace(":", "_")


def filename_stem_to_doi(stem: str) -> Optional[str]:
    """Convert a manual ZIP PDF stem back to DOI form."""
    cleaned = str(stem).strip()
    if cleaned.lower().endswith(".pdf"):
        cleaned = cleaned[:-4]
    if cleaned.lower().startswith("doi_"):
        cleaned = cleaned[4:]
    if cleaned.startswith("10.") and "_" in cleaned:
        prefix, suffix = cleaned.split("_", 1)
        return normalize_doi(f"{prefix}/{suffix}")
    return normalize_doi(cleaned.replace("_", "/"))


@dataclass
class MetadataResult:
    doi: str
    citation: Optional[str] = None
    abstract: Optional[str] = None
    article_type: Optional[str] = None
    topic: Optional[str] = None
    errors: List[str] = field(default_factory=list)


@dataclass
class PDFResult:
    doi: str
    success: bool = False
    path: Optional[str] = None
    sha256: Optional[str] = None
    bytes: Optional[int] = None
    provenance: str = "Metadata Only"
    error: Optional[str] = None
    is_oa: Optional[bool] = None
    pdf_url: Optional[str] = None


@dataclass
class IngestionResult:
    doi: str
    status: str
    paper_id: str
    metadata: MetadataResult
    pdf: PDFResult
    created: bool


class CrossrefBibliographyClient:
    """Fetch formatted APA citations through DOI content negotiation."""

    def get_apa_citation(self, doi: str) -> Optional[str]:
        url = f"https://doi.org/{quote(doi, safe='/')}"
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "text/x-bibliography; style=apa",
                "User-Agent": "ArticleFinder/3.2",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            text = response.read().decode("utf-8", errors="replace").strip()
            return text or None


class SemanticScholarClient:
    """Fetch DOI metadata from Semantic Scholar Graph API."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1/paper"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or get("apis.semantic_scholar.api_key")

    def get_details(self, doi: str) -> Dict[str, Any]:
        fields = "abstract,publicationTypes,fieldsOfStudy,title,year,authors,venue"
        url = f"{self.BASE_URL}/DOI:{quote(doi, safe='')}?fields={fields}"
        headers = {"User-Agent": "ArticleFinder/3.2"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))


class UnpaywallPDFClient:
    """Find and download open-access PDFs from Unpaywall."""

    BASE_URL = "https://api.unpaywall.org/v2"

    def __init__(self, email: Optional[str] = None, output_dir: Optional[Path] = None):
        self.email = email or get("apis.unpaywall.email", "your-email@example.com")
        self.output_dir = Path(output_dir or get("paths.pdfs", "data/pdfs"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def fetch(self, doi: str) -> PDFResult:
        result = PDFResult(doi=doi)
        if not self.email or "@" not in self.email:
            result.error = "Unpaywall requires a valid email"
            return result

        try:
            url = f"{self.BASE_URL}/{quote(doi, safe='')}?email={quote(self.email)}"
            req = urllib.request.Request(url, headers={"User-Agent": "ArticleFinder/3.2"})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            result.error = f"Unpaywall HTTP {exc.code}"
            return result
        except Exception as exc:
            result.error = f"Unpaywall lookup failed: {exc}"
            return result

        result.is_oa = bool(data.get("is_oa"))
        if not result.is_oa:
            result.error = "Not open access"
            return result

        location = data.get("best_oa_location") or {}
        pdf_url = location.get("url_for_pdf")
        if not pdf_url:
            for candidate in data.get("oa_locations", []):
                pdf_url = candidate.get("url_for_pdf")
                if pdf_url:
                    break
        if not pdf_url:
            result.error = "Open access record has no PDF URL"
            return result

        result.pdf_url = pdf_url
        return self._download_pdf(doi, pdf_url)

    def _download_pdf(self, doi: str, pdf_url: str) -> PDFResult:
        result = PDFResult(doi=doi, is_oa=True, pdf_url=pdf_url)
        try:
            req = urllib.request.Request(
                pdf_url,
                headers={"User-Agent": "ArticleFinder/3.2", "Accept": "application/pdf"},
            )
            with urllib.request.urlopen(req, timeout=60) as response:
                pdf_data = response.read()
            if not pdf_data.startswith(b"%PDF"):
                result.error = "Downloaded file is not a PDF"
                return result

            path = self.output_dir / f"{doi_to_filename_stem(doi)}.pdf"
            path.write_bytes(pdf_data)
            result.success = True
            result.path = str(path)
            result.sha256 = hashlib.sha256(pdf_data).hexdigest()
            result.bytes = len(pdf_data)
            result.provenance = "Open Access / Unpaywall"
            return result
        except urllib.error.HTTPError as exc:
            result.error = f"PDF HTTP {exc.code}"
        except Exception as exc:
            result.error = f"PDF download failed: {exc}"
        return result


class DOIPDFIngestionPipeline:
    """Concurrent DOI metadata, OA PDF, deduplication, and ZIP fallback pipeline."""

    def __init__(
        self,
        database: Database,
        semantic_scholar_api_key: Optional[str] = None,
        unpaywall_email: Optional[str] = None,
        pdf_dir: Optional[Path] = None,
        max_workers: int = 4,
    ):
        self.db = database
        self.crossref = CrossrefBibliographyClient()
        self.semantic_scholar = SemanticScholarClient(semantic_scholar_api_key)
        self.unpaywall = UnpaywallPDFClient(unpaywall_email, pdf_dir)
        self.max_workers = max_workers

    def ingest_batch(self, dois: Iterable[str], status_callback: Optional[StatusCallback] = None) -> List[IngestionResult]:
        normalized = [doi for doi in (normalize_doi(d) for d in dois) if doi]
        results: List[IngestionResult] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.ingest_one, doi, status_callback): doi for doi in normalized}
            for future in as_completed(futures):
                results.append(future.result())
        return sorted(results, key=lambda item: normalized.index(item.doi))

    def ingest_one(self, doi: str, status_callback: Optional[StatusCallback] = None) -> IngestionResult:
        self._emit(status_callback, doi, "Pending")
        with ThreadPoolExecutor(max_workers=2) as executor:
            metadata_future = executor.submit(self._fetch_metadata, doi)
            pdf_future = executor.submit(self.unpaywall.fetch, doi)
            metadata = metadata_future.result()
            self._emit(status_callback, doi, "Metadata Extracted")
            pdf = pdf_future.result()

        paper_id, created = self._upsert_paper(doi, metadata, pdf)
        status = "PDF Downloaded" if pdf.success else "PDF Failed"
        self._emit(status_callback, doi, status)
        return IngestionResult(doi=doi, status=status, paper_id=paper_id, metadata=metadata, pdf=pdf, created=created)

    def process_manual_zip(self, zip_path: Path, status_callback: Optional[StatusCallback] = None) -> Dict[str, Any]:
        stats = {"total_pdfs": 0, "updated": 0, "unmatched": [], "errors": []}
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                with zipfile.ZipFile(zip_path) as archive:
                    archive.extractall(tmpdir)
            except Exception as exc:
                stats["errors"].append(f"Could not unzip file: {exc}")
                return stats

            for pdf in Path(tmpdir).rglob("*.pdf"):
                stats["total_pdfs"] += 1
                doi = filename_stem_to_doi(pdf.stem)
                if not doi:
                    stats["unmatched"].append(pdf.name)
                    continue
                paper = self.db.get_paper_by_doi(doi)
                if not paper:
                    stats["unmatched"].append(pdf.name)
                    continue

                try:
                    dest = self.unpaywall.output_dir / f"{doi_to_filename_stem(doi)}.pdf"
                    shutil.copy2(pdf, dest)
                    pdf_data = dest.read_bytes()
                    patch = {
                        "pdf_path": str(dest),
                        "pdf_sha256": hashlib.sha256(pdf_data).hexdigest(),
                        "pdf_bytes": len(pdf_data),
                        "pdf_source": "Manual ZIP Upload",
                    }
                    self._update_empty_or_pdf_fields(paper["paper_id"], patch)
                    stats["updated"] += 1
                    self._emit(status_callback, doi, "Manual ZIP Uploaded")
                except Exception as exc:
                    stats["errors"].append(f"{pdf.name}: {exc}")
        return stats

    def _fetch_metadata(self, doi: str) -> MetadataResult:
        result = MetadataResult(doi=doi)
        try:
            result.citation = self.crossref.get_apa_citation(doi)
        except Exception as exc:
            result.errors.append(f"Crossref citation failed: {exc}")

        try:
            details = self.semantic_scholar.get_details(doi)
            result.abstract = details.get("abstract")
            result.article_type = "; ".join(details.get("publicationTypes") or []) or None
            result.topic = "; ".join(details.get("fieldsOfStudy") or []) or None
        except urllib.error.HTTPError as exc:
            result.errors.append(f"Semantic Scholar HTTP {exc.code}")
        except Exception as exc:
            result.errors.append(f"Semantic Scholar failed: {exc}")
        return result

    def _upsert_paper(self, doi: str, metadata: MetadataResult, pdf: PDFResult) -> tuple[str, bool]:
        existing = self.db.get_paper_by_doi(doi)
        now = datetime.utcnow().isoformat()
        if existing:
            patch = {
                "abstract": metadata.abstract,
                "citation": metadata.citation,
                "article_type": metadata.article_type,
                "topic": metadata.topic,
                "pdf_path": pdf.path if pdf.success else None,
                "pdf_sha256": pdf.sha256 if pdf.success else None,
                "pdf_bytes": pdf.bytes if pdf.success else None,
                "pdf_source": pdf.provenance,
                "ingest_method": "doi_pdf_pipeline",
                "retrieved_at": now,
            }
            self._update_empty_or_pdf_fields(existing["paper_id"], patch)
            return existing["paper_id"], False

        paper = {
            "paper_id": f"doi:{doi}",
            "doi": doi,
            "title": metadata.citation or doi,
            "abstract": metadata.abstract,
            "citation": metadata.citation,
            "article_type": metadata.article_type,
            "topic": metadata.topic,
            "source": "api",
            "ingest_method": "doi_pdf_pipeline",
            "retrieved_at": now,
            "pdf_path": pdf.path if pdf.success else None,
            "pdf_sha256": pdf.sha256 if pdf.success else None,
            "pdf_bytes": pdf.bytes if pdf.success else None,
            "pdf_source": pdf.provenance,
            "status": "downloaded" if pdf.success else "candidate",
        }
        paper_id = self.db.add_paper({key: value for key, value in paper.items() if value is not None})
        return paper_id, True

    def _update_empty_or_pdf_fields(self, paper_id: str, values: Dict[str, Any]) -> None:
        writable = {key: value for key, value in values.items() if value is not None}
        if not writable:
            return
        existing = self.db.get_paper(paper_id)
        if not existing:
            return

        updates = {}
        for key, value in writable.items():
            if key.startswith("pdf_") or key in {"pdf_path", "pdf_source", "retrieved_at", "ingest_method"}:
                updates[key] = value
            elif not existing.get(key):
                updates[key] = value

        if not updates:
            return
        updates["updated_at"] = datetime.utcnow().isoformat()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        params = list(updates.values()) + [paper_id]
        with self.db.connection() as conn:
            conn.execute(f"UPDATE papers SET {assignments} WHERE paper_id = ?", params)

    def _emit(self, callback: Optional[StatusCallback], doi: str, status: str) -> None:
        if callback:
            callback({"doi": doi, "status": status, "updated_at": datetime.utcnow().isoformat()})
