"""Mirrors com.leadtools.document_service.controllers.DocumentConverterController (@Path("convert"))."""
import json
from typing import Dict, List, Optional

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse, Response

from app.models import AnnotationObject, DocumentConverterRequest, DocumentConverterResponse
from app.services import any_to_pdf, content_disposition, embed_convert, office_convert

router = APIRouter(prefix="/convert", tags=["convert"])

# ConversionError raised by the service layer below is turned into a JSON error
# response by the global handler registered in app.main.


@router.post("/to-pdf")
async def convert_to_pdf(file: UploadFile = File(...)) -> Response:
    """Mirrors convertToPdf(InputStream, FormDataContentDisposition) -> application/pdf.
    Accepts PDFs (returned as-is), raster images and office formats -- see
    app.services.any_to_pdf."""
    pdf_bytes = any_to_pdf.to_pdf_bytes(await file.read(), file.filename or "document")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": content_disposition.attachment(f"{file.filename or 'document'}.pdf")},
    )


@router.post("/to-pdf-path", response_model=DocumentConverterResponse)
async def convert_to_pdf_path(request: DocumentConverterRequest):
    """Mirrors convertToPdf(DocumentConverterRequest) -> JSON { pdfPath }.

    Server-local file path conversion, same as the original endpoint. Not intended
    to accept arbitrary client-supplied paths without validation in a real deployment.
    """
    pdf_path = office_convert.convert_path_to_pdf(request.docx_path, request.pdf_file_name)
    return DocumentConverterResponse(pdf_path=pdf_path)


@router.post("/embed-and-convert")
async def embed_and_convert(
    file: UploadFile = File(...),
    annotations: Optional[str] = Form(None),
    rotation: Optional[str] = Form(None),
) -> Response:
    """Mirrors embedAndConvert(...) -> application/zip.

    `annotations` is a JSON array matching AnnotationObject (see app.models docstring
    for why this replaces LEADTOOLS' .ann XML). `rotation` is a JSON object of
    {"<page number>": <0|90|180|270>}, same shape as the original endpoint's map.
    """
    try:
        parsed_annotations: List[AnnotationObject] = (
            [AnnotationObject(**a) for a in json.loads(annotations)] if annotations else []
        )
        raw_rotation: Dict[str, int] = json.loads(rotation) if rotation else {}
        rotation_map = {int(page): degrees for page, degrees in raw_rotation.items()}
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return JSONResponse(status_code=400, content={"message": f"Invalid annotations/rotation payload: {exc}"})

    zip_bytes = embed_convert.embed_and_convert(
        await file.read(), file.filename or "document", parsed_annotations, rotation_map
    )
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="result.zip"'},
    )
