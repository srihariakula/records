"""
Thin HTTP client for the GLiNER2 NER sidecar (ner_service/, run as a separate
process/venv because gliner2 requires Python 3.10+ -- see that directory's
README and the root README's "AI-assisted NER (GLiNER2)" section).

PHI note: `text` here is raw page content from documents the app is viewing,
which may contain patient names, DOB, diagnoses, medications. Do not add
logging of `text` or of extracted entity text to this module.
"""
import os
from typing import Dict, List, Optional

import requests

from app.services.errors import ConversionError

NER_SERVICE_URL = os.environ.get("DOCSVC_NER_SERVICE_URL", "http://127.0.0.1:8801").rstrip("/")
NER_TIMEOUT_SECONDS = float(os.environ.get("DOCSVC_NER_TIMEOUT_SECONDS", "30"))
NER_THRESHOLD = float(os.environ.get("DOCSVC_NER_THRESHOLD", "0.4"))
_HEALTH_TIMEOUT_SECONDS = 1.5


def is_available() -> bool:
    """Used by Factory/ListConcepts so the viewer can gray out the
    AI-assisted NER pills instead of letting a click fail against a sidecar
    that was never started."""
    try:
        resp = requests.get(f"{NER_SERVICE_URL}/health", timeout=_HEALTH_TIMEOUT_SECONDS)
        return resp.ok
    except requests.RequestException:
        return False


def extract_entities(text: str, gliner_label: str, threshold: Optional[float] = None) -> List[Dict]:
    """Returns [{"text": ..., "start": ..., "end": ...}, ...] for one label,
    with offsets into `text` as passed in. `threshold` overrides the global
    NER_THRESHOLD default -- see concepts_registry.NerConcept.threshold."""
    if not text.strip():
        return []
    try:
        resp = requests.post(
            f"{NER_SERVICE_URL}/extract",
            json={"text": text, "labels": [gliner_label], "threshold": threshold if threshold is not None else NER_THRESHOLD},
            timeout=NER_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise ConversionError(
            "AI-assisted NER service is unavailable. Start ner_service/ (see ner_service/README.md) "
            "and point DOCSVC_NER_SERVICE_URL at it if it isn't on the default port.",
            status_code=503,
        ) from exc
    if not resp.ok:
        raise ConversionError(f"NER service returned an error (status {resp.status_code})", status_code=502)
    return resp.json().get("entities", {}).get(gliner_label, [])
