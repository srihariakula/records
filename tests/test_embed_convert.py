import fitz
import pytest

from app.models import AnnotationObject
from app.services.embed_convert import embed_and_convert


def _make_pdf_bytes(page_count: int = 2) -> bytes:
    doc = fitz.open()
    for _ in range(page_count):
        doc.new_page(width=200, height=300)
    data = doc.tobytes()
    doc.close()
    return data


def test_embed_and_convert_produces_one_jpeg_per_page_plus_annotations_file():
    import io
    import zipfile

    pdf_bytes = _make_pdf_bytes(page_count=3)
    annotations = [AnnotationObject(page=1, type="rect", x=10, y=10, width=50, height=20)]
    rotation_map = {2: 90}

    zip_bytes = embed_and_convert(pdf_bytes, "input.pdf", annotations, rotation_map)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = set(zf.namelist())

    assert names == {
        "output_Page(1).jpeg",
        "output_Page(2).jpeg",
        "output_Page(3).jpeg",
        "annotations.json",
    }


def test_embed_and_convert_rejects_unparseable_pdf_bytes():
    from app.services.errors import ConversionError

    # Named .pdf so _ensure_pdf_bytes skips LibreOffice and hands this straight
    # to PyMuPDF, which must reject it as a malformed PDF.
    with pytest.raises(ConversionError):
        embed_and_convert(b"%PDF-not-a-real-pdf", "input.pdf", [], {})
