"""Mirrors com.leadtools.document_service.controllers.Page (@Path("Page")),
minus GetSvg / GetSvgBackImage (LEADTOOLS' proprietary vector SVG object model)
and ReadBarcodes (a separate capability, see document-service-py/README.md)."""
from typing import Optional

import fitz  # PyMuPDF
from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.models_page import (
    GetAnnotationsRequest,
    GetAnnotationsResponse,
    GetTextRequest,
    GetTextResponse,
    SetAnnotationsRequest,
    SetAnnotationsResponse,
    WordBox,
)
from app.services import document_session, image_render
from app.services.cache_store import cache
from app.services.errors import ConversionError

router = APIRouter(prefix="/Page", tags=["page"])


@router.get("/GetImage")
async def get_image(
    document_id: str = Query(..., alias="documentId"),
    page_number: int = Query(0, alias="pageNumber"),
    resolution: int = Query(0),
    mime_type: str = Query("image/jpeg", alias="mimeType"),
    bits_per_pixel: int = Query(0, alias="bitsPerPixel"),
    quality_factor: int = Query(0, alias="qualityFactor"),
    width: int = Query(0),
    height: int = Query(0),
):
    if page_number < 0 or width < 0 or height < 0 or resolution < 0 or not (0 <= quality_factor <= 100):
        raise ConversionError("Invalid GetImage parameters", status_code=400)
    page_number = page_number or 1

    entry = cache.require(document_id)
    pdf_path = document_session.get_pdf_path(entry)
    image = image_render.render_page_image(pdf_path, page_number, resolution, width, height, bits_per_pixel)
    data, content_type = image_render.encode_image(image, mime_type, quality_factor)
    return Response(content=data, media_type=content_type)


@router.get("/GetThumbnail")
async def get_thumbnail(
    document_id: str = Query(..., alias="documentId"),
    page_number: int = Query(0, alias="pageNumber"),
    mime_type: str = Query("image/jpeg", alias="mimeType"),
    width: int = Query(0),
    height: int = Query(0),
):
    if page_number < 0 or width < 0 or height < 0:
        raise ConversionError("Invalid GetThumbnail parameters", status_code=400)
    page_number = page_number or 1
    width = width or image_render.DEFAULT_THUMBNAIL_SIZE[0]
    height = height or image_render.DEFAULT_THUMBNAIL_SIZE[1]

    entry = cache.require(document_id)
    pdf_path = document_session.get_pdf_path(entry)
    image = image_render.render_page_image(pdf_path, page_number, 0, width, height, 0)
    data, content_type = image_render.encode_image(image, mime_type, 0)
    return Response(content=data, media_type=content_type)


@router.post("/GetText", response_model=GetTextResponse)
async def get_text(request: GetTextRequest):
    if request.page_number < 0:
        raise ConversionError("'pageNumber' must be >= 0", status_code=400)
    page_number = request.page_number or 1

    entry = cache.require(request.document_id)
    pdf_path = document_session.get_pdf_path(entry)

    doc = fitz.open(str(pdf_path))
    try:
        if page_number > doc.page_count:
            raise ConversionError(f"'pageNumber' is out of range for this document (1-{doc.page_count})",
                                   status_code=400)
        page = doc[page_number - 1]
        response = GetTextResponse()
        if request.build_text:
            response.text = page.get_text("text")
        if request.build_words:
            response.words = [
                WordBox(text=w[4], x0=w[0], y0=w[1], x1=w[2], y1=w[3])
                for w in page.get_text("words")
            ]
        return response
    finally:
        doc.close()


@router.post("/GetAnnotations", response_model=GetAnnotationsResponse)
async def get_annotations(request: GetAnnotationsRequest):
    if request.page_number < 0:
        raise ConversionError("'pageNumber' must be >= 0", status_code=400)
    entry = cache.require(request.document_id)
    if request.page_number == 0:
        annotations = [a for page_anns in entry.annotations.values() for a in page_anns]
    else:
        annotations = entry.annotations.get(request.page_number, [])
    return GetAnnotationsResponse(annotations=annotations)


@router.post("/SetAnnotations", response_model=SetAnnotationsResponse)
async def set_annotations(request: SetAnnotationsRequest):
    if request.page_number < 0:
        raise ConversionError("'pageNumber' must be >= 0", status_code=400)
    entry = cache.require(request.document_id)
    if request.page_number == 0:
        entry.annotations.clear()
        for ann in request.annotations:
            entry.annotations.setdefault(ann.page, []).append(ann)
    else:
        entry.annotations[request.page_number] = request.annotations
    return SetAnnotationsResponse()
