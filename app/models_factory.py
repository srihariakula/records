"""Mirrors com.leadtools.document_service.models.factory.*.

Field names are snake_case (Python convention) rather than the original
camelCase JSON contract -- this is a port, not a wire-compatible drop-in
replacement. GET-endpoint query params (Factory.DownloadDocument, etc.) keep
the original camelCase names via FastAPI aliases, since those are cheap to
preserve and matter most for reusing an existing frontend's URLs.
"""
from typing import List, Optional

from pydantic import BaseModel


class DocumentDTO(BaseModel):
    """Minimal stand-in for LEADTOOLS' serialized LEADDocument -- just enough
    metadata for a viewer to page through a document."""
    document_id: str
    name: Optional[str] = None
    mime_type: Optional[str] = None
    page_count: int = 0
    has_annotations: bool = False


class BeginUploadRequest(BaseModel):
    document_id: Optional[str] = None
    mime_type: Optional[str] = None
    name: Optional[str] = None


class BeginUploadResponse(BaseModel):
    upload_uri: str


class UploadDocumentRequest(BaseModel):
    """The original Java DTO also has a raw `buffer: byte[]` alternative to `data`,
    meant for binary-friendly transports. Over plain JSON that doesn't apply --
    a base64 string is the only sane encoding, so `buffer` is dropped here."""
    uri: str
    data: Optional[str] = None  # base64-encoded chunk


class EndUploadRequest(BaseModel):
    uri: str


class AbortUploadDocumentRequest(BaseModel):
    uri: str


class LoadFromCacheRequest(BaseModel):
    document_id: str


class LoadFromCacheResponse(BaseModel):
    document: Optional[DocumentDTO] = None


class LoadFromUriRequest(BaseModel):
    uri: str
    name: Optional[str] = None


class LoadFromUriResponse(BaseModel):
    document: DocumentDTO


class SaveToCacheRequest(BaseModel):
    document_id: Optional[str] = None
    name: Optional[str] = None


class SaveToCacheResponse(BaseModel):
    document: DocumentDTO


class CloneDocumentRequest(BaseModel):
    document_id: str
    clone_document_id: Optional[str] = None
    delete_source_document: bool = False


class CloneDocumentResponse(BaseModel):
    document: DocumentDTO


class DeleteRequest(BaseModel):
    document_id: str
    allow_non_existing: bool = False


class DocumentsHeartbeatRequest(BaseModel):
    document_ids: List[str]


class GetCacheStatisticsResponse(BaseModel):
    entry_count: int
    total_bytes: int
    upload_sessions_in_progress: int


class SearchMultiCriteriaRequest(BaseModel):
    """Combines a free-text query with any number of selected concept ids
    (see app.services.concepts_registry) into one AND search -- see
    Factory/SearchMultiCriteria and app.services.multi_criteria_search."""
    document_id: str
    query: Optional[str] = None
    case_sensitive: bool = False
    whole_word: bool = False
    use_regex: bool = False
    concept_ids: List[str] = []


class UpdateAnnotatedFieldRequest(BaseModel):
    """Edits one annotation's label and/or corrected value in place, identified
    by its position within that page's annotation list -- the `index` field
    returned alongside it by Factory/ExtractAnnotatedFields."""
    document_id: str
    page: int
    index: int
    label: Optional[str] = None
    value: Optional[str] = None
