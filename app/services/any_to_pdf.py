"""
Single entry point for "turn whatever was uploaded into a PDF", shared by the
viewer's upload flow (app.services.document_session), /convert/to-pdf and
/convert/embed-and-convert, so they all accept the same formats:

  - PDF          -> passed through untouched
  - raster image -> app.services.image_convert (Pillow + PyMuPDF)
  - anything else (docx, xlsx, pptx, odt, rtf, txt, html, csv, ...)
                 -> app.services.office_convert (headless LibreOffice)

Type detection sniffs the file's magic bytes first, because the viewer sends
only a file name (no MIME type), names can be wrong or missing an extension,
and browsers often declare application/octet-stream.
"""
import mimetypes
from typing import Optional

from app.services.errors import ConversionError
from app.services.image_convert import image_bytes_to_pdf
from app.services.office_convert import convert_bytes_to_pdf

PDF_MIME = "application/pdf"
_GENERIC_MIMES = {None, "", "application/octet-stream", "binary/octet-stream"}

# (magic prefix, mime) -- checked in order against the first bytes of the file.
_MAGIC = [
    (b"%PDF", PDF_MIME),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"II*\x00", "image/tiff"),
    (b"MM\x00*", "image/tiff"),
    (b"II+\x00", "image/tiff"),  # BigTIFF
    (b"MM\x00+", "image/tiff"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"BM", "image/bmp"),
]


def sniff_mime(head: bytes) -> Optional[str]:
    for magic, mime in _MAGIC:
        if head.startswith(magic):
            return mime
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def detect_mime_type(head: bytes, filename: Optional[str] = None, declared: Optional[str] = None) -> str:
    """Content first (PDF / images are unambiguous by magic bytes), then the
    caller's declared type, then the file extension."""
    sniffed = sniff_mime(head)
    if sniffed:
        return sniffed
    if declared not in _GENERIC_MIMES:
        return declared
    guessed, _ = mimetypes.guess_type(filename or "")
    return guessed or "application/octet-stream"


def is_image_mime(mime: Optional[str]) -> bool:
    # SVG is vector markup Pillow can't decode -- leave it to LibreOffice.
    return bool(mime) and mime.startswith("image/") and mime != "image/svg+xml"


def _looks_like_unknown_binary(data: bytes, mime: Optional[str]) -> bool:
    """LibreOffice "converts" any byte soup by importing it as text, producing
    pages of garbage. Refuse binary content whose type we couldn't identify --
    except ZIP/OLE containers (extension-less docx/xlsx/pptx/doc/xls), which
    LibreOffice recognises by content."""
    if mime not in _GENERIC_MIMES:
        return False
    if data[:4] == b"PK\x03\x04" or data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return False
    return b"\x00" in data[:4096]


def to_pdf_bytes(data: bytes, filename: Optional[str] = None, mime_type: Optional[str] = None) -> bytes:
    mime = mime_type or detect_mime_type(data[:16], filename)
    if mime == PDF_MIME:
        return data
    if is_image_mime(mime):
        return image_bytes_to_pdf(data, filename)
    if _looks_like_unknown_binary(data, mime):
        raise ConversionError(
            f"PDF can not be generated: unsupported file type ({filename or 'upload'} is not a recognised "
            "document or image format)", status_code=415)
    return convert_bytes_to_pdf(data, filename or "document")
