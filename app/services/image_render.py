"""Renders a document page to a raster image. Ports the raster half of
Page.GetImage / Page.GetThumbnail (LEADTOOLS DocumentPage.getImage /
getThumbnailImage + ImageResizer + ImageSaver) using PyMuPDF + Pillow."""
import io
from pathlib import Path
from typing import Tuple

import fitz  # PyMuPDF
from PIL import Image

from app.services.errors import ConversionError

DEFAULT_RESOLUTION_ZOOM = 96 / 72.0
DEFAULT_THUMBNAIL_SIZE = (150, 200)

_MIME_TO_PIL_FORMAT = {
    "image/jpeg": "JPEG",
    "image/jpg": "JPEG",
    "image/png": "PNG",
    "image/bmp": "BMP",
    "image/gif": "GIF",
    "image/tiff": "TIFF",
}


def render_page_image(pdf_path: Path, page_number: int, resolution: int = 0, width: int = 0,
                       height: int = 0, bits_per_pixel: int = 0) -> Image.Image:
    zoom = (resolution / 72.0) if resolution and resolution > 0 else DEFAULT_RESOLUTION_ZOOM
    doc = fitz.open(str(pdf_path))
    try:
        if page_number < 1 or page_number > doc.page_count:
            raise ConversionError(f"'pageNumber' is out of range for this document (1-{doc.page_count})",
                                   status_code=400)
        page = doc[page_number - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    finally:
        doc.close()

    # Mirrors ImageResizer.resizeImage: only resize when both dimensions are given.
    if width > 0 and height > 0:
        image.thumbnail((width, height), Image.LANCZOS)

    if bits_per_pixel == 1:
        image = image.convert("1")
    elif bits_per_pixel == 8:
        image = image.convert("L")

    return image


def encode_image(image: Image.Image, mime_type: str, quality_factor: int = 0) -> Tuple[bytes, str]:
    mime_type = (mime_type or "image/jpeg").lower()
    fmt = _MIME_TO_PIL_FORMAT.get(mime_type, "JPEG")
    if fmt == "JPEG" and image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    buffer = io.BytesIO()
    save_kwargs = {"quality": quality_factor} if fmt == "JPEG" and quality_factor else {}
    image.save(buffer, format=fmt, **save_kwargs)
    return buffer.getvalue(), mime_type
