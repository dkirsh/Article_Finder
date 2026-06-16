"""Open-access PDF acquisition helpers.

This module supplies small acquisition helpers for the candidate-discovery
stage: strict `%PDF-` byte validation, SHA-256 recording, and an explicit
assisted-browser registration path for OA files retrieved manually.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Callable


FetchResult = tuple[int, bytes]
Fetcher = Callable[[str, dict[str, str], int], FetchResult]


def _default_fetch(url: str, headers: dict[str, str], timeout: int) -> FetchResult:
    import requests

    response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    return response.status_code, response.content or b""


def store_pdf_bytes(data: bytes, reference_id: str, out_dir: Path) -> tuple[Path, str]:
    if data[:5] != b"%PDF-":
        raise ValueError("downloaded bytes are not a PDF")
    out_dir.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(data).hexdigest()
    path = out_dir / f"{reference_id}.pdf"
    path.write_bytes(data)
    return path, sha


def download_pdf_url(
    url: str | None,
    reference_id: str,
    out_dir: Path,
    *,
    fetch: Fetcher | None = None,
    timeout: int = 30,
) -> tuple[Path, str] | None:
    if not url:
        return None
    fetch = fetch or _default_fetch
    status, data = fetch(
        url,
        {"User-Agent": "ArticleFinderCandidateDiscovery/1.0", "Accept": "application/pdf,*/*"},
        timeout,
    )
    if status != 200 or data[:5] != b"%PDF-":
        return None
    return store_pdf_bytes(data, reference_id, out_dir)


def register_browser_pdf(
    candidate_buffer,
    reference_id: str,
    source_pdf: str | Path,
    out_dir: str | Path,
    *,
    source: str = "browser_assisted",
) -> dict[str, str | int]:
    """Register a browser-downloaded OA PDF into the candidate buffer.

    This is for open-access PDFs that the automated fetcher cannot retrieve
    because of publisher bot protection. It does not bypass paywalls.
    """
    source_pdf = Path(source_pdf).expanduser()
    if not source_pdf.exists():
        raise FileNotFoundError(source_pdf)
    data = source_pdf.read_bytes()
    if data[:5] != b"%PDF-":
        raise ValueError(f"not a PDF: {source_pdf}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{reference_id}.pdf"
    shutil.copy2(source_pdf, dest)
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    candidate_buffer.record_pdf(
        reference_id,
        pdf_path=dest,
        pdf_sha256=sha,
        source=source,
        agent="browser_assisted_acquisition",
    )
    return {
        "reference_id": reference_id,
        "pdf_path": str(dest),
        "sha256": sha,
        "bytes": dest.stat().st_size,
        "source": source,
    }
