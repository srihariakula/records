"""
In-process, disk-backed equivalent of LEADTOOLS' ObjectCache / DocumentFactory
cache used by the Factory controller.

Scope, deliberately: this replaces the single-process caching path only. Two
pieces of the original Factory.java are NOT ported here and would need their own
design if wanted later:
  - PreCacheDocument / ReportPreCache: a cross-user, URI-keyed shared document
    dictionary (an optimization for many users viewing the same source document).
  - SaveAttachmentToCache / LoadDocumentAttachment: extracting sub-documents
    embedded in a container format (e.g. email attachments) -- LEADTOOLS' document
    model understands those containers natively; there's no drop-in open-source
    equivalent used here.
"""
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from app.models import AnnotationObject
from app.services import document_session
from app.services.errors import ConversionError

CACHE_ROOT = Path(tempfile.gettempdir()) / "document-service-py-cache"
CACHE_ROOT.mkdir(exist_ok=True)

DEFAULT_TTL_SECONDS = int(os.environ.get("DOCSVC_CACHE_TTL_SECONDS", "3600"))
ACCESS_PASSCODE = os.environ.get("DOCSVC_ACCESS_PASSCODE")  # unset = no passcode required, same as LEADTOOLS' default

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _new_id() -> str:
    return uuid.uuid4().hex


def _validate_document_id(document_id: str) -> str:
    # documentId is used to build a cache directory path -- reject anything that
    # isn't a plain token to rule out path traversal (e.g. "../../etc").
    if not _SAFE_ID_RE.match(document_id):
        raise ConversionError(
            "Invalid documentId: must be 1-128 characters of letters, digits, '_' or '-'",
            status_code=400,
        )
    return document_id


def _safe_file_name(name: Optional[str]) -> str:
    # `name` is caller-supplied (BeginUpload / UploadDocument / SaveToCache) and
    # becomes a path under the entry's directory -- keep only its final
    # component so "../../x" can't write outside the cache, or point delete()'s
    # rmtree of the file's parent at an arbitrary directory. Both separators
    # are stripped since the name may come from a Windows client.
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    if base in ("", ".", "..") or base == document_session.RENDERED_PDF_FILENAME:
        return "document.bin"
    return base


def check_passcode(passcode: Optional[str]) -> None:
    if ACCESS_PASSCODE and passcode != ACCESS_PASSCODE:
        raise ConversionError("Unauthorized: passcode is incorrect", status_code=401)


@dataclass
class DocumentEntry:
    document_id: str
    file_path: Path
    name: Optional[str] = None
    mime_type: Optional[str] = None
    page_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)
    ttl_seconds: int = DEFAULT_TTL_SECONDS
    annotations: Dict[int, List[AnnotationObject]] = field(default_factory=dict)
    conversion_error: Optional[str] = None  # why the upload couldn't be turned into a PDF, if it couldn't

    def is_expired(self) -> bool:
        return (time.time() - self.last_access) > self.ttl_seconds

    def touch(self) -> None:
        self.last_access = time.time()

    def has_annotations(self) -> bool:
        return any(self.annotations.values())


@dataclass
class UploadSession:
    upload_id: str
    file_path: Path
    document_id: str
    mime_type: Optional[str] = None
    name: Optional[str] = None


class DocumentCache:
    def __init__(self):
        self._entries: Dict[str, DocumentEntry] = {}
        self._uploads: Dict[str, UploadSession] = {}
        self._lock = threading.RLock()

    # -- chunked upload lifecycle (BeginUpload / UploadDocument[Blob] / EndUpload) --

    def begin_upload(self, document_id: Optional[str] = None, mime_type: Optional[str] = None,
                      name: Optional[str] = None) -> str:
        document_id = _validate_document_id(document_id) if document_id else _new_id()
        upload_id = _new_id()
        file_path = CACHE_ROOT / f"_upload_{upload_id}.tmp"
        file_path.touch()
        with self._lock:
            self._uploads[upload_id] = UploadSession(upload_id, file_path, document_id, mime_type, name)
        return upload_id

    def _require_upload(self, upload_id: str) -> UploadSession:
        with self._lock:
            session = self._uploads.get(upload_id)
        if session is None:
            raise ConversionError(f"Unknown or already-finalized upload uri: {upload_id}", status_code=400)
        return session

    def append_chunk(self, upload_id: str, data: bytes) -> None:
        session = self._require_upload(upload_id)
        with open(session.file_path, "ab") as f:
            f.write(data)

    def end_upload(self, upload_id: str) -> DocumentEntry:
        session = self._require_upload(upload_id)
        entry = self._finalize(session.document_id, session.file_path.read_bytes(), session.name, session.mime_type)
        session.file_path.unlink(missing_ok=True)
        with self._lock:
            del self._uploads[upload_id]
        return entry

    def abort_upload(self, upload_id: str) -> None:
        with self._lock:
            session = self._uploads.pop(upload_id, None)
        if session and session.file_path.exists():
            session.file_path.unlink()

    # -- cache entries --

    def _finalize(self, document_id: str, data: bytes, name: Optional[str],
                  mime_type: Optional[str]) -> DocumentEntry:
        document_id = _validate_document_id(document_id)
        entry_dir = CACHE_ROOT / document_id
        entry_dir.mkdir(exist_ok=True)
        file_path = entry_dir / _safe_file_name(name)
        file_path.write_bytes(data)

        detected_mime = document_session.detect_mime_type(file_path, mime_type)
        page_count = 0
        conversion_error = None
        try:
            pdf_path = document_session.get_pdf_path_for(file_path, detected_mime)
            page_count = document_session.count_pages(pdf_path)
        except ConversionError as exc:
            # Still cache the upload (the original can be downloaded, and a retry
            # after installing a converter works), but report why it has no pages.
            conversion_error = exc.message

        entry = DocumentEntry(document_id=document_id, file_path=file_path, name=name, mime_type=detected_mime,
                               page_count=page_count, conversion_error=conversion_error)
        with self._lock:
            self._entries[document_id] = entry
        return entry

    def put_bytes(self, document_id: Optional[str], data: bytes, name: Optional[str] = None,
                  mime_type: Optional[str] = None) -> DocumentEntry:
        return self._finalize(document_id or _new_id(), data, name, mime_type)

    def get(self, document_id: str) -> Optional[DocumentEntry]:
        _validate_document_id(document_id)
        with self._lock:
            entry = self._entries.get(document_id)
        if entry is None or entry.is_expired():
            return None
        entry.touch()
        return entry

    def require(self, document_id: str) -> DocumentEntry:
        entry = self.get(document_id)
        if entry is None:
            raise ConversionError(f"Document not found or expired in cache: {document_id}", status_code=404)
        return entry

    def delete(self, document_id: str, allow_missing: bool = False) -> None:
        _validate_document_id(document_id)
        with self._lock:
            entry = self._entries.pop(document_id, None)
        if entry is None:
            if not allow_missing:
                raise ConversionError(f"Document not found in cache: {document_id}", status_code=404)
            return
        shutil.rmtree(entry.file_path.parent, ignore_errors=True)

    def clone(self, document_id: str, clone_document_id: Optional[str] = None) -> DocumentEntry:
        source = self.require(document_id)
        return self.put_bytes(clone_document_id, source.file_path.read_bytes(), name=source.name,
                               mime_type=source.mime_type)

    def purge_expired(self) -> int:
        with self._lock:
            expired = [doc_id for doc_id, entry in self._entries.items() if entry.is_expired()]
        for doc_id in expired:
            self.delete(doc_id, allow_missing=True)
        return len(expired)

    def statistics(self) -> dict:
        with self._lock:
            entries = list(self._entries.values())
            uploads_in_progress = len(self._uploads)
        total_bytes = sum(e.file_path.stat().st_size for e in entries if e.file_path.exists())
        return {
            "entry_count": len(entries),
            "total_bytes": total_bytes,
            "upload_sessions_in_progress": uploads_in_progress,
        }

    def heartbeat(self, document_ids: List[str]) -> None:
        for doc_id in document_ids:
            self.get(doc_id)  # get() already bumps last_access on a hit


cache = DocumentCache()
