"""
Per-document helpers used by the cache and the Page viewer endpoints.

LEADTOOLS' LEADDocument/DocumentPage abstraction works uniformly across many
source formats. Here that's approximated by normalizing everything to a PDF once
(app.services.any_to_pdf: images via Pillow/PyMuPDF, office formats via
LibreOffice) and caching that PDF next to the source file -- all page
operations (image, thumbnail, text) then go through PyMuPDF against that
single representation.
"""
from pathlib import Path
from typing import Optional, Tuple

import fitz  # PyMuPDF

from app.services import any_to_pdf
from app.services.errors import ConversionError

RENDERED_PDF_FILENAME = "rendered.pdf"
# Written next to a PDF upload once it's been checked and needed no OCR, so
# later page requests don't re-open and re-check it every time.
NO_RENDER_MARKER = ".pdf-as-is"
RESERVED_NAMES = {RENDERED_PDF_FILENAME, NO_RENDER_MARKER}


def detect_mime_type(file_path: Path, declared: Optional[str] = None) -> str:
    with open(file_path, "rb") as f:
        head = f.read(16)
    return any_to_pdf.detect_mime_type(head, file_path.name, declared)


def ensure_pdf(file_path: Path, mime_type: str) -> Tuple[Path, int]:
    """Converts (and OCRs) the upload once, caching the result next to it.
    Returns (pdf path, pages OCR'd by this call -- 0 when already cached).
    A PDF that needed no OCR is served as-is, without a copy."""
    rendered_path = file_path.parent / RENDERED_PDF_FILENAME
    if rendered_path.exists():
        return rendered_path, 0
    if (file_path.parent / NO_RENDER_MARKER).exists():
        return file_path, 0

    data = file_path.read_bytes()
    result = any_to_pdf.convert(data, file_path.name, mime_type)
    if result.pdf_bytes is data:  # PDF upload, nothing to add
        (file_path.parent / NO_RENDER_MARKER).touch()
        return file_path, 0
    rendered_path.write_bytes(result.pdf_bytes)
    return rendered_path, result.ocr_pages


def get_pdf_path_for(file_path: Path, mime_type: str) -> Path:
    return ensure_pdf(file_path, mime_type)[0]


def get_pdf_path(entry) -> Path:
    return get_pdf_path_for(entry.file_path, entry.mime_type)


def count_pages(pdf_path: Path) -> int:
    try:
        doc = fitz.open(str(pdf_path), filetype="pdf")
    except (fitz.FileDataError, RuntimeError, ValueError) as exc:
        raise ConversionError("Document is damaged or not a readable PDF") from exc
    try:
        return doc.page_count
    finally:
        doc.close()
