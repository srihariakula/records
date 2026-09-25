"""Mirrors com.leadtools.document_service.controllers.Factory (@Path("Factory")),
minus PreCache* / *Attachment* -- see app.services.cache_store module docstring."""
import base64
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import Response

from app.models_factory import (
    AbortUploadDocumentRequest,
    BeginUploadRequest,
    BeginUploadResponse,
    CloneDocumentRequest,
    CloneDocumentResponse,
    DeleteRequest,
    DocumentDTO,
    DocumentsHeartbeatRequest,
    EndUploadRequest,
    GetCacheStatisticsResponse,
    LoadFromCacheRequest,
    LoadFromCacheResponse,
    LoadFromUriRequest,
    LoadFromUriResponse,
    SaveToCacheRequest,
    SaveToCacheResponse,
    SearchMultiCriteriaRequest,
    UpdateAnnotatedFieldRequest,
    UploadDocumentRequest,
)
from app.services import ann_xml_export, annotate_export, content_disposition, document_session, field_extraction, multi_criteria_search, ner_client, ner_search, regex_concepts, search_text
from app.services.cache_store import DocumentEntry, cache, check_passcode
from app.services.concepts_registry import NER_CONCEPTS, REGEX_CONCEPTS, get_ner_concept, get_regex_concept
from app.services.errors import ConversionError
from app.services.uri_fetch import fetch_uri_bytes

router = APIRouter(prefix="/Factory", tags=["factory"])


def _to_dto(entry: DocumentEntry) -> DocumentDTO:
    return DocumentDTO(
        document_id=entry.document_id,
        name=entry.name,
        mime_type=entry.mime_type,
        page_count=entry.page_count,
        has_annotations=entry.has_annotations(),
    )


@router.post("/BeginUpload", response_model=BeginUploadResponse)
async def begin_upload(request: BeginUploadRequest):
    upload_uri = cache.begin_upload(request.document_id, request.mime_type, request.name)
    return BeginUploadResponse(upload_uri=upload_uri)


@router.post("/UploadDocument")
async def upload_document(request: UploadDocumentRequest):
    data = base64.b64decode(request.data) if request.data else b""
    cache.append_chunk(request.uri, data)
    return {}


@router.post("/UploadDocumentBlob")
async def upload_document_blob(uri: str = Form(...), file: UploadFile = File(...)):
    cache.append_chunk(uri, await file.read())
    return {}


@router.post("/EndUpload", response_model=DocumentDTO)
async def end_upload(request: EndUploadRequest):
    entry = cache.end_upload(request.uri)
    return _to_dto(entry)


@router.post("/AbortUploadDocument")
async def abort_upload_document(request: AbortUploadDocumentRequest):
    cache.abort_upload(request.uri)
    return {}


@router.post("/LoadFromCache", response_model=LoadFromCacheResponse)
async def load_from_cache(request: LoadFromCacheRequest):
    # Same as the original: returns document=None rather than a 404 when missing.
    entry = cache.get(request.document_id)
    return LoadFromCacheResponse(document=_to_dto(entry) if entry else None)


@router.post("/LoadFromUri", response_model=LoadFromUriResponse)
async def load_from_uri(request: LoadFromUriRequest):
    data, mime_type = fetch_uri_bytes(request.uri)
    entry = cache.put_bytes(None, data, name=request.name, mime_type=mime_type)
    return LoadFromUriResponse(document=_to_dto(entry))


@router.post("/SaveToCache", response_model=SaveToCacheResponse)
async def save_to_cache(request: SaveToCacheRequest):
    entry = cache.get(request.document_id) if request.document_id else None
    if entry is None:
        entry = cache.put_bytes(request.document_id, b"", name=request.name)
    elif request.name:
        entry.name = request.name
    return SaveToCacheResponse(document=_to_dto(entry))


@router.post("/CloneDocument", response_model=CloneDocumentResponse)
async def clone_document(request: CloneDocumentRequest):
    entry = cache.clone(request.document_id, request.clone_document_id)
    if request.delete_source_document:
        cache.delete(request.document_id, allow_missing=True)
    return CloneDocumentResponse(document=_to_dto(entry))


@router.post("/Delete")
async def delete(request: DeleteRequest):
    cache.delete(request.document_id, allow_missing=request.allow_non_existing)
    return {}


@router.get("/PurgeCache")
@router.post("/PurgeCache")
async def purge_cache(passcode: Optional[str] = Query(None)):
    check_passcode(passcode)
    removed = cache.purge_expired()
    return {"removed": removed}


@router.get("/GetCacheStatistics", response_model=GetCacheStatisticsResponse)
async def get_cache_statistics(passcode: Optional[str] = Query(None)):
    check_passcode(passcode)
    return GetCacheStatisticsResponse(**cache.statistics())


@router.post("/DocumentsHeartbeat")
async def documents_heartbeat(request: DocumentsHeartbeatRequest):
    cache.heartbeat(request.document_ids)
    return {}


@router.get("/DownloadDocument")
async def download_document(
    document_id: str = Query(..., alias="documentId"),
    file_name: Optional[str] = Query(None, alias="fileName"),
):
    entry = cache.require(document_id)
    name = file_name or entry.name or entry.document_id
    return Response(
        content=entry.file_path.read_bytes(),
        media_type=entry.mime_type or "application/octet-stream",
        headers={"Content-Disposition": content_disposition.attachment(name)},
    )


@router.get("/DownloadAnnotations")
async def download_annotations(document_id: str = Query(..., alias="documentId")):
    """Deviation from the original: returns our simplified AnnotationObject JSON
    (see app.models), not LEADTOOLS' .ann XML -- there's no XML schema to match."""
    entry = cache.require(document_id)
    all_annotations = [a.model_dump() for page_anns in entry.annotations.values() for a in page_anns]
    payload = json.dumps(all_annotations, indent=2).encode()
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": content_disposition.attachment(f"{entry.document_id}_ann.json")},
    )


@router.get("/DownloadAnnotationsXml")
async def download_annotations_xml(document_id: str = Query(..., alias="documentId")):
    """Not in the original API. Exports this document's annotations as XML
    matching LEADTOOLS' own <Annotations>/<Container>/<Object> .ann schema
    (see app.services.ann_xml_export), unlike DownloadAnnotations' simplified
    JSON -- every node from that schema is emitted for every page, even
    fields this port has no data for (left empty rather than omitted)."""
    entry = cache.require(document_id)
    pdf_path = document_session.get_pdf_path(entry)
    xml_bytes = ann_xml_export.build_annotations_xml(pdf_path, entry.document_id, entry.annotations)
    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": content_disposition.attachment(f"{entry.document_id}_ann.xml")},
    )


@router.get("/DownloadAnnotatedDocument")
async def download_annotated_document(
    document_id: str = Query(..., alias="documentId"),
    file_name: Optional[str] = Query(None, alias="fileName"),
):
    """Not in the original API -- LEADTOOLS' DownloadDocument(includeAnnotations=true)
    zips the raw document with a separate .ann XML sidecar rather than merging them.
    This instead burns the annotations directly into the page content as real PDF
    annotation objects (see app.services.annotate_export), producing one
    self-contained file. Non-PDF sources are normalized to PDF first, same as
    Page/GetImage."""
    entry = cache.require(document_id)
    pdf_path = document_session.get_pdf_path(entry)
    pdf_bytes = annotate_export.burn_annotations_into_pdf(pdf_path, entry.annotations)
    name = file_name or (Path(entry.name).stem if entry.name else entry.document_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": content_disposition.attachment(f"{name}_annotated.pdf")},
    )


@router.get("/ExtractAnnotatedFields")
async def extract_annotated_fields(document_id: str = Query(..., alias="documentId")):
    """Not in the original API. Resolves each labeled annotation against the
    actual page text underneath it (app.services.field_extraction), returning
    both a flat per-annotation list and a convenience label->value dict. Only
    annotations with a non-empty text label are included -- there's nothing to
    key an unlabeled one by."""
    entry = cache.require(document_id)
    pdf_path = document_session.get_pdf_path(entry)
    fields = field_extraction.extract_annotated_fields(pdf_path, entry.annotations)
    key_values = {field["label"]: field["value"] for field in fields}
    return {"fields": fields, "key_values": key_values}


@router.post("/UpdateAnnotatedField")
async def update_annotated_field(request: UpdateAnnotatedFieldRequest):
    """Not in the original API. Lets the viewer's extracted-fields table edit a
    label and/or manually correct a value in place, without having to resend
    that page's entire annotation list (unlike Page/SetAnnotations)."""
    entry = cache.require(request.document_id)
    page_annotations = entry.annotations.get(request.page, [])
    if request.index < 0 or request.index >= len(page_annotations):
        raise ConversionError(
            f"Annotation index {request.index} out of range for page {request.page}", status_code=400
        )
    annotation = page_annotations[request.index]
    if request.label is not None:
        annotation.text = request.label
    if request.value is not None:
        annotation.value = request.value
    return {"ok": True}


@router.get("/SearchDocument")
async def search_document(
    document_id: str = Query(..., alias="documentId"),
    query: str = Query(..., min_length=1, alias="query"),
    case_sensitive: bool = Query(False, alias="caseSensitive"),
    whole_word: bool = Query(False, alias="wholeWord"),
    use_regex: bool = Query(False, alias="regex"),
):
    """Not in the original API -- see app.services.search_text module docstring."""
    entry = cache.require(document_id)
    pdf_path = document_session.get_pdf_path(entry)
    matches = search_text.search_document(
        pdf_path, query, case_sensitive=case_sensitive, whole_word=whole_word, use_regex=use_regex
    )
    return {"matches": matches, "total_matches": sum(len(v) for v in matches.values())}


@router.post("/SearchMultiCriteria")
async def search_multi_criteria(request: SearchMultiCriteriaRequest):
    """Not in the original API. Combines a free-text query and/or any number
    of concept ids into one AND search (app.services.multi_criteria_search):
    only pages where every selected criterion matched are returned, with all
    their matched boxes on those pages unioned together. Same response shape
    as SearchDocument/SearchConcept."""
    entry = cache.require(request.document_id)
    pdf_path = document_session.get_pdf_path(entry)
    matches = multi_criteria_search.search_multi_criteria(
        pdf_path,
        request.query,
        request.concept_ids,
        case_sensitive=request.case_sensitive,
        whole_word=request.whole_word,
        use_regex=request.use_regex,
        use_ner=request.use_ner,
    )
    return {"matches": matches, "total_matches": sum(len(v) for v in matches.values())}


@router.get("/ListConcepts")
async def list_concepts():
    """Not in the original API. Backs the search bar's REGEX CONCEPTS /
    AI-ASSISTED NER pill groups (see web/index.html) -- app.services.concepts_registry
    is the source of truth for id+label; `ner_available` reflects whether the
    GLiNER2 sidecar (ner_service/) is reachable right now, so the viewer can
    disable the AI-assisted pills instead of failing on click."""
    return {
        "regex_concepts": [{"id": c.id, "label": c.label} for c in REGEX_CONCEPTS],
        "ner_concepts": [{"id": c.id, "label": c.label} for c in NER_CONCEPTS],
        "ner_available": ner_client.is_available(),
    }


@router.get("/SearchConcept")
async def search_concept(
    document_id: str = Query(..., alias="documentId"),
    concept_id: str = Query(..., alias="conceptId"),
):
    """Not in the original API. Dispatches conceptId to the regex or NER
    matcher (app.services.regex_concepts / app.services.ner_search) and
    returns the same shape as SearchDocument so the viewer reuses its existing
    highlight rendering."""
    entry = cache.require(document_id)
    pdf_path = document_session.get_pdf_path(entry)

    if get_regex_concept(concept_id) is not None:
        matches = regex_concepts.find_concept_matches(pdf_path, concept_id)
    elif get_ner_concept(concept_id) is not None:
        matches = ner_search.find_concept_matches(pdf_path, concept_id)
    else:
        raise ConversionError(f"Unknown concept: {concept_id}", status_code=400)

    return {"matches": matches, "total_matches": sum(len(v) for v in matches.values())}
