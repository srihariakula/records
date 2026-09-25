"""
Finds NER_CONCEPTS (app.services.concepts_registry) matches across a
document's pages via the GLiNER2 sidecar (app.services.ner_client), one page
at a time so each sidecar call stays scoped to a single page's text and its
char offsets map unambiguously back through that page's own
app.services.page_text_index.
"""
from pathlib import Path
from typing import Dict, List

import fitz  # PyMuPDF

from app.services import ner_client
from app.services.concepts_registry import get_ner_concept
from app.services.errors import ConversionError
from app.services.page_text_index import build_page_index


def find_concept_matches(pdf_path: Path, concept_id: str) -> Dict[int, List[List[float]]]:
    """Returns {page_number (1-based): [[x0, y0, x1, y1], ...]} for pages with
    at least one match; pages with none are omitted. Same shape as
    search_text.search_document."""
    concept = get_ner_concept(concept_id)
    if concept is None:
        raise ConversionError(f"Unknown NER concept: {concept_id}", status_code=400)

    matches: Dict[int, List[List[float]]] = {}
    doc = fitz.open(str(pdf_path))
    try:
        for index in range(doc.page_count):
            page_index = build_page_index(doc[index])
            entities = ner_client.extract_entities(page_index.text, concept.gliner_label, threshold=concept.threshold)
            rects = []
            for entity in entities:
                bbox = page_index.bbox_for_range(entity["start"], entity["end"])
                if bbox:
                    rects.append(bbox)
            if rects:
                matches[index + 1] = rects
    finally:
        doc.close()
    return matches
