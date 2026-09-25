"""
Raster image -> PDF conversion (PNG, JPEG, TIFF incl. multi-page, BMP, GIF,
WEBP, ...), used whenever an uploaded document is an image rather than a PDF
or an office file.

LEADTOOLS' DocumentFactory loads raster formats natively through its codecs.
Handing them to LibreOffice instead doesn't work: without the Draw component
it can't import images at all, and even with it a multi-page TIFF came out
with the wrong page count. So images get their own path here: Pillow decodes
(it covers far more formats and TIFF variants than MuPDF) and PyMuPDF builds
the PDF, one page per image frame, sized from the image's DPI so a 300 DPI
letter scan becomes a letter-size page.

The resulting pages are image-only -- no text layer (this port has no OCR),
so text search and NER find nothing on them until OCR is added.
"""
import io
from typing import Optional

import fitz  # PyMuPDF
from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError

from app.services.errors import ConversionError

DEFAULT_DPI = 96  # used when the image carries no (or an implausible) DPI
MAX_PAGES = 500
# Cameras stamp a meaningless 72 DPI, which would make a 4032 px phone photo a
# 56-inch page. Pages whose longer side exceeds this are scaled down to fit a
# letter page (same orientation); real scans at their true DPI are untouched.
MAX_PAGE_SIDE_IN = 17.0
LETTER_IN = (8.5, 11.0)

# Formats where every frame is a document page. For animated GIF/WEBP/APNG the
# extra frames are animation, not pages, so only the first frame is kept.
_MULTI_PAGE_FORMATS = {"TIFF", "MPO"}
_PDF_SAFE_MODES = {"1", "L", "RGB"}


def _page_size_points(image: Image.Image) -> tuple:
    dpi = image.info.get("dpi") or (DEFAULT_DPI, DEFAULT_DPI)
    try:
        xdpi, ydpi = (float(dpi[0]), float(dpi[1]))
    except (TypeError, ValueError, IndexError):
        xdpi = ydpi = DEFAULT_DPI
    xdpi = xdpi if 30 <= xdpi <= 2400 else DEFAULT_DPI
    ydpi = ydpi if 30 <= ydpi <= 2400 else DEFAULT_DPI
    width, height = image.width * 72.0 / xdpi, image.height * 72.0 / ydpi
    if max(width, height) > MAX_PAGE_SIDE_IN * 72:
        short_in, long_in = LETTER_IN
        box_w, box_h = (long_in, short_in) if width > height else (short_in, long_in)
        scale = min(box_w * 72 / width, box_h * 72 / height)
        width, height = width * scale, height * scale
    return width, height


def _normalize_mode(frame: Image.Image) -> Image.Image:
    """PDF image XObjects need gray, RGB (or 1-bit); flatten alpha onto white
    and convert CMYK / palette / 16-bit / float modes."""
    if frame.mode in _PDF_SAFE_MODES:
        return frame
    if frame.mode in ("RGBA", "LA", "PA") or (frame.mode == "P" and "transparency" in frame.info):
        rgba = frame.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    if frame.mode.startswith("I;16"):
        return frame.convert("I").point(lambda v: v / 256).convert("L")
    if frame.mode in ("I", "F"):
        return frame.convert("L")
    return frame.convert("RGB")


def image_bytes_to_pdf(data: bytes, filename: Optional[str] = None) -> bytes:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Image.DecompressionBombError as exc:
        raise ConversionError(f"Image is too large to convert: {filename or 'upload'}", status_code=413) from exc
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ConversionError(f"PDF can not be generated: unreadable or unsupported image file {filename or ''}".strip(),
                              status_code=422) from exc

    frames = ImageSequence.Iterator(image) if image.format in _MULTI_PAGE_FORMATS else [image]
    # The original JPEG bytes can be embedded untouched only if no EXIF rotation
    # applies (a 180-degree one keeps the same size, so compare the tag, not sizes).
    jpeg_passthrough = image.format == "JPEG" and image.mode in ("L", "RGB") and image.getexif().get(0x0112, 1) == 1
    pdf = fitz.open()
    try:
        for index, frame in enumerate(frames):
            if index >= MAX_PAGES:
                raise ConversionError(f"Image has more than {MAX_PAGES} pages", status_code=413)
            page_image = ImageOps.exif_transpose(frame.copy())  # phone photos: honour the EXIF rotation
            page_image.info.setdefault("dpi", frame.info.get("dpi") or image.info.get("dpi"))
            width, height = _page_size_points(page_image)
            page = pdf.new_page(width=width, height=height)

            buffer = io.BytesIO()
            if jpeg_passthrough:
                buffer.write(data)  # embed the original JPEG as-is: no recompression loss
            else:
                _normalize_mode(page_image).save(buffer, format="PNG")
            page.insert_image(page.rect, stream=buffer.getvalue())
        return pdf.tobytes(garbage=3, deflate=True)
    finally:
        pdf.close()
