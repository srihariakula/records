import base64
import io

import fitz
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.cache_store import cache

client = TestClient(app)


def _make_pdf_bytes(page_count: int = 3) -> bytes:
    doc = fitz.open()
    for _ in range(page_count):
        doc.new_page(width=200, height=300)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def uploaded_document_id():
    pdf_bytes = _make_pdf_bytes(page_count=3)
    entry = cache.put_bytes(None, pdf_bytes, name="test.pdf", mime_type="application/pdf")
    yield entry.document_id
    cache.delete(entry.document_id, allow_missing=True)


def test_chunked_upload_round_trip():
    pdf_bytes = _make_pdf_bytes(page_count=2)
    begin = client.post("/Factory/BeginUpload", json={}).json()
    upload_uri = begin["upload_uri"]

    # Upload in two chunks to exercise append behavior.
    mid = len(pdf_bytes) // 2
    for chunk in (pdf_bytes[:mid], pdf_bytes[mid:]):
        encoded = base64.b64encode(chunk).decode()
        resp = client.post("/Factory/UploadDocument", json={"uri": upload_uri, "data": encoded})
        assert resp.status_code == 200

    end = client.post("/Factory/EndUpload", json={"uri": upload_uri})
    assert end.status_code == 200, end.text
    body = end.json()
    assert body["mime_type"] == "application/pdf"
    assert body["page_count"] == 2

    load = client.post("/Factory/LoadFromCache", json={"document_id": body["document_id"]})
    assert load.json()["document"]["page_count"] == 2


def test_load_from_cache_missing_returns_null_document():
    resp = client.post("/Factory/LoadFromCache", json={"document_id": "does-not-exist"})
    assert resp.status_code == 200
    assert resp.json()["document"] is None


def test_document_id_path_traversal_is_rejected():
    resp = client.post("/Factory/LoadFromCache", json={"document_id": "../../etc/passwd"})
    assert resp.status_code == 400


def test_delete_missing_document_without_allow_flag_is_404():
    resp = client.post("/Factory/Delete", json={"document_id": "nope", "allow_non_existing": False})
    assert resp.status_code == 404


def test_clone_and_delete_source(uploaded_document_id):
    resp = client.post("/Factory/CloneDocument", json={
        "document_id": uploaded_document_id, "delete_source_document": True,
    })
    assert resp.status_code == 200, resp.text
    clone_id = resp.json()["document"]["document_id"]
    assert clone_id != uploaded_document_id

    assert client.post("/Factory/LoadFromCache", json={"document_id": uploaded_document_id}).json()["document"] is None
    assert client.post("/Factory/LoadFromCache", json={"document_id": clone_id}).json()["document"] is not None
    cache.delete(clone_id, allow_missing=True)


def test_get_image_returns_jpeg(uploaded_document_id):
    resp = client.get("/Page/GetImage", params={"documentId": uploaded_document_id, "pageNumber": 1})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.content[:2] == b"\xff\xd8"  # JPEG magic bytes


def test_get_image_out_of_range_page_is_400(uploaded_document_id):
    resp = client.get("/Page/GetImage", params={"documentId": uploaded_document_id, "pageNumber": 99})
    assert resp.status_code == 400


def test_get_thumbnail_defaults_to_configured_size(uploaded_document_id):
    resp = client.get("/Page/GetThumbnail", params={"documentId": uploaded_document_id})
    assert resp.status_code == 200
    from PIL import Image
    image = Image.open(io.BytesIO(resp.content))
    assert image.width <= 150 and image.height <= 200


def test_set_and_get_annotations_round_trip(uploaded_document_id):
    annotations = [{"page": 1, "type": "rect", "x": 1, "y": 2, "width": 3, "height": 4}]
    set_resp = client.post("/Page/SetAnnotations", json={
        "document_id": uploaded_document_id, "page_number": 1, "annotations": annotations,
    })
    assert set_resp.status_code == 200

    get_resp = client.post("/Page/GetAnnotations", json={"document_id": uploaded_document_id, "page_number": 1})
    assert get_resp.json()["annotations"][0]["type"] == "rect"

    get_all = client.post("/Page/GetAnnotations", json={"document_id": uploaded_document_id, "page_number": 0})
    assert len(get_all.json()["annotations"]) == 1


def test_get_text_extracts_embedded_text():
    doc = fitz.open()
    page = doc.new_page(width=300, height=300)
    page.insert_text((50, 50), "hello world")
    pdf_bytes = doc.tobytes()
    doc.close()

    entry = cache.put_bytes(None, pdf_bytes, name="text.pdf", mime_type="application/pdf")
    try:
        resp = client.post("/Page/GetText", json={"document_id": entry.document_id, "page_number": 1})
        assert "hello world" in resp.json()["text"]
    finally:
        cache.delete(entry.document_id, allow_missing=True)


def test_cache_statistics_requires_passcode_when_configured(monkeypatch):
    import app.services.cache_store as cache_store_module

    monkeypatch.setattr(cache_store_module, "ACCESS_PASSCODE", "secret")
    resp = client.get("/Factory/GetCacheStatistics", params={"passcode": "wrong"})
    assert resp.status_code == 401

    resp_ok = client.get("/Factory/GetCacheStatistics", params={"passcode": "secret"})
    assert resp_ok.status_code == 200


def test_download_annotated_document_burns_annotations_into_real_pdf_annots(uploaded_document_id):
    annotations = [
        {"page": 1, "type": "rect", "x": 10, "y": 20, "width": 30, "height": 40, "color": "#00FF00", "text": "box"},
        {"page": 1, "type": "text", "x": 5, "y": 5, "width": 100, "height": 20, "text": "hello"},
    ]
    set_resp = client.post("/Page/SetAnnotations", json={
        "document_id": uploaded_document_id, "page_number": 1, "annotations": annotations,
    })
    assert set_resp.status_code == 200

    resp = client.get("/Factory/DownloadAnnotatedDocument", params={"documentId": uploaded_document_id})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "_annotated.pdf" in resp.headers["content-disposition"]

    doc = fitz.open(stream=resp.content, filetype="pdf")
    try:
        page1 = doc[0]  # keep a live reference -- annots become unbound if the Page wrapper is GC'd
        page_annots = list(page1.annots())
        assert len(page_annots) == 2
        kinds = sorted(a.type[1] for a in page_annots)
        assert kinds == ["FreeText", "Square"]
        # page 2 had no annotations set -- should have none
        page2 = doc[1]
        assert list(page2.annots()) == []
    finally:
        doc.close()


def test_download_annotated_document_with_no_annotations_still_returns_valid_pdf(uploaded_document_id):
    resp = client.get("/Factory/DownloadAnnotatedDocument", params={"documentId": uploaded_document_id})
    assert resp.status_code == 200
    doc = fitz.open(stream=resp.content, filetype="pdf")
    try:
        assert doc.page_count == 3
    finally:
        doc.close()


@pytest.fixture
def document_with_text():
    doc = fitz.open()
    page = doc.new_page(width=300, height=300)
    page.insert_text((50, 50), "Applicant Name: John Doe")
    page.insert_text((50, 80), "SSN: 078-05-1120")
    pdf_bytes = doc.tobytes()
    doc.close()

    entry = cache.put_bytes(None, pdf_bytes, name="field_test.pdf", mime_type="application/pdf")
    yield entry.document_id
    cache.delete(entry.document_id, allow_missing=True)


def test_extract_annotated_fields_resolves_label_to_underlying_text(document_with_text):
    # PyMuPDF text coordinates: insert_text's y is the baseline, so a box a
    # little above and around each line captures its text via get_textbox.
    annotations = [
        {"page": 1, "type": "rect", "x": 45, "y": 40, "width": 220, "height": 15, "text": "name_field"},
        {"page": 1, "type": "rect", "x": 45, "y": 70, "width": 150, "height": 15, "text": "ssn_field"},
        {"page": 1, "type": "rect", "x": 200, "y": 200, "width": 50, "height": 20, "text": ""},  # unlabeled
    ]
    set_resp = client.post("/Page/SetAnnotations", json={
        "document_id": document_with_text, "page_number": 1, "annotations": annotations,
    })
    assert set_resp.status_code == 200

    resp = client.get("/Factory/ExtractAnnotatedFields", params={"documentId": document_with_text})
    assert resp.status_code == 200
    body = resp.json()

    assert len(body["fields"]) == 2  # unlabeled annotation excluded
    assert set(body["key_values"].keys()) == {"name_field", "ssn_field"}
    assert "John Doe" in body["key_values"]["name_field"]
    assert "078-05-1120" in body["key_values"]["ssn_field"]


def test_search_document_finds_matches_with_bounding_boxes(document_with_text):
    resp = client.get("/Factory/SearchDocument", params={"documentId": document_with_text, "query": "John Doe"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_matches"] == 1
    assert "1" in body["matches"]
    rect = body["matches"]["1"][0]
    assert len(rect) == 4


def test_search_document_no_match_returns_empty():
    doc = fitz.open()
    doc.new_page(width=100, height=100)
    pdf_bytes = doc.tobytes()
    doc.close()
    entry = cache.put_bytes(None, pdf_bytes, name="empty.pdf", mime_type="application/pdf")
    try:
        resp = client.get("/Factory/SearchDocument", params={"documentId": entry.document_id, "query": "nothing"})
        assert resp.json() == {"matches": {}, "total_matches": 0}
    finally:
        cache.delete(entry.document_id, allow_missing=True)


def test_extract_annotated_fields_includes_index_for_editing(document_with_text):
    annotations = [
        {"page": 1, "type": "rect", "x": 45, "y": 40, "width": 220, "height": 15, "text": ""},  # unlabeled, index 0
        {"page": 1, "type": "rect", "x": 45, "y": 70, "width": 150, "height": 15, "text": "ssn_field"},  # index 1
    ]
    client.post("/Page/SetAnnotations", json={
        "document_id": document_with_text, "page_number": 1, "annotations": annotations,
    })

    resp = client.get("/Factory/ExtractAnnotatedFields", params={"documentId": document_with_text})
    fields = resp.json()["fields"]
    assert len(fields) == 1
    assert fields[0]["index"] == 1  # position within the full per-page list, not the filtered list
    assert "078-05-1120" in fields[0]["value"]


def test_update_annotated_field_edits_label_and_overrides_value(document_with_text):
    client.post("/Page/SetAnnotations", json={
        "document_id": document_with_text, "page_number": 1,
        "annotations": [{"page": 1, "type": "rect", "x": 45, "y": 70, "width": 150, "height": 15, "text": "ssn"}],
    })

    resp = client.post("/Factory/UpdateAnnotatedField", json={
        "document_id": document_with_text, "page": 1, "index": 0,
        "label": "social_security_number", "value": "REDACTED",
    })
    assert resp.status_code == 200

    extract_resp = client.get("/Factory/ExtractAnnotatedFields", params={"documentId": document_with_text})
    fields = extract_resp.json()["fields"]
    assert fields[0]["label"] == "social_security_number"
    assert fields[0]["value"] == "REDACTED"  # override wins over recomputing from the page

    annotations_resp = client.post("/Page/GetAnnotations", json={"document_id": document_with_text, "page_number": 1})
    assert annotations_resp.json()["annotations"][0]["text"] == "social_security_number"


def test_update_annotated_field_out_of_range_index_is_400(document_with_text):
    client.post("/Page/SetAnnotations", json={
        "document_id": document_with_text, "page_number": 1,
        "annotations": [{"page": 1, "type": "rect", "x": 0, "y": 0, "width": 10, "height": 10, "text": "a"}],
    })
    resp = client.post("/Factory/UpdateAnnotatedField", json={
        "document_id": document_with_text, "page": 1, "index": 5, "label": "x",
    })
    assert resp.status_code == 400
