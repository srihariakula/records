---
name: leadtools-port
description: How to port another LEADTOOLS document-service capability (a Java controller or endpoint such as Factory, Page, convert, qrcode, Structure, ReadBarcodes, SVG) into this Python/FastAPI repo, or add a new "not in the original" endpoint, following the repo's existing conventions. Use it whenever someone asks to port, mirror, map or re-implement a LEADTOOLS endpoint, or add an endpoint to app/routers, even if they don't say "port".
---

# Porting a LEADTOOLS endpoint

This repo is a **proof of concept for scoping a LEADTOOLS → Python migration**, not a drop-in replacement. Every port swaps LEADTOOLS' proprietary engine for an open-source one and says honestly what's lost. Read the matching Java controller first, then follow the existing pattern.

## Where things go

| Piece | Location | Pattern to copy |
|---|---|---|
| Route | `app/routers/<controller>.py` with `APIRouter(prefix="/<Controller>")`, registered in `app/main.py` | `factory.py`, `page.py` |
| Request/response models | `app/models_<controller>.py` (pydantic) | `models_factory.py` |
| Engine logic | `app/services/<name>.py`, kept free of FastAPI imports | `search_text.py`, `qr_code.py` |
| Errors | raise `app.services.errors.ConversionError(msg, status_code=...)`; `app/main.py` turns it into JSON `{"message": ...}` | everywhere |
| Tests | `tests/test_<area>.py` with `fastapi.testclient.TestClient` | `test_factory_and_page.py` |
| Docs | README endpoint-mapping table, "Not ported", and "Honest limitations" | README |

## Conventions (keep them consistent)

- **Route names mirror the Java ones** (`/Factory/LoadFromCache`, `/Page/GetImage`), so a frontend port can map one to one. Put a docstring on each module and route saying what it mirrors, e.g. `"""Mirrors com.leadtools.document_service.controllers.Factory (@Path("Factory"))"""`, and call out every deviation.
- **Field names:** JSON bodies use snake_case (Python convention). GET query params keep the original camelCase through `Query(..., alias="documentId")`. The README documents this split, so don't change it on one endpoint only.
- **Documents:** get them through `cache.require(document_id)` (it 404s when the document is missing or expired). Use `document_session.get_pdf_path(entry)` to get a PDF, since every format is normalized to PDF once via LibreOffice. Page operations then use PyMuPDF on that PDF.
- **Endpoints with no Java counterpart:** say so explicitly in the docstring (`"""Not in the original API..."""`), and mark the README row with `*(not in the original)*`.
- **Same response shape across searches:** `{"matches": {page: [[x0,y0,x1,y1], ...]}, "total_matches": n}`, so the viewer's highlight code can be reused.
- **Downloads** set `Content-Disposition` only via `app.services.content_disposition.attachment(name)`. **Caller-supplied names, ids, paths and URLs** follow the `security-conventions` skill.

## Engine swaps already chosen (reuse them before adding a dependency)

- LEADTOOLS `DocumentConverter` / `DocumentFactory` loading → `any_to_pdf.to_pdf_bytes()`. PDFs pass through, images go to `image_convert.py` (Pillow + PyMuPDF), and office files go to headless LibreOffice (`office_convert.py`, which needs `libreoffice-writer`, `-calc` and `-impress`). Call the dispatcher; don't call a converter directly.
- Rendering, text and search → PyMuPDF (`fitz`).
- Annotation overlays → Pillow or PyMuPDF annotation objects.
- QR codes → the `qrcode` library to write them and OpenCV to read them (no system zbar needed).
- The `.ann` XML shape is in `ann_xml_export.py` (720 units per inch, i.e. PyMuPDF points × 10).

If a capability has no open-source equivalent (OCR engine parity, SVG back-image, general multi-symbology barcodes, attachments inside container formats), don't fake it. Add it to the README's "Not ported" list with the reason and the likely engine (e.g. `pyzbar`), and stop.

## Steps

1. Read the Java controller/method. Note its inputs, outputs, error cases and any auth or passcode gating. Passcode-gated endpoints use `cache_store.check_passcode`.
2. Write the service function first and unit-test it directly. Then add the thin route and an endpoint test through `TestClient`, covering one success path and each error status you raise.
3. Update the README:
   - the mapping table row: Java → Python → engine swap;
   - any behaviour that differs, under "Honest limitations";
   - anything skipped, under "Not ported".
4. If the viewer should use it, wire `web/app.js`/`index.html`. Then run the `document-service-dev` skill's UI check and add a check for the new control.
5. Run `pytest tests/ -q`; everything must be green.
