import io

import fitz
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services import qr_code

client = TestClient(app)


def test_generate_returns_a_decodable_png():
    resp = client.post("/qrcode/generate", json={"qrcode": "hello from a test"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert "qrcode_" in resp.headers["content-disposition"]

    # Round-trip: decode what we just generated.
    detected = qr_code.detect_qr_codes_by_page(resp.content, "generated.png")
    assert detected == {1: ["hello from a test"]}


def test_generate_requires_nonempty_code():
    resp = client.post("/qrcode/generate", json={"qrcode": ""})
    assert resp.status_code == 400


def test_detect_via_http_on_a_pdf_page():
    qr_png = qr_code.generate_qr_png("page two payload")

    doc = fitz.open()
    doc.new_page(width=300, height=300)  # page 1: no QR code
    page2 = doc.new_page(width=300, height=300)
    page2.insert_image(fitz.Rect(50, 50, 200, 200), stream=qr_png)
    pdf_bytes = doc.tobytes()
    doc.close()

    resp = client.post("/qrcode/detect", files={"file": ("two_pages.pdf", pdf_bytes, "application/pdf")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["pagewise_qr_codes"] == {"2": ["page two payload"]}


def test_detect_returns_empty_map_when_no_qr_present():
    doc = fitz.open()
    doc.new_page(width=200, height=200)
    pdf_bytes = doc.tobytes()
    doc.close()

    resp = client.post("/qrcode/detect", files={"file": ("blank.pdf", pdf_bytes, "application/pdf")})
    assert resp.json()["pagewise_qr_codes"] == {}
