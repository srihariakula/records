"""
Per-document helpers used by the cache and the Page viewer endpoints.

LEADTOOLS' LEADDocument/DocumentPage abstraction works uniformly across many
source formats. Here that's approximated by normalizing everything to a PDF once
(via LibreOffice, same engine as app.services.office_convert) and caching that
PDF next to the source file -- all page operations (image, thumbnail, text) then
go through PyMuPDF against that single representation.
"""
import mimetypes
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from app.services.office_convert import convert_bytes_to_pdf

RENDERED_PDF_FILENAME = "rendered.pdf"


def detect_mime_type(file_path: Path, declared: Optional[str] = None) -> str:
    if declared:
        return declared
    head = file_path.read_bytes()[:4]
    if head == b"%PDF":
        return "application/pdf"
    guessed, _ = mimetypes.guess_type(str(file_path))
    return guessed or "application/octet-stream"


def get_pdf_path_for(file_path: Path, mime_type: str) -> Path:
    if mime_type == "application/pdf":
        return file_path

    rendered_path = file_path.parent / RENDERED_PDF_FILENAME
    if not rendered_path.exists():
        pdf_bytes = convert_bytes_to_pdf(file_path.read_bytes(), file_path.name)
        rendered_path.write_bytes(pdf_bytes)
    return rendered_path


def get_pdf_path(entry) -> Path:
    return get_pdf_path_for(entry.file_path, entry.mime_type)


def count_pages(pdf_path: Path) -> int:
    doc = fitz.open(str(pdf_path))
    try:
        return doc.page_count
    finally:
        doc.close()
