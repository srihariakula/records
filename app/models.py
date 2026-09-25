"""Pydantic request/response models mirroring the Java DocumentConverter DTOs."""
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class DocumentConverterRequest(BaseModel):
    """Mirrors com.leadtools.document_service.models.document.DocumentConverterRequest."""
    docx_path: str
    pdf_file_name: str


class DocumentConverterResponse(BaseModel):
    """Mirrors com.leadtools.document_service.models.document.DocumentConverterResponse."""
    pdf_path: str


class AnnotationObject(BaseModel):
    """
    Simplified annotation schema for this PoC.

    NOT compatible with LEADTOOLS' .ann XML format (leadtools.annotations.engine).
    That format supports a much larger object model (freehand, stamps, redaction,
    encryption, hyperlinks, ...); this covers just rectangles and text labels,
    enough to demonstrate page-wise burn-in during conversion.
    """
    page: int
    type: Literal["rect", "text"]
    x: float
    y: float
    width: float = 0
    height: float = 0
    text: Optional[str] = None
    color: str = "#FF0000"
    value: Optional[str] = Field(
        default=None,
        description=(
            "Manually-corrected extracted-field value (see app.services.field_extraction). "
            "When set, ExtractAnnotatedFields returns this instead of recomputing the text "
            "under the annotation's bounding box from the page content."
        ),
    )


class EmbedAndConvertResult(BaseModel):
    job_id: str
    page_count: int
    rotations_applied: Dict[int, int]
    annotations_applied: int
