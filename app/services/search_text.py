"""
Whole-document text search. Not present in the original API -- LEADTOOLS'
document-service has no server-side search endpoint; DocumentViewerDemo's
search box (if any) would have been implemented client-side inside the
missing Leadtools.Document.Viewer.js.

The plain default path (no flags) is built directly on PyMuPDF's
page.search_for, which finds case-insensitive exact-substring matches and
returns their bounding boxes in PDF point space -- the same coordinate system
used for annotations, so the viewer can highlight results with the same
overlay math. The Case sensitive / Whole word / Regex checkboxes need
capabilities search_for doesn't have, so that path instead runs a compiled
pattern over app.services.page_text_index's per-page text and maps spans back
to boxes -- the same mechanism app.services.regex_concepts uses.
"""
import re
from pathlib import Path
from typing import Dict, List

import fitz  # PyMuPDF

from app.services.errors import ConversionError
from app.services.page_text_index import build_page_index


def search_document(
    pdf_path: Path,
    query: str,
    case_sensitive: bool = False,
    whole_word: bool = False,
    use_regex: bool = False,
) -> Dict[int, List[List[float]]]:
    """Returns {page_number (1-based): [[x0, y0, x1, y1], ...]} for pages with
    at least one match; pages with none are omitted."""
    matches: Dict[int, List[List[float]]] = {}
    if not query:
        return matches

    doc = fitz.open(str(pdf_path))
    try:
        if not (case_sensitive or whole_word or use_regex):
            for index in range(doc.page_count):
                rects = doc[index].search_for(query)
                if rects:
                    matches[index + 1] = [[r.x0, r.y0, r.x1, r.y1] for r in rects]
            return matches

        pattern_text = query if use_regex else re.escape(query)
        if whole_word:
            pattern_text = rf"\b{pattern_text}\b"
        try:
            compiled = re.compile(pattern_text, 0 if case_sensitive else re.IGNORECASE)
        except re.error as exc:
            raise ConversionError(f"Invalid search pattern: {exc}", status_code=400)

        for index in range(doc.page_count):
            page_index = build_page_index(doc[index])
            rects = []
            for m in compiled.finditer(page_index.text):
                bbox = page_index.bbox_for_range(m.start(), m.end())
                if bbox:
                    rects.append(bbox)
            if rects:
                matches[index + 1] = rects
        return matches
    finally:
        doc.close()
