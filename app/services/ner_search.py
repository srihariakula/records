"""
Finds GLiNER2 entity matches across a document's pages via the sidecar
(app.services.ner_client) -- either for a registered NER_CONCEPTS id
(app.services.concepts_registry) or for a free-text label typed into the
viewer's search box with its NER checkbox ticked -- one page
at a time so each sidecar call stays scoped to a single page's text and its
char offsets map unambiguously back through that page's own
app.services.page_text_index.
"""
from pathlib import Path
from typing import Dict, List, Optional

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
    return find_label_matches(pdf_path, concept.gliner_label, threshold=concept.threshold)


def find_label_matches(pdf_path: Path, gliner_label: str,
                       threshold: Optional[float] = None) -> Dict[int, List[List[float]]]:
    """Same as find_concept_matches, but for an arbitrary zero-shot label
    (e.g. "medication") instead of a registered concept id."""
    matches: Dict[int, List[List[float]]] = {}
    doc = fitz.open(str(pdf_path))
    try:
        for index in range(doc.page_count):
            page_index = build_page_index(doc[index])
            entities = ner_client.extract_entities(page_index.text, gliner_label, threshold=threshold)
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
