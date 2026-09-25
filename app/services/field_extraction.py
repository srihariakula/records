"""
Extracts the underlying document text under each labeled annotation, pairing
the annotation's label (the "key") with the real page text inside its bounding
box (the "value") -- a lightweight analogue of LEADTOOLS' forms-recognition
field extraction, driven by the same simplified AnnotationObject overlay used
elsewhere in this port (see app.models).

Not in the original API by this name -- Page/GetAnnotations only ever returns
the annotation objects themselves, never resolves them against page content.
"""
from pathlib import Path
from typing import Dict, List

import fitz  # PyMuPDF

from app.models import AnnotationObject


def extract_annotated_fields(pdf_path: Path, annotations_by_page: Dict[int, List[AnnotationObject]]) -> List[dict]:
    """Returns a list of {page, index, label, value, x, y, width, height}, one
    per labeled annotation (annotations with no text label are skipped --
    there's nothing to key them by).

    `index` is the annotation's position within entry.annotations[page] (not
    within this filtered list) -- Factory/UpdateAnnotatedField takes it back
    as-is to identify which annotation on which page to edit, the same
    index-based identity already used for move/resize/delete in the viewer.

    If the annotation has a manually-corrected `value` set (via
    UpdateAnnotatedField), that's returned as-is instead of recomputing the
    text under its bounding box.
    """
    fields: List[dict] = []
    doc = fitz.open(str(pdf_path))
    try:
        for page_number in sorted(annotations_by_page):
            if page_number < 1 or page_number > doc.page_count:
                continue
            page = doc[page_number - 1]
            for index, ann in enumerate(annotations_by_page[page_number]):
                if not ann.text:
                    continue
                if ann.value is not None:
                    value = ann.value
                else:
                    rect = fitz.Rect(ann.x, ann.y, ann.x + ann.width, ann.y + ann.height)
                    value = page.get_textbox(rect).strip()
                fields.append({
                    "page": page_number,
                    "index": index,
                    "label": ann.text,
                    "value": value,
                    "x": ann.x,
                    "y": ann.y,
                    "width": ann.width,
                    "height": ann.height,
                })
    finally:
        doc.close()
    return fields
