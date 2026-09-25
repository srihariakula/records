"""Mirrors com.leadtools.document_service.models.document.{GenerateQrRequest,QRDetectionResponse}."""
from typing import Dict, List

from pydantic import BaseModel


class GenerateQrRequest(BaseModel):
    qrcode: str


class QRDetectionResponse(BaseModel):
    pagewise_qr_codes: Dict[int, List[str]]
