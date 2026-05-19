"""
PDF download validation: safe paths, magic bytes, size cap, content-type.
"""
from __future__ import annotations
import hashlib
import os
import re
from pathlib import Path
from typing import Optional

MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB
MIN_PDF_BYTES = 1024  # 1 KB
PDF_MAGIC = b"%PDF-"


def safe_filename(year: Optional[int], first_author: Optional[str],
                  title: Optional[str], doi: Optional[str]) -> str:
    parts = [
        str(year) if year else "noyear",
        re.sub(r"[^a-z0-9]", "", (first_author or "unknown").lower())[:24] or "unknown",
        re.sub(r"[^a-z0-9-]+", "-", (title or "untitled").lower()).strip("-")[:40] or "untitled",
        hashlib.sha1((doi or "").encode("utf-8")).hexdigest()[:8],
    ]
    return "_".join(parts) + ".pdf"


def ensure_safe_path(out_dir: Path, filename: str) -> Path:
    """Reject path-traversal attempts; ensure result is inside out_dir."""
    out_dir = out_dir.resolve()
    candidate = (out_dir / filename).resolve()
    if not str(candidate).startswith(str(out_dir) + os.sep) and candidate != out_dir:
        raise ValueError(f"unsafe path: {candidate} not in {out_dir}")
    return candidate


def looks_like_pdf(data: bytes) -> bool:
    return len(data) >= MIN_PDF_BYTES and data[:5] == PDF_MAGIC


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
