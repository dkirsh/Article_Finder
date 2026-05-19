"""
Strict OA-only PDF downloader.

Cardinal rule: this module REFUSES to download any URL that does not come
from a legal OA source (an `OALocation` produced by oa_resolver). There is
no escape hatch for Sci-Hub or any other unauthorized source.

There is no `scidownl`, `scihub`, or `scihub_downloader` import in this
file or anywhere else in article_finder_v2. The compliance test enforces
this.
"""
from __future__ import annotations
import time
from pathlib import Path
from typing import Optional, Tuple
from .validators import (MAX_PDF_BYTES, ensure_safe_path, looks_like_pdf,
                          safe_filename, sha256)
from .oa_resolver import OALocation, resolve

try:
    import requests
except ImportError:
    requests = None


def download_pdf(record: dict, out_dir: Path, *,
                 enable_network: bool = True) -> dict:
    """
    Try to download the PDF for `record`. Returns a dict suitable for
    `download_report.json`:
        {
          reference_id, pdf_status, pdf_url, local_pdf_path, pdf_sha256,
          source, legal_oa_proof, reason
        }
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    base = {
        "canonical_id": record.get("canonical_id"),
        "doi": record.get("doi"),
        "pdf_url": None,
        "local_pdf_path": None,
        "pdf_sha256": None,
        "source": None,
        "legal_oa_proof": None,
    }

    loc = resolve(record, enable_network=enable_network)
    if loc is None:
        return {**base, "pdf_status": "no_oa_pdf",
                "reason": "no legal OA URL found across cascade"}

    base["pdf_url"] = loc.pdf_url
    base["source"] = loc.source
    base["legal_oa_proof"] = loc.legal_oa_proof

    # Compute target path
    fname = safe_filename(record.get("year"),
                           record.get("first_author_surname"),
                           record.get("title"),
                           record.get("doi") or record.get("canonical_id"))
    try:
        target = ensure_safe_path(out_dir, fname)
    except ValueError as e:
        return {**base, "pdf_status": "failed_validation", "reason": str(e)}

    if target.exists():
        data = target.read_bytes()
        return {**base, "pdf_status": "already_exists",
                "local_pdf_path": str(target),
                "pdf_sha256": sha256(data),
                "reason": "file already on disk"}

    if not enable_network or requests is None:
        return {**base, "pdf_status": "skipped_no_download",
                "reason": "network disabled or requests not installed"}

    # Stream-download with a hard byte cap
    try:
        with requests.get(loc.pdf_url, stream=True, timeout=30) as r:
            if r.status_code != 200:
                return {**base, "pdf_status": "failed_network",
                        "reason": f"http {r.status_code}"}
            ctype = (r.headers.get("Content-Type") or "").lower()
            if "pdf" not in ctype and not loc.pdf_url.lower().endswith(".pdf"):
                # Some publishers return application/octet-stream; allow IF the URL
                # is a .pdf and the magic bytes match below. Else reject.
                pass
            buf = bytearray()
            for chunk in r.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                buf.extend(chunk)
                if len(buf) > MAX_PDF_BYTES:
                    return {**base, "pdf_status": "failed_validation",
                            "reason": f"exceeded {MAX_PDF_BYTES} bytes"}
        data = bytes(buf)
    except Exception as e:
        return {**base, "pdf_status": "failed_network", "reason": str(e)}

    if not looks_like_pdf(data):
        return {**base, "pdf_status": "failed_validation",
                "reason": "missing %PDF- magic bytes or too small"}

    target.write_bytes(data)
    return {**base, "pdf_status": "downloaded",
            "local_pdf_path": str(target),
            "pdf_sha256": sha256(data),
            "reason": f"downloaded via {loc.source}"}
