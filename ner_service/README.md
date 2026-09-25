# ner_service

A standalone [GLiNER2](https://github.com/fastino-ai/GLiNER2) inference
sidecar used by the main app's search bar: with the **NER** checkbox ticked, the
typed text is sent here as a zero-shot entity label. It's a
separate process with its own venv because `gliner2` requires Python 3.10+,
while the main app's venv is pinned to Python 3.9 (see the root
[README.md](../README.md)'s "AI-assisted NER (GLiNER2)" section for the full
picture).

## Setup

```bash
cd ner_service
python3.10 -m venv .venv   # or any Python 3.10+ interpreter
.venv/bin/pip install -r requirements.txt
```

## Run

```bash
ner_service/.venv/bin/python ner_service/main.py
```

Listens on `127.0.0.1:8801` by default (localhost only -- it is not meant to
be reachable from outside the machine). The model (`fastino/gliner2.5-small-v1`
by default, ~74M params, CPU-friendly) loads at startup, not on the first
request -- a cold load (first-time download + torch init) was measured at
~25s on a dev machine, close enough to the main app's 30s request timeout
that loading it lazily on the first click risked that first request timing
out. This means the process takes ~20-30s to start accepting connections the
very first time (subsequent restarts are faster once the weights are cached
under `~/.cache/huggingface`); `Factory/ListConcepts` on the main app will
report `ner_available: false` until it's ready.

Env vars:
- `GLINER_MODEL` -- Hugging Face model id (default `fastino/gliner2.5-small-v1`;
  larger/more accurate options: `fastino/gliner2.5-base-v1`, `fastino/gliner2-large-v1`).
- `GLINER_HOST` / `GLINER_PORT` -- bind address (default `127.0.0.1:8801`).
- `GLINER_DEFAULT_THRESHOLD` -- default confidence threshold (default `0.4`).

The main app finds this service at `DOCSVC_NER_SERVICE_URL` (default
`http://127.0.0.1:8801`) -- see `app/services/ner_client.py`. If this service
isn't running, the viewer grays out the NER checkbox
(`Factory/ListConcepts` reports `ner_available: false`); the regex concepts
and plain text search work regardless.
