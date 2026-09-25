from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routers import convert, factory, page, qrcode
from app.services.errors import ConversionError

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(
    title="document-service (Python port)",
    description="Python/FastAPI port of the LEADTOOLS document-service reference app.",
    version="0.1.0",
)
app.include_router(convert.router)
app.include_router(factory.router)
app.include_router(page.router)
app.include_router(qrcode.router)

# A viewer built against this port's own API -- not LEADTOOLS' Leadtools.Document.Viewer.js,
# which isn't included in this checkout. See README.md.
app.mount("/viewer", StaticFiles(directory=str(WEB_DIR), html=True), name="viewer")


@app.exception_handler(ConversionError)
async def conversion_error_handler(request, exc: ConversionError):
    return JSONResponse(status_code=exc.status_code, content={"message": exc.message})


@app.get("/health")
async def health():
    return {"status": "ok"}
