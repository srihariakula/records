"""
Burns this port's simplified AnnotationObject overlay (see app.models) into
real PDF annotation objects on the underlying document, producing a single
downloadable, self-contained PDF.

The original LEADTOOLS service never actually does this: Factory.DownloadDocument's
`includeAnnotations` flag bundles the raw document and a separate `.ann` XML
sidecar together in a zip -- the client viewer re-overlays them from that
sidecar. This endpoint instead merges them server-side into one file using
PyMuPDF's native PDF annotation objects (Square / FreeText), which is more
useful as a hand-this-to-someone-else artifact, at the cost of no longer
matching the original's "document + sidecar" contract.
"""
from pathlib import Path
from typing import Dict, List, Tuple

import fitz  # PyMuPDF

from app.models import AnnotationObject

_DEFAULT_RGB = (1.0, 0.0, 0.0)


def _hex_to_rgb01(hex_color: str) -> Tuple[float, float, float]:
    value = (hex_color or "").lstrip("#")
    if len(value) != 6:
        return _DEFAULT_RGB
    try:
        r, g, b = (int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
        return (r, g, b)
    except ValueError:
        return _DEFAULT_RGB


def burn_annotations_into_pdf(pdf_path: Path, annotations_by_page: Dict[int, List[AnnotationObject]]) -> bytes:
    doc = fitz.open(str(pdf_path))
    try:
        for page_number, annotations in annotations_by_page.items():
            if page_number < 1 or page_number > doc.page_count or not annotations:
                continue
            page = doc[page_number - 1]
            for ann in annotations:
                color = _hex_to_rgb01(ann.color)
                if ann.type == "rect":
                    rect = fitz.Rect(ann.x, ann.y, ann.x + ann.width, ann.y + ann.height)
                    annot = page.add_rect_annot(rect)
                    annot.set_colors(stroke=color)
                    annot.set_border(width=2)
                    if ann.text:
                        annot.set_info(content=ann.text)
                    annot.update()
                elif ann.type == "text":
                    width = max(ann.width, 150)
                    height = max(ann.height, 20)
                    rect = fitz.Rect(ann.x, ann.y, ann.x + width, ann.y + height)
                    annot = page.add_freetext_annot(rect, ann.text or "", fontsize=10, text_color=color)
                    annot.update()
        return doc.tobytes()
    finally:
        doc.close()
