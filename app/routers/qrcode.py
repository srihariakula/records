"""Mirrors com.leadtools.document_service.controllers.QRCodeController (@Path("qrcode"))."""
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import Response

from app.models_qrcode import GenerateQrRequest, QRDetectionResponse
from app.services import qr_code

router = APIRouter(prefix="/qrcode", tags=["qrcode"])


@router.post("/generate")
async def generate(request: GenerateQrRequest) -> Response:
    png_bytes = qr_code.generate_qr_png(request.qrcode)
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{qr_code.generate_qr_filename()}"'},
    )


@router.post("/detect", response_model=QRDetectionResponse)
async def detect(file: UploadFile = File(...)):
    pagewise = qr_code.detect_qr_codes_by_page(await file.read(), file.filename or "document")
    return QRDetectionResponse(pagewise_qr_codes=pagewise)
