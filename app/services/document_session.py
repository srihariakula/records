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
from typing import Optional

import fitz  # PyMuPDF

from app.services import any_to_pdf
from app.services.errors import ConversionError

RENDERED_PDF_FILENAME = "rendered.pdf"


def detect_mime_type(file_path: Path, declared: Optional[str] = None) -> str:
    with open(file_path, "rb") as f:
        head = f.read(16)
    return any_to_pdf.detect_mime_type(head, file_path.name, declared)


def get_pdf_path_for(file_path: Path, mime_type: str) -> Path:
    if mime_type == "application/pdf":
        return file_path

    rendered_path = file_path.parent / RENDERED_PDF_FILENAME
    if not rendered_path.exists():
        pdf_bytes = any_to_pdf.to_pdf_bytes(file_path.read_bytes(), file_path.name, mime_type)
        rendered_path.write_bytes(pdf_bytes)
    return rendered_path


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
