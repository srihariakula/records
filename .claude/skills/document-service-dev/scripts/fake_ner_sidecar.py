"""Stand-in for ner_service/ with the same /health + /extract contract, using a
keyword lookup instead of the GLiNER2 model. Lets you exercise the viewer's
NER checkbox end to end without Python 3.10, torch or a model download.

Every label received is appended (JSON, one per line) to $NER_LABEL_LOG so a
test can assert exactly what the viewer sent to GLiNER2.

Run:  NER_LABEL_LOG=/path/labels.log uvicorn fake_ner_sidecar:app --port 8801
"""
import json
import os
from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

LOG = os.environ.get("NER_LABEL_LOG")
VOCAB = {
    "medication": ["Metformin", "Lisinopril"],
    "diagnosis": ["Diabetes", "Hypertension"],
    "person name": ["Jane Doe"],
}

app = FastAPI(title="fake-gliner2-sidecar")


class ExtractRequest(BaseModel):
    text: str
    labels: List[str]
    threshold: Optional[float] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extract")
def extract(req: ExtractRequest):
    out = {}
    for label in req.labels:
        if LOG:
            with open(LOG, "a") as f:
                f.write(json.dumps(label) + "\n")
        entities = []
        for word in VOCAB.get(label.lower(), []):
            start = req.text.find(word)
            if start >= 0:
                entities.append({"text": word, "start": start, "end": start + len(word)})
        out[label] = entities
    return {"entities": out}
