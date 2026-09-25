"""
QR code generation and page-wise detection.

Ports QRCodeHelper.generateQRCode (LEADTOOLS BarcodeEngine writer) and
QRCodeHelper.detectAllQRCode (LEADTOOLS BarcodeEngine reader over a rasterized
PDF) using the `qrcode` library for writing and OpenCV's built-in QR detector
for reading.

Why OpenCV instead of pyzbar/zbar: pyzbar dlopens the native `zbar` library,
which isn't on PyPI as a wheel for macOS -- it needs `brew install zbar` as a
separate system dependency (the same category as the LibreOffice dependency
`convert` already has). OpenCV's QR detector ships inside the `opencv-python-
headless` wheel with no extra system install, and this endpoint only ever
needs to read QR codes (not the general multi-symbology barcode reading that
Page.ReadBarcodes does) -- so it's a purpose-built fit. Trade-off: OpenCV's
detector is less robust than zbar against heavy rotation/damage/low contrast.
"""
import tempfile
import time
from pathlib import Path
from typing import Dict, List

import cv2
import fitz  # PyMuPDF
import numpy as np
import qrcode

from app.services import document_session
from app.services.errors import ConversionError

QR_DETECTION_DPI = 300  # LEADTOOLS' helper uses 600; 300 balances speed/accuracy for a PoC

_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/bmp", "image/tiff", "image/gif"}


def generate_qr_png(data: str) -> bytes:
    if not data:
        raise ConversionError("'qrcode' is required", status_code=400)
    image = qrcode.make(data)
    buffer = tempfile.SpooledTemporaryFile()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.read()


def generate_qr_filename() -> str:
    return f"qrcode_{int(time.time() * 1000)}.png"


def _pixmap_to_bgr(pix: "fitz.Pixmap") -> "np.ndarray":
    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        return cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
    if pix.n == 3:
        return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)


_MAX_CODES_PER_IMAGE = 16


def _decode(detector: "cv2.QRCodeDetector", image) -> List[str]:
    """OpenCV's QR detector has two APIs with complementary blind spots:
    detectAndDecodeMulti is built for several codes in one image but has been
    observed to miss an isolated code depending on its version/module count;
    detectAndDecode (single) reliably finds an isolated code but gives up when
    more than one is in frame. Neither alone is robust enough, so this runs
    both and unions the results -- multi first, then iterative single-detect
    with the found region masked out so the next call can find another."""
    found = set()

    ok, decoded_info, _points, _ = detector.detectAndDecodeMulti(image)
    if ok:
        found.update(value for value in decoded_info if value)

    work = image.copy()
    for _ in range(_MAX_CODES_PER_IMAGE):
        value, points, _ = detector.detectAndDecode(work)
        if not value or points is None:
            break
        found.add(value)
        cv2.fillPoly(work, [points[0].astype(int)], (255, 255, 255))

    return sorted(found)


def detect_qr_codes_by_page(file_bytes: bytes, filename: str) -> Dict[int, List[str]]:
    """Returns {page_number (1-based): [unique decoded values]}, only for pages
    where at least one QR code was found (pages with none are omitted, same as
    the original Java map which is only populated on a hit)."""
    detector = cv2.QRCodeDetector()

    with tempfile.TemporaryDirectory() as tmp_dir:
        input_path = Path(tmp_dir) / (Path(filename).name or "input")
        input_path.write_bytes(file_bytes)
        mime_type = document_session.detect_mime_type(input_path, None)

        if mime_type in _IMAGE_MIME_TYPES:
            image = cv2.imread(str(input_path))
            if image is None:
                raise ConversionError("Could not read image for QR detection", status_code=422)
            values = _decode(detector, image)
            return {1: values} if values else {}

        pdf_path = document_session.get_pdf_path_for(input_path, mime_type)
        doc = fitz.open(str(pdf_path))
        try:
            results: Dict[int, List[str]] = {}
            zoom = QR_DETECTION_DPI / 72.0
            for index in range(doc.page_count):
                page = doc[index]
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
                values = _decode(detector, _pixmap_to_bgr(pix))
                if values:
                    results[index + 1] = values
            return results
        finally:
            doc.close()
