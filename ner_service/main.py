"""
Standalone GLiNER2 (fastino-ai/GLiNER2, Apache-2.0) zero-shot extraction
service. Kept out of the main app's process/venv because the `gliner2`
package requires Python 3.10+ while the main app's venv is pinned to
Python 3.9 -- see ../README.md's "AI-assisted NER (GLiNER2)" section.

The main app calls this over localhost HTTP via app.services.ner_client,
pointed at it through DOCSVC_NER_SERVICE_URL.

PHI note: request/response bodies here are raw page text from documents the
main app is viewing (may contain patient names, DOB, diagnoses, medications).
Nothing in this module logs `text`, `labels` values, or extracted entity text
-- keep it that way if you touch this file. uvicorn's own access log line
records only method/path/status, not the body.
"""
import os
from typing import Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

MODEL_NAME = os.environ.get("GLINER_MODEL", "fastino/gliner2.5-small-v1")
HOST = os.environ.get("GLINER_HOST", "127.0.0.1")
PORT = int(os.environ.get("GLINER_PORT", "8801"))
DEFAULT_THRESHOLD = float(os.environ.get("GLINER_DEFAULT_THRESHOLD", "0.4"))

app = FastAPI(title="gliner2-ner-service", description="Local sidecar wrapping fastino-ai/GLiNER2.")

_extractor = None


@app.on_event("startup")
async def _load_model_on_startup():
    # Loaded eagerly (server startup blocks on this) rather than lazily on the
    # first /extract call: a cold load (weights download + torch init) was
    # measured at ~25s on this machine, close enough to ner_client.py's 30s
    # request timeout that the very first click on an AI-assisted pill could
    # time out and surface as a 503 even though nothing's actually wrong.
    global _extractor
    from gliner2 import AutoExtractor

    _extractor = AutoExtractor.from_pretrained(MODEL_NAME)


class ExtractRequest(BaseModel):
    text: str
    labels: List[str]
    threshold: Optional[float] = None


class ExtractResponse(BaseModel):
    entities: Dict[str, List[Dict]]


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_NAME, "model_loaded": _extractor is not None}


@app.post("/extract", response_model=ExtractResponse)
async def extract(request: ExtractRequest):
    result = _extractor.extract_entities(
        request.text,
        request.labels,
        threshold=request.threshold if request.threshold is not None else DEFAULT_THRESHOLD,
        include_spans=True,
    )
    return {"entities": result.get("entities", {})}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
