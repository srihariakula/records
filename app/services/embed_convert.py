"""
Page-wise rotate + annotate + rasterize + zip.

Ports DocumentConverterHelper.embedAndConvert(...). LEADTOOLS renders its native
.ann XML annotation objects through AnnJavaRenderingEngine and burns them into a
JPEG per page via DocumentConverter/DocumentWriter. Here the same page pipeline
(rotate -> render -> overlay annotations -> JPEG -> zip) is rebuilt with PyMuPDF
(rendering) + Pillow (drawing), against the simplified AnnotationObject schema in
app.models -- see that file's docstring for why it isn't LEADTOOLS-.ann-compatible.
"""
import io
import json
import zipfile
from typing import Dict, List

import fitz  # PyMuPDF
from PIL import Image, ImageDraw

from app.models import AnnotationObject
from app.services.errors import ConversionError
from app.services.any_to_pdf import to_pdf_bytes

RENDER_ZOOM = 2.0  # ~144 DPI, matches typical LEADTOOLS demo preview quality
PAGE_FILENAME_TEMPLATE = "output_Page({page}).jpeg"
ANNOTATIONS_FILENAME = "annotations.json"


def _ensure_pdf_bytes(source_bytes: bytes, source_filename: str) -> bytes:
    return to_pdf_bytes(source_bytes, source_filename)


def _draw_annotations(image: Image.Image, annotations: List[AnnotationObject], zoom: float) -> None:
    draw = ImageDraw.Draw(image)
    for ann in annotations:
        x0, y0 = ann.x * zoom, ann.y * zoom
        if ann.type == "rect":
            x1, y1 = x0 + ann.width * zoom, y0 + ann.height * zoom
            draw.rectangle([x0, y0, x1, y1], outline=ann.color, width=3)
        elif ann.type == "text" and ann.text:
            draw.text((x0, y0), ann.text, fill=ann.color)


def embed_and_convert(
    source_bytes: bytes,
    source_filename: str,
    annotations: List[AnnotationObject],
    rotation_map: Dict[int, int],
) -> bytes:
    """Returns a zip archive: one JPEG per page (rotated + annotated) plus
    annotations.json, matching the shape of the original .zip response."""
    try:
        pdf_bytes = _ensure_pdf_bytes(source_bytes, source_filename)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except ConversionError:
        raise
    except Exception as exc:  # malformed/unsupported input document
        raise ConversionError("Images/Zip can not be generated", cause=exc) from exc

    annotations_by_page: Dict[int, List[AnnotationObject]] = {}
    for ann in annotations:
        annotations_by_page.setdefault(ann.page, []).append(ann)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for index in range(doc.page_count):
            page_number = index + 1
            page = doc[index]
            rotation = rotation_map.get(page_number, 0)
            if rotation:
                page.set_rotation(rotation)

            pix = page.get_pixmap(matrix=fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM))
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            _draw_annotations(image, annotations_by_page.get(page_number, []), RENDER_ZOOM)

            jpeg_buffer = io.BytesIO()
            image.save(jpeg_buffer, format="JPEG", quality=90)
            zf.writestr(PAGE_FILENAME_TEMPLATE.format(page=page_number), jpeg_buffer.getvalue())

        zf.writestr(
            ANNOTATIONS_FILENAME,
            json.dumps([a.model_dump() for a in annotations], indent=2),
        )

    doc.close()
    return zip_buffer.getvalue()
