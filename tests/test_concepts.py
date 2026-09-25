import xml.etree.ElementTree as ET

import fitz
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import AnnotationObject
from app.services import ann_xml_export, multi_criteria_search, regex_concepts, search_text
from app.services.cache_store import cache

client = TestClient(app)


def _make_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def sample_pdf_path(tmp_path):
    text = (
        "Member: Jane Sample Doe\n"
        "DOB: 04/12/1985\n"
        "Email: jane.sample@example.com\n"
        "Phone: (555) 123-4567\n"
        "Chase ID: CHS-0012345\n"
        "Diagnosis: Type 2 Diabetes Mellitus\n"
    )
    path = tmp_path / "sample.pdf"
    path.write_bytes(_make_pdf_bytes(text))
    return path


def test_regex_concept_finds_email(sample_pdf_path):
    matches = regex_concepts.find_concept_matches(sample_pdf_path, "email")
    assert matches.get(1)
    assert len(matches[1]) == 1


def test_regex_concept_finds_chase_id(sample_pdf_path):
    matches = regex_concepts.find_concept_matches(sample_pdf_path, "chase_id")
    assert matches.get(1)


def test_regex_concept_unknown_id_raises(sample_pdf_path):
    with pytest.raises(Exception):
        regex_concepts.find_concept_matches(sample_pdf_path, "not-a-real-concept")


def test_search_document_case_sensitive_flag(sample_pdf_path):
    insensitive = search_text.search_document(sample_pdf_path, "diagnosis")
    sensitive = search_text.search_document(sample_pdf_path, "diagnosis", case_sensitive=True)
    assert sum(len(v) for v in insensitive.values()) == 1
    assert sum(len(v) for v in sensitive.values()) == 0  # actual text is "Diagnosis"


def test_search_document_whole_word_flag(sample_pdf_path):
    partial = search_text.search_document(sample_pdf_path, "Diabet", whole_word=True)
    whole = search_text.search_document(sample_pdf_path, "Diabetes", whole_word=True)
    assert sum(len(v) for v in partial.values()) == 0
    assert sum(len(v) for v in whole.values()) == 1


def test_search_document_regex_flag(sample_pdf_path):
    matches = search_text.search_document(sample_pdf_path, r"\d{3}-\d{4}", use_regex=True)
    assert sum(len(v) for v in matches.values()) == 1


def test_search_document_invalid_regex_returns_400():
    entry = cache.put_bytes(None, _make_pdf_bytes("hello"), name="test.pdf", mime_type="application/pdf")
    try:
        resp = client.get(
            "/Factory/SearchDocument",
            params={"documentId": entry.document_id, "query": "(unclosed", "regex": "true"},
        )
        assert resp.status_code == 400
    finally:
        cache.delete(entry.document_id, allow_missing=True)


def test_list_concepts_endpoint():
    resp = client.get("/Factory/ListConcepts")
    assert resp.status_code == 200
    body = resp.json()
    assert {c["id"] for c in body["regex_concepts"]} == {"email", "phone", "dob", "visit_date", "chase_id"}
    assert {c["id"] for c in body["ner_concepts"]} == {
        "person_name", "any_date", "diagnosis", "medication", "quality_measure", "submeasure", "vitals",
    }
    assert "ner_available" in body


def test_search_concept_endpoint_regex(sample_pdf_path):
    entry = cache.put_bytes(None, sample_pdf_path.read_bytes(), name="test.pdf", mime_type="application/pdf")
    try:
        resp = client.get(
            "/Factory/SearchConcept", params={"documentId": entry.document_id, "conceptId": "email"}
        )
        assert resp.status_code == 200
        assert resp.json()["total_matches"] == 1
    finally:
        cache.delete(entry.document_id, allow_missing=True)


def test_ann_xml_export_shape(sample_pdf_path):
    anns = {
        1: [
            AnnotationObject(
                page=1, type="rect", x=50, y=60, width=100, height=40,
                text="Member Name", color="#FF0000", value="Jane Doe",
            ),
        ],
    }
    xml_bytes = ann_xml_export.build_annotations_xml(sample_pdf_path, "doc123", anns)
    root = ET.fromstring(xml_bytes)

    assert root.tag == "Annotations"
    assert root.find("Version").text == "1"

    container = root.find("Container")
    assert container.find("PageNumber").text == "1"
    # sample_pdf_path's page is PyMuPDF's new_page() default (595x842, A4) --
    # LEAD_UNITS_PER_POINT (10) times that.
    assert container.find("Size").find("Width").text == "5950"
    assert container.find("Size").find("Height").text == "8420"

    obj = container.find("Objects").find("Object")
    assert obj.find("ObjectType").text == "Leadtools.Annotations.Engine.AnnRectangleObject"
    assert obj.find("Labels").find("Label").find("Text").text == "Member Name"
    assert len(obj.find("Points").findall("Point")) == 4
    # Fields with no data on AnnotationObject are still present, just empty.
    assert obj.find("Hyperlink").text is None
    assert obj.find("UserId").text is None
    content_item = obj.find("Metadata").findall("Item")[4]
    assert content_item.find("Key").text == "Content"
    assert content_item.find("Value").text == "Jane Doe"


def test_ann_xml_export_empty_page_has_no_objects(sample_pdf_path):
    xml_bytes = ann_xml_export.build_annotations_xml(sample_pdf_path, "doc123", {})
    root = ET.fromstring(xml_bytes)
    assert root.find("Container").find("Objects").find("Object") is None


def test_download_annotations_xml_endpoint(sample_pdf_path):
    entry = cache.put_bytes(None, sample_pdf_path.read_bytes(), name="test.pdf", mime_type="application/pdf")
    try:
        entry.annotations[1] = [AnnotationObject(page=1, type="rect", x=0, y=0, width=10, height=10, text="X")]
        resp = client.get("/Factory/DownloadAnnotationsXml", params={"documentId": entry.document_id})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/xml"
        root = ET.fromstring(resp.content)
        assert root.tag == "Annotations"
    finally:
        cache.delete(entry.document_id, allow_missing=True)


@pytest.fixture
def two_page_pdf_path(tmp_path):
    doc = fitz.open()
    doc.new_page().insert_text((50, 72), "Email: jane.sample@example.com", fontsize=11)
    doc.new_page().insert_text((50, 72), "Chase ID: CHS-0012345", fontsize=11)
    path = tmp_path / "two_page.pdf"
    path.write_bytes(doc.tobytes())
    doc.close()
    return path


def test_multi_criteria_and_intersection_across_pages(two_page_pdf_path):
    # email only matches page 1, chase_id only matches page 2 -- AND across
    # both concepts should qualify no pages at all.
    matches = multi_criteria_search.search_multi_criteria(two_page_pdf_path, None, ["email", "chase_id"])
    assert matches == {}


def test_multi_criteria_single_concept_matches_its_page(two_page_pdf_path):
    matches = multi_criteria_search.search_multi_criteria(two_page_pdf_path, None, ["chase_id"])
    assert list(matches.keys()) == [2]


def test_multi_criteria_query_and_concept_on_same_page(sample_pdf_path):
    # sample_pdf_path has both "Diagnosis" text and an email on page 1.
    matches = multi_criteria_search.search_multi_criteria(sample_pdf_path, "Diagnosis", ["email"])
    assert list(matches.keys()) == [1]
    assert len(matches[1]) == 2  # one box for the text match, one for the email


def test_multi_criteria_no_criteria_raises_400():
    with pytest.raises(Exception):
        multi_criteria_search.search_multi_criteria("irrelevant", None, [])


def test_search_multi_criteria_endpoint(two_page_pdf_path):
    entry = cache.put_bytes(None, two_page_pdf_path.read_bytes(), name="test.pdf", mime_type="application/pdf")
    try:
        resp = client.post(
            "/Factory/SearchMultiCriteria",
            json={"document_id": entry.document_id, "concept_ids": ["chase_id"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert list(body["matches"].keys()) == ["2"]

        empty_resp = client.post(
            "/Factory/SearchMultiCriteria",
            json={"document_id": entry.document_id, "concept_ids": ["email", "chase_id"]},
        )
        assert empty_resp.json()["total_matches"] == 0
    finally:
        cache.delete(entry.document_id, allow_missing=True)


def test_search_concept_endpoint_unknown_concept(sample_pdf_path):
    entry = cache.put_bytes(None, sample_pdf_path.read_bytes(), name="test.pdf", mime_type="application/pdf")
    try:
        resp = client.get(
            "/Factory/SearchConcept", params={"documentId": entry.document_id, "conceptId": "not-a-concept"}
        )
        assert resp.status_code == 400
    finally:
        cache.delete(entry.document_id, allow_missing=True)
