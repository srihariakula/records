"""
Finds REGEX_CONCEPTS (app.services.concepts_registry) matches across a
document's pages, using app.services.page_text_index to map each match's char
span back to a bounding box.
"""
from pathlib import Path
from typing import Dict, List

import fitz  # PyMuPDF

from app.services.concepts_registry import get_regex_concept
from app.services.errors import ConversionError
from app.services.page_text_index import build_page_index


def find_concept_matches(pdf_path: Path, concept_id: str) -> Dict[int, List[List[float]]]:
    """Returns {page_number (1-based): [[x0, y0, x1, y1], ...]} for pages with
    at least one match; pages with none are omitted. Same shape as
    search_text.search_document."""
    concept = get_regex_concept(concept_id)
    if concept is None:
        raise ConversionError(f"Unknown regex concept: {concept_id}", status_code=400)

    matches: Dict[int, List[List[float]]] = {}
    doc = fitz.open(str(pdf_path))
    try:
        for index in range(doc.page_count):
            page_index = build_page_index(doc[index])
            rects = []
            for m in concept.pattern.finditer(page_index.text):
                bbox = page_index.bbox_for_range(m.start(), m.end())
                if bbox:
                    rects.append(bbox)
            if rects:
                matches[index + 1] = rects
    finally:
        doc.close()
    return matches
