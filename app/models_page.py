"""Mirrors com.leadtools.document_service.models.page.* (the subset ported)."""
from typing import List, Optional

from pydantic import BaseModel

from app.models import AnnotationObject


class GetTextRequest(BaseModel):
    document_id: str
    page_number: int = 0  # 0 defaults to page 1
    build_words: bool = False
    build_text: bool = True


class WordBox(BaseModel):
    text: str
    x0: float
    y0: float
    x1: float
    y1: float


class GetTextResponse(BaseModel):
    """No OCR is performed -- this returns the PDF's embedded text layer only
    (via PyMuPDF), same limitation already documented for the `convert`
    endpoints. Image-only / scanned pages return empty text."""
    text: Optional[str] = None
    words: List[WordBox] = []


class GetAnnotationsRequest(BaseModel):
    document_id: str
    page_number: int = 0  # 0 = all pages


class GetAnnotationsResponse(BaseModel):
    annotations: List[AnnotationObject] = []


class SetAnnotationsRequest(BaseModel):
    document_id: str
    page_number: int = 0  # 0 = replace annotations for every page
    annotations: List[AnnotationObject] = []


class SetAnnotationsResponse(BaseModel):
    ok: bool = True
