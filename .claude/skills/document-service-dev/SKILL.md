---
name: document-service-dev
description: Set up, run, test and verify document-service-py (the FastAPI port of LEADTOOLS' document-service, its /viewer browser UI, and the GLiNER2 NER sidecar). Use this whenever you need to install dependencies, start the app, run pytest, check a change actually works in the viewer, reproduce a UI bug, or confirm .docx/office uploads convert. Also use it before declaring any change to app/, web/ or ner_service/ done, since unit tests alone have missed real UI regressions in this repo.
---

# document-service-py: run, test, verify

## Layout (what lives where)

- `app/main.py`: the FastAPI app. It mounts the routers and serves `web/` at `/viewer`.
- `app/routers/`: `convert.py`, `factory.py` (upload, cache, download, search), `page.py` (image, text, annotations), `qrcode.py`.
- `app/services/`: the engines. PyMuPDF does rendering, text and search. LibreOffice converts office files to PDF. Pillow and OpenCV handle images and QR codes. The cache is on disk under the OS temp dir.
- `web/`: the viewer. Vanilla `index.html`, `app.js` and `style.css`, with no build step.
- `ner_service/`: the GLiNER2 sidecar. It needs Python 3.10+ and has its own venv. It listens on `:8801`, and the app reaches it via `DOCSVC_NER_SERVICE_URL`.
- `tests/`: pytest suite. It needs no network, no LibreOffice and no sidecar (the NER client is monkeypatched).
- `samples/`: synthetic HEDIS `.docx` charts. The root `CBP.pdf` and `EED.pdf` are the original samples.

## Setup

```bash
pip install -r requirements.txt            # app + pytest + httpx
# Office uploads (.docx etc.) need LibreOffice WITH Writer:
apt-get install -y --no-install-recommends libreoffice-writer
```

`libreoffice-core` alone is a trap. `soffice` exists, but every conversion fails with "source file could not be loaded", even for a `.txt`. If uploads of non-PDFs fail, check `dpkg -l | grep libreoffice-writer` first.

The real NER sidecar is optional for most work; see `ner_service/README.md` for how to set it up. For UI testing, use the fake sidecar below instead.

## Run

```bash
uvicorn app.main:app --reload --port 8811     # viewer: http://127.0.0.1:8811/viewer/
```

The viewer calls `Factory/ListConcepts` only on page load to decide whether the NER checkbox is enabled. If you start the sidecar after opening the page, reload it.

## Test

```bash
python3 -m pytest tests/ -q -p no:cacheprovider
```

- Run it with `PYTHONDONTWRITEBYTECODE=1`, or rely on `.gitignore`. Never commit `__pycache__`.
- When you fix a bug, first show the new test failing against the old code: stash the fix, run the test, then pop the fix back. Then show it passing.
- Any test that exercises cache or file paths must root the cache in `tmp_path` (monkeypatch `cache_store.CACHE_ROOT`). Never let a test clean up through a code path that could `rmtree` outside the cache. See the `security-conventions` skill; this once wiped `/tmp`.

## Verify UI changes in a real browser (do this, don't skip it)

Unit tests don't cover `web/`. A CSS change once left the concept dropdown opening behind the page image, so its checkboxes couldn't be clicked, and pytest was all green. Run the bundled end-to-end check:

```bash
.claude/skills/document-service-dev/scripts/run_ui_check.sh [WORK_DIR]
```

It starts the app on `:8811` and `scripts/fake_ner_sidecar.py` on `:8801`. The fake sidecar is a keyword stand-in for GLiNER2 that logs every label it receives. The script then drives Chromium through `scripts/ui_smoke_test.js`, first with the sidecar up (24 checks) and then with it down (4 checks), and shuts everything down. It exits non-zero on any failure.

The checks cover:
- the search bar layout and the NER checkbox;
- that the dropdown lists regex concepts only;
- literal search versus NER search, including that the exact typed label is sent to GLiNER2;
- AND-ing with a concept, the Enter key, and a label with no matches;
- non-ASCII download filenames;
- wrapping at a narrow width;
- JS errors.

**Look at the screenshots it writes to WORK_DIR, not just the PASS lines.** When you change the UI, add a check for the new behaviour to `ui_smoke_test.js` in the same style.

Environment gotchas that aren't app bugs:
- Chromium lives at `/opt/pw-browsers/chromium`; override with `CHROMIUM_PATH`. Don't run `playwright install`. The script installs `playwright-core` into WORK_DIR.
- playwright-core can't `setInputFiles` from a disk path containing CJK characters; the file silently isn't attached. Pass `{name, mimeType, buffer}` instead.
- Under a non-UTF-8 locale, Chromium names non-ASCII downloads `download`. The script exports `LANG=C.UTF-8`.
- `GET /favicon.ico` returning 404 is expected noise.

For a quick manual look, start the app plus `uvicorn fake_ner_sidecar:app --port 8801`, run from `scripts/` with `NER_LABEL_LOG` set, and screenshot with playwright-core.

## Before you call it done

1. `pytest` is green.
2. For any `web/` change, `run_ui_check.sh` passes and you've looked at the screenshots.
3. Re-read your diff for anything that would break the checks above.
4. `git status` shows no `__pycache__` files or scratch files.
