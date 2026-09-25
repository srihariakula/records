import io
import subprocess

import fitz
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services import any_to_pdf, image_convert, office_convert
from app.services.cache_store import cache
from app.services.errors import ConversionError

client = TestClient(app)


def _image_bytes(fmt, size=(850, 1100), mode="RGB", **save_kwargs):
    buf = io.BytesIO()
    Image.new(mode, size, "white" if mode in ("RGB", "RGBA", "CMYK") else 255).save(buf, format=fmt, **save_kwargs)
    return buf.getvalue()


def _pdf_pages(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return [(round(p.rect.width / 72, 2), round(p.rect.height / 72, 2)) for p in doc]
    finally:
        doc.close()


@pytest.mark.parametrize("fmt, mime", [
    ("PNG", "image/png"), ("JPEG", "image/jpeg"), ("TIFF", "image/tiff"),
    ("GIF", "image/gif"), ("BMP", "image/bmp"), ("WEBP", "image/webp"),
])
def test_sniff_mime_recognises_images_by_content(fmt, mime):
    assert any_to_pdf.sniff_mime(_image_bytes(fmt, size=(10, 10))[:16]) == mime


def test_detect_mime_prefers_content_over_misleading_name_and_generic_declared_type():
    png = _image_bytes("PNG", size=(10, 10))
    assert any_to_pdf.detect_mime_type(png[:16], "scan.pdf", "application/octet-stream") == "image/png"
    assert any_to_pdf.detect_mime_type(b"%PDF-1.7\n", None, None) == "application/pdf"
    assert any_to_pdf.detect_mime_type(b"hello", "notes.txt", "application/octet-stream") == "text/plain"
    assert any_to_pdf.detect_mime_type(b"hello", "noext", None) == "application/octet-stream"


def test_multi_page_tiff_becomes_one_pdf_page_per_frame():
    frames = [Image.new("L", (850, 1100), shade) for shade in (255, 200, 150)]
    buf = io.BytesIO()
    frames[0].save(buf, format="TIFF", save_all=True, append_images=frames[1:])
    assert len(_pdf_pages(image_convert.image_bytes_to_pdf(buf.getvalue()))) == 3


def test_image_dpi_sets_page_size():
    scan = _image_bytes("JPEG", size=(2550, 3300), dpi=(300, 300))
    assert _pdf_pages(any_to_pdf.to_pdf_bytes(scan, "scan.jpg")) == [(8.5, 11.0)]


def test_camera_photo_with_72_dpi_is_scaled_to_letter_not_a_56_inch_page():
    photo = _image_bytes("JPEG", size=(4032, 3024), dpi=(72, 72))
    assert _pdf_pages(any_to_pdf.to_pdf_bytes(photo, "IMG_0001.jpg")) == [(11.0, 8.25)]


def test_exif_orientation_is_applied():
    img = Image.new("RGB", (1100, 850), "white")  # stored landscape...
    exif = img.getexif()
    exif[0x0112] = 6  # ...but displayed rotated 90 degrees -> portrait
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif, dpi=(100, 100))
    [(w, h)] = _pdf_pages(any_to_pdf.to_pdf_bytes(buf.getvalue(), "photo.jpg"))
    assert h > w


@pytest.mark.parametrize("mode, fmt", [("RGBA", "PNG"), ("CMYK", "JPEG"), ("I;16", "TIFF"), ("1", "TIFF"), ("P", "GIF")])
def test_unusual_colour_modes_convert(mode, fmt):
    assert len(_pdf_pages(any_to_pdf.to_pdf_bytes(_image_bytes(fmt, size=(200, 300), mode=mode), f"x.{fmt.lower()}"))) == 1


def test_pdf_passes_through_untouched():
    doc = fitz.open()
    doc.new_page()
    data = doc.tobytes()
    assert any_to_pdf.to_pdf_bytes(data, "a.pdf") is data


def test_unreadable_image_is_a_clear_422():
    with pytest.raises(ConversionError) as exc:
        any_to_pdf.to_pdf_bytes(b"\x89PNG\r\n\x1a\n" + b"truncated", "broken.png")
    assert exc.value.status_code == 422


def test_unknown_binary_is_refused_instead_of_imported_as_garbage_text():
    with pytest.raises(ConversionError) as exc:
        any_to_pdf.to_pdf_bytes(bytes(range(256)) * 4, "blob.bin")
    assert exc.value.status_code == 415


def test_libreoffice_failure_names_missing_component_and_drops_javaldx_noise():
    result = subprocess.CompletedProcess(
        args=[], returncode=0, stdout=b"",
        stderr=b"Warning: failed to launch javaldx - java may not function correctly\nError: source file could not be loaded\n")
    reason = office_convert._failure_reason(result, ".xlsx")
    assert "libreoffice-calc" in reason and "javaldx" not in reason


def _upload(name, data):
    uri = client.post("/Factory/BeginUpload", json={"name": name}).json()["upload_uri"]
    client.post("/Factory/UploadDocumentBlob", data={"uri": uri}, files={"file": (name, data)})
    return client.post("/Factory/EndUpload", json={"uri": uri}).json()


def test_viewer_upload_flow_converts_an_image():
    doc = _upload("scan.png", _image_bytes("PNG"))
    try:
        assert doc["mime_type"] == "image/png"
        assert doc["page_count"] == 1
        assert doc["conversion_error"] is None
        resp = client.get("/Page/GetImage", params={"documentId": doc["document_id"], "pageNumber": 1})
        assert resp.status_code == 200
    finally:
        cache.delete(doc["document_id"], allow_missing=True)


def test_viewer_upload_flow_reports_why_a_file_could_not_be_converted():
    doc = _upload("damaged.pdf", b"%PDF-1.4\n not really a pdf")
    try:
        assert doc["page_count"] == 0
        assert "damaged" in doc["conversion_error"]
    finally:
        cache.delete(doc["document_id"], allow_missing=True)
