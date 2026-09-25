import io

import fitz
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services import any_to_pdf, cache_store, document_session, ocr
from app.services.cache_store import cache

client = TestClient(app)

needs_tesseract = pytest.mark.skipif(not ocr.is_available(), reason="tesseract not installed (apt-get install tesseract-ocr)")

LINES = ["HEMOGLOBIN A1C 7.6 H", "Patient: Nguyen, Thomas", "Visit Date: 09/30/2024"]


def _scan_png(dpi=200, lines=LINES):
    """A 'scanned' letter page: text drawn by PyMuPDF, then flattened to pixels."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    for i, line in enumerate(lines):
        page.insert_text((72, 100 + 40 * i), line, fontsize=18)
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
    img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(dpi, dpi))
    return buf.getvalue()


def _image_only_pdf(png, stamp=None):
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(page.rect, stream=png)
    if stamp:
        page.insert_text((20, 12), stamp, fontsize=7)
    return doc.tobytes()


def test_page_needs_ocr_rules():
    doc = fitz.open()
    text_page = doc.new_page()
    text_page.insert_text((72, 72), "real text layer " * 20)
    scan = doc.new_page(width=612, height=792)
    scan.insert_image(scan.rect, stream=_scan_png())
    logo_only = doc.new_page(width=612, height=792)
    logo_only.insert_image(fitz.Rect(0, 0, 60, 60), stream=_scan_png())
    stamped_scan = doc.new_page(width=612, height=792)
    stamped_scan.insert_image(stamped_scan.rect, stream=_scan_png())
    stamped_scan.insert_text((20, 12), "FAX FROM 555-0100 P.1/2", fontsize=7)
    assert [ocr.page_needs_ocr(p) for p in doc] == [False, True, False, True]


def test_ocr_off_leaves_pdf_untouched(monkeypatch):
    monkeypatch.setattr(ocr, "OCR_MODE", "off")
    pdf = _image_only_pdf(_scan_png())
    result = ocr.add_text_layer(pdf)
    assert result.pdf_bytes is pdf and result.ocr_pages == 0


@needs_tesseract
def test_scanned_image_becomes_searchable():
    result = any_to_pdf.convert(_scan_png(), "scan.png")
    assert result.ocr_pages == 1
    page = fitz.open(stream=result.pdf_bytes, filetype="pdf")[0]
    text = page.get_text()
    for word in ("HEMOGLOBIN", "A1C", "Nguyen", "09/30/2024"):
        assert word in text
    # The invisible text sits over the pixels: the word box is where it was drawn.
    [hit] = page.search_for("HEMOGLOBIN")
    assert abs(hit.x0 - 72) < 6 and 80 < hit.y1 < 110


@needs_tesseract
def test_blank_scan_is_not_counted_as_ocrd():
    blank = io.BytesIO()
    Image.new("L", (1700, 2200), 255).save(blank, format="PNG", dpi=(200, 200))
    assert any_to_pdf.convert(blank.getvalue(), "blank.png").ocr_pages == 0


@needs_tesseract
def test_rotated_scanned_pdf_text_lands_where_displayed():
    # How scanners really do it: pixels stored sideways, /Rotate 90 makes the
    # page display upright. The text layer must line up with the *displayed* page.
    sideways = Image.open(io.BytesIO(_scan_png())).rotate(90, expand=True)
    buf = io.BytesIO()
    sideways.save(buf, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=792, height=612)
    page.insert_image(page.rect, stream=buf.getvalue())
    page.set_rotation(90)

    result = ocr.add_text_layer(doc.tobytes())
    assert result.ocr_pages == 1
    page = fitz.open(stream=result.pdf_bytes, filetype="pdf")[0]
    [hit] = page.search_for("HEMOGLOBIN")
    assert page.rect.width < page.rect.height  # displayed portrait
    assert abs(hit.x0 - 72) < 6 and 80 < hit.y1 < 110  # same spot as the unrotated scan


@needs_tesseract
def test_fax_stamped_scan_still_gets_ocr():
    result = ocr.add_text_layer(_image_only_pdf(_scan_png(), stamp="FAX FROM 555-0100 P.1/2"))
    assert result.ocr_pages == 1
    assert "Nguyen" in fitz.open(stream=result.pdf_bytes, filetype="pdf")[0].get_text()


def test_text_pdf_is_served_as_is_and_checked_only_once(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_store, "CACHE_ROOT", tmp_path / "cache")
    (tmp_path / "cache").mkdir()
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "already has a text layer " * 10)
    try:
        entry = cache.put_bytes("ocr-passthrough", doc.tobytes(), name="text.pdf")
        assert entry.ocr_pages == 0
        assert document_session.get_pdf_path(entry) == entry.file_path  # no rendered copy
        assert (entry.file_path.parent / document_session.NO_RENDER_MARKER).exists()
    finally:
        cache._entries.pop("ocr-passthrough", None)


@needs_tesseract
def test_upload_flow_reports_ocr_and_search_finds_scanned_text():
    uri = client.post("/Factory/BeginUpload", json={"name": "scan.png"}).json()["upload_uri"]
    client.post("/Factory/UploadDocumentBlob", data={"uri": uri}, files={"file": ("scan.png", _scan_png())})
    doc = client.post("/Factory/EndUpload", json={"uri": uri}).json()
    try:
        assert doc["ocr_pages"] == 1
        resp = client.post("/Factory/SearchMultiCriteria", json={"document_id": doc["document_id"], "query": "Nguyen"})
        assert list(resp.json()["matches"].keys()) == ["1"]
        text = client.post("/Page/GetText", json={"document_id": doc["document_id"], "page_number": 1}).json()["text"]
        assert "HEMOGLOBIN" in text
    finally:
        cache.delete(doc["document_id"], allow_missing=True)
