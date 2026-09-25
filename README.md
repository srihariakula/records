# document-service-py

Python/FastAPI port of three capabilities from LEADTOOLS' `document-service`
reference app:

- `convert` (`DocumentConverterController.java`) — document → PDF, and
  rotate/annotate/rasterize → zip
- `Factory` + `Page` (`Factory.java`, `Page.java`) — the document caching/session
  lifecycle and page-level viewing (image, thumbnail, text, annotations) needed
  to build a document viewer
- `qrcode` (`QRCodeController.java`) — QR code generation, and page-wise QR
  detection over a document

There's also a minimal browser viewer at `/viewer` (`web/`) built against this
port's own API, to see the pipeline actually render — see **Browser viewer**
below for why this exists instead of wiring up LEADTOOLS' own `DocumentViewerDemo`.

This is a proof-of-concept for scoping a larger LEADTOOLS -> Python migration, not
a drop-in replacement. See **Honest limitations** below before using it for anything
beyond evaluation.

## Endpoint mapping

### convert

| Java (LEADTOOLS)                          | Python (this repo)          | Engine swap |
|--------------------------------------------|------------------------------|-------------|
| `POST /convert/convertToPdf` (multipart)   | `POST /convert/to-pdf`       | LEADTOOLS `DocumentConverter` → headless **LibreOffice** |
| `POST /convert/convertToPdf` (JSON path)   | `POST /convert/to-pdf-path`  | same |
| `POST /convert/embedAndConvert`            | `POST /convert/embed-and-convert` | LEADTOOLS `DocumentConverter` + `AnnJavaRenderingEngine` → **PyMuPDF** (rotate/render) + **Pillow** (annotation overlay) |

### Factory (document cache / session lifecycle)

| Java                        | Python                              | Notes |
|------------------------------|--------------------------------------|-------|
| `POST Factory/BeginUpload`   | `POST /Factory/BeginUpload`          | returns an opaque upload token, not a real URI |
| `POST Factory/UploadDocument`| `POST /Factory/UploadDocument`       | base64 `data` only — the original's raw `buffer: byte[]` alt doesn't map cleanly onto JSON |
| `POST Factory/UploadDocumentBlob` | `POST /Factory/UploadDocumentBlob` | multipart, single-shot |
| `POST Factory/EndUpload`     | `POST /Factory/EndUpload`            | finalizes: detects mime type, converts to PDF once (cached), counts pages |
| `POST Factory/AbortUploadDocument` | `POST /Factory/AbortUploadDocument` | |
| `POST Factory/LoadFromCache` | `POST /Factory/LoadFromCache`        | returns `document: null` if missing, same as the original (not a 404) |
| `POST Factory/LoadFromUri`   | `POST /Factory/LoadFromUri`          | fetches an http(s) URL server-side — see SSRF note below |
| `POST Factory/SaveToCache`   | `POST /Factory/SaveToCache`          | metadata update / create-if-missing |
| `POST Factory/CloneDocument` | `POST /Factory/CloneDocument`        | |
| `POST Factory/Delete`        | `POST /Factory/Delete`               | |
| `GET/POST Factory/PurgeCache`| `GET/POST /Factory/PurgeCache`       | passcode-gated via `DOCSVC_ACCESS_PASSCODE` env var |
| `GET Factory/GetCacheStatistics` | `GET /Factory/GetCacheStatistics` | passcode-gated |
| `POST Factory/DocumentsHeartbeat` | `POST /Factory/DocumentsHeartbeat` | bumps TTL so an open viewer doesn't expire |
| `GET Factory/DownloadDocument` | `GET /Factory/DownloadDocument`     | |
| `GET Factory/DownloadAnnotations` | `GET /Factory/DownloadAnnotations` | returns our JSON annotation schema, not `.ann` XML |
| *(not in the original)* | `GET /Factory/DownloadAnnotationsXml` | exports annotations as XML matching LEADTOOLS' own `<Annotations>`/`<Container>`/`<Object>` `.ann` schema instead of the JSON above (`app/services/ann_xml_export.py`) — see below |
| *(not in the original)* | `GET /Factory/DownloadAnnotatedDocument` | burns the stored annotations into real PDF annotation objects (Square/FreeText via PyMuPDF) and returns one self-contained PDF — see below |
| *(not in the original)* | `GET /Factory/ExtractAnnotatedFields` | resolves each labeled annotation against the real page text under it (`app/services/field_extraction.py`); returns a flat `fields` list (each with a `page`+`index` identifying its position in that page's annotation array) plus a `key_values` label→text dict |
| *(not in the original)* | `POST /Factory/UpdateAnnotatedField` | edits one annotation's label and/or manually-corrected value in place, addressed by the `page`+`index` from `ExtractAnnotatedFields` — used by the viewer's editable fields table |
| *(not in the original)* | `GET /Factory/SearchDocument` | whole-document text search via PyMuPDF's `page.search_for` (`app/services/search_text.py`); returns `{matches: {page: [[x0,y0,x1,y1], ...]}}`. Optional `caseSensitive`/`wholeWord`/`regex` query flags switch to a regex-driven path over `app/services/page_text_index.py` |
| *(not in the original)* | `GET /Factory/ListConcepts` | lists the search bar's REGEX CONCEPTS / AI-assisted NER pills (`app/services/concepts_registry.py`) plus `ner_available` (is the GLiNER2 sidecar reachable) |
| *(not in the original)* | `GET /Factory/SearchConcept` | runs one named concept (`conceptId`) across the document — regex concepts via `app/services/regex_concepts.py`, NER concepts via `app/services/ner_search.py` + the GLiNER2 sidecar — same response shape as `SearchDocument`. See **AI-assisted NER (GLiNER2)** below |
| *(not in the original)* | `POST /Factory/SearchMultiCriteria` | combines a free-text query and/or any number of concept ids into one **AND** search (`app/services/multi_criteria_search.py`) — only pages where every selected criterion matched are returned. Backs the search bar's concept dropdown — see below |

**`DownloadAnnotatedDocument` has no equivalent in the original.** LEADTOOLS'
`DownloadDocument(includeAnnotations=true)` zips the raw document with a
separate `.ann` XML sidecar; the client viewer re-overlays them. This port
instead merges annotations directly into the document server-side
(`app/services/annotate_export.py`), producing a single portable PDF —
verified by opening the result outside this app entirely (rendered with
PyMuPDF into a plain image) and confirming the annotations are visible on
the page, not just present as metadata.

**Not ported** (see `app/services/cache_store.py` docstring for why):
`PreCacheDocument` / `ReportPreCache` (a cross-user, URI-keyed shared-document
dictionary — an optimization, not needed for a single-viewer PoC) and
`SaveAttachmentToCache` / `LoadDocumentAttachment` (extracting sub-documents
embedded in container formats, e.g. email attachments — LEADTOOLS' document
model understands those natively; no open-source drop-in exists here).
`CheckCacheInfo` is also skipped — it exists to validate a document already
staged by URI before `LoadFromUri` runs, a distinction that doesn't apply to
this port's simpler cache model.

### Page (viewing)

| Java                     | Python                    | Notes |
|---------------------------|----------------------------|-------|
| `GET Page/GetImage`       | `GET /Page/GetImage`       | query params keep the original camelCase names (`documentId`, `pageNumber`, ...) for easier frontend reuse |
| `GET Page/GetThumbnail`   | `GET /Page/GetThumbnail`   | same |
| `POST Page/GetText`       | `POST /Page/GetText`       | PDF text layer only — **no OCR** (see limitations) |
| `POST Page/GetAnnotations`| `POST /Page/GetAnnotations`| our JSON `AnnotationObject` schema, not `.ann` XML |
| `POST Page/SetAnnotations`| `POST /Page/SetAnnotations`| |

**Not ported:** `GetSvgBackImage` / `GetSvg` (LEADTOOLS' proprietary vector SVG
page representation — no equivalent object model in PyMuPDF/Pillow) and
`ReadBarcodes` (general multi-symbology barcode reading — a separate capability
from QR-only detection below; `pyzbar`/`zbar` would be the natural engine swap
if/when that's scoped as its own slice).

### qrcode

| Java                    | Python                | Engine swap |
|--------------------------|------------------------|-------------|
| `POST qrcode/generate`   | `POST /qrcode/generate`| LEADTOOLS `BarcodeEngine` writer → **`qrcode`** (Python lib) |
| `POST qrcode/detect`     | `POST /qrcode/detect`  | LEADTOOLS `BarcodeEngine` reader over a rasterized PDF → **OpenCV**'s built-in QR detector |

`detect` accepts a PDF/office document (rasterized page-by-page, same pipeline as
`Page/GetImage`) or a plain image file (PNG/JPEG/etc., treated as a single page).
Response is `{"pagewise_qr_codes": {"<page number>": ["value", ...]}}` — pages
with no QR code are omitted, matching the original's map semantics.

**Why OpenCV instead of pyzbar/zbar:** `pyzbar` needs the native `zbar` library,
which isn't a pip wheel on macOS — it requires a separate `brew install zbar`
system dependency (the same category as `convert`'s LibreOffice dependency).
OpenCV's QR detector ships inside the `opencv-python-headless` wheel with no
extra system install, and this endpoint is QR-only, not general barcode reading
— a good fit for a purpose-built detector. Trade-off: OpenCV's detector is
measurably less robust than zbar in isolation, so `app/services/qr_code.py`
runs *both* of OpenCV's detection APIs (`detectAndDecodeMulti` and iterative
`detectAndDecode` with the found region masked out) and unions the results —
each API was observed to miss cases the other one catches (see that file's
docstring for specifics). This was verified against LEADTOOLS' own
`Samples/barcodes.pdf`, correctly decoding all 4 QR codes on one page plus a
version-5 QR on another.

## LEADTOOLS-shaped annotation XML export

`Factory/DownloadAnnotationsXml` (the &#128228; button next to **Download JSON**
in the Extracted fields panel) exports this document's annotations as XML
matching LEADTOOLS' own `.ann` schema (`<Annotations>` → one `<Container>` per
page → each page's `<Objects>` → one `<Object>` per annotation), built against
a real sample of that format rather than a written spec. This is a second,
parallel export alongside `Factory/DownloadAnnotations` (this port's own
simplified JSON) — the JSON export isn't going away, this just also offers
the shape a real LEADTOOLS `.ann` sidecar file has.

Every node present in that sample is always emitted, on every page (not just
pages with annotations) — for fields this port has no equivalent data for
(`Hyperlink`, `Password`, `GroupName`, `UserId`, `Metadata/Subject`,
`Metadata/Author`, ...) the node is still created, just empty, rather than
omitted, so the document stays structurally identical to a real
LEADTOOLS-produced file. What *does* carry real data: `PageNumber`/`Size` (the
actual page geometry), `Points`/`RotateCenter` (the annotation's rectangle),
`Labels/Label/Text` (the annotation's text label), `Stroke`'s color (the
annotation's `color`), and `Metadata/Item[Key=Content]/Value` (the
annotation's `value`, e.g. a manually-corrected extracted-field value) — the
`Content` slot was chosen because it's the template's most semantically
fitting place for "the content associated with this annotation," not because
the original schema defines it that way.

**Coordinate scale is an inferred assumption, not a spec.** The one sample
this was built against has a Letter-size (8.5in × 11in) page reported as
6120×7920 units at `CalibrationUnit=Inch` — exactly 720 units/inch, i.e. 10x
PyMuPDF's 72-points/inch space. `app/services/ann_xml_export.py` applies that
`* 10` factor to all page and annotation geometry uniformly
(`LEAD_UNITS_PER_POINT`). It's internally consistent and reproduces that one
sample's numbers exactly, but wasn't verified against LEADTOOLS' own SDK or
documentation for other calibration units/scales.

**Guid** is the one field that's fabricated rather than left empty, because a
well-formed GUID is structurally required and this port doesn't otherwise
track one per annotation: it's derived deterministically from
`(document_id, page, index)` via `uuid5`, so re-exporting the same document
produces the same Guids across calls without needing a schema change to
`AnnotationObject`.

## Multi-criteria search

The search bar combines free text with a **Select concepts** dropdown
(`#concept-dropdown` in `web/index.html`) listing every concept as a
checkbox, grouped into:

- **Regex concepts** (Email, Phone, DOB, Visit Date, Chase ID) — plain pattern
  matching, no model involved (`app/services/concepts_registry.py` +
  `app/services/regex_concepts.py`). DOB and Visit Date share one date-shaped
  pattern since regex alone can't distinguish their semantics; Chase ID has no
  universal standard format, so it defaults to a generic placeholder pattern
  overridable via `DOCSVC_CHASE_ID_REGEX` without touching code.
- **AI-assisted · NER** (Person / member name, Any date, Diagnosis / condition,
  Medication, Quality measure, Submeasure, Vitals) — zero-shot entity
  extraction via [GLiNER2](https://github.com/fastino-ai/GLiNER2) (fastino-ai,
  Apache-2.0), one arbitrary text label per concept (e.g. "healthcare quality
  measure name") passed straight to the model — no fine-tuning or training
  data needed. Most use the sidecar's default confidence threshold, but a
  concept can override it (`NerConcept.threshold` in `concepts_registry.py`)
  — Vitals needed a lower one (`0.25` vs. the `0.4` default) to reliably fire.

Clicking **Search** sends the text query (if any) plus every checked concept
id to `Factory/SearchMultiCriteria` as one combined **AND** search: only
pages where *every* selected criterion has at least one match are returned,
with all their matched boxes on those pages highlighted together
(`app/services/multi_criteria_search.py`). The single-criterion
`Factory/SearchConcept` and `Factory/SearchDocument` endpoints still exist
underneath it and remain independently callable/tested — the dropdown is a
composition on top, not a replacement.

**Why GLiNER2 runs as a separate process (`ner_service/`), not inside this
app:** the `gliner2` PyPI package requires Python 3.10+, while this app's own
`.venv` is pinned to Python 3.9. Rather than upgrading the whole app's
interpreter for one feature, `ner_service/` is a small standalone FastAPI app
with its own Python 3.10+ venv, and the main app talks to it over localhost
HTTP (`app/services/ner_client.py`, pointed at `DOCSVC_NER_SERVICE_URL`,
default `http://127.0.0.1:8801`). See `ner_service/README.md` for setup.

If the sidecar isn't running, `Factory/ListConcepts` reports
`ner_available: false` and the viewer grays out the AI-assisted pills instead
of letting a click fail — the REGEX CONCEPTS pills and plain text search work
regardless. The sidecar loads its model at startup rather than on the first
request (a cold load measured ~25s — see `ner_service/README.md`), so it
also reports as unavailable for the ~20-30s it takes to start up the first
time.

**Mapping entity/match text back to a page location:** neither regex matches
nor GLiNER2's entity spans can be safely relocated with `page.search_for`
(PyMuPDF's own exact-substring search) once the matched text isn't unique on
the page — a repeated name or date would resolve to the wrong occurrence.
`app/services/page_text_index.py` instead builds one text-with-word-boxes
index per page and maps any `(start, end)` char span back to a bounding box by
unioning the covered words' boxes; `search_text.py`, `regex_concepts.py`, and
`ner_search.py` all share it.

**PHI handling:** the text sent to the sidecar, and the entities it returns,
are raw page content from whatever document is loaded — potentially real
patient names, DOB, diagnoses, medications. Neither `app/services/ner_client.py`
nor `ner_service/main.py` logs request/response bodies or entity text, and
extraction results aren't persisted anywhere beyond the request/response
cycle (no disk cache, unlike the uploaded document itself). Keep it that way
if you touch either file. This is a local proof-of-concept with no auth (see
**Honest limitations** below) — don't point it at real PHI outside a
controlled/local environment.

## Honest limitations vs. the original

- **Annotation format is not compatible.** LEADTOOLS' `.ann` XML
  (`leadtools.annotations.engine`) supports a large object model (freehand ink,
  stamps, redaction, encryption, hyperlinks, grouping, ...). This port defines a
  minimal JSON schema (`AnnotationObject` in [app/models.py](app/models.py)) covering
  only rectangles and text labels.
- **No OCR.** `Page/GetText` reads the PDF's embedded text layer via PyMuPDF.
  Scanned/image-only pages return empty text — LEADTOOLS' OCR engine integration
  isn't ported.
- **`to-pdf` and any non-PDF input require LibreOffice installed separately**
  (`brew install --cask libreoffice` on macOS, `apt-get install libreoffice` on
  Debian/Ubuntu). It's an external binary invoked via subprocess, not a pip
  package — the same approach tools like Gotenberg use.
- **Conversion fidelity will differ** from LEADTOOLS' (or Word's) layout engine —
  expect font substitution and minor pagination differences on complex documents.
- **The document cache is in-process and disk-backed under the OS temp dir**
  (`app/services/cache_store.py`), not a distributed/Ehcache-backed store like the
  original. It won't survive a process restart and doesn't support multiple
  named caches or cache-routing policies.
- **`Factory/LoadFromUri` fetches server-side and has a best-effort SSRF guard
  only** (http/https-only, resolves the host and blocks private/loopback/link-local
  ranges, redirects disabled). It does not defend against DNS rebinding or a
  target that itself proxies to an internal address — harden before exposing this
  to untrusted callers.
- **Field names are snake_case** (Python convention) in JSON request/response
  bodies, not wire-compatible with the original camelCase contract. GET query
  params are the exception — those keep the original names.
- **No auth.** The original's `AuthFilter`/user-token handling isn't ported;
  every endpoint here is unauthenticated. Don't deploy this as-is.
- **No OCR, forms recognition, general barcode reading, DICOM, or SharePoint
  integration** — those are separate LEADTOOLS modules/controllers (`Structure`,
  `Page.ReadBarcodes`, `SharePoint`, etc.), out of scope for this PoC. QR code
  generation/detection specifically *is* ported — see the `qrcode` section above.
- **`/convert/to-pdf-path` takes a server-local file path**, same as the original
  Java endpoint. Don't expose it to untrusted input without path/allowlist
  validation — that gap exists in the original too.
- **`Factory/SearchDocument`'s `regex=true` flag runs unvalidated caller-supplied
  patterns through Python's `re` with no execution timeout** — a pathological
  pattern is a ReDoS risk. Bounded to one page's text per match attempt, and
  this is already an unauthenticated single-user local PoC (see below), so no
  guard was added; harden this (a regex complexity check or a timeout) before
  exposing it to untrusted callers.

## Running

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8811
```

Then open **http://127.0.0.1:8811/viewer/** in a browser.

## Browser viewer

`web/` is a small vanilla HTML/JS/CSS page (no build step, no framework) mounted
at `/viewer` by `app/main.py`, calling this port's own API directly:

- Upload a file (chunked-upload flow: `BeginUpload` → `UploadDocumentBlob` →
  `EndUpload`)
- Page through it via a thumbnail strip (`Page/GetThumbnail`) and a main image
  view (`Page/GetImage`)
- See the page's extracted text (`Page/GetText`)
- Click-drag on the page to draw a rectangle annotation, label it, and it's
  saved/reloaded via `Page/SetAnnotations` / `GetAnnotations`. Existing boxes
  are adjustable afterward: drag the body to move, drag the bottom-right handle
  to resize, click the × to delete — each commits back to `SetAnnotations`
  immediately (index-based identity within the page's annotation array, fine
  for this single-user local demo)
- Zoom in/out, which re-fetches the page image at a different `resolution`
  (`Page/GetImage`'s existing DPI-like parameter) rather than CSS-scaling a
  fixed bitmap — text stays sharp at any zoom level
- Search the whole document for a text string and/or any number of concepts
  picked from the **Select concepts** dropdown (`Factory/SearchMultiCriteria`)
  — all selected criteria must match on a page (AND) — with clickable
  per-page match counts and yellow highlight boxes on the matched page, plus
  Case sensitive / Whole word / Regex checkboxes for the text part. See
  **Multi-criteria search** above
- Extract each labeled annotation's underlying page text as a key/value pair
  (`Factory/ExtractAnnotatedFields`), shown in an editable table: Label and
  Value are both `<input>`s, with a 💾 save button (enabled only once a value
  actually changes) that commits via `Factory/UpdateAnnotatedField` — editing
  Label renames the annotation itself; editing Value stores a manual
  correction that future extractions return as-is instead of recomputing it
  from the page. A **Download JSON** button does a client-side `Blob` download
  of the already-fetched result (no extra backend round-trip), and a 👁 button
  per row jumps to that field's page, scrolls it into view, and pulses a
  highlight over its exact bounding box. The 📤 button next to Download JSON
  exports the document's annotations as LEADTOOLS-`.ann`-shaped XML
  (`Factory/DownloadAnnotationsXml`) instead of the JSON schema above — see
  **LEADTOOLS-shaped annotation XML export** above
- Collapse/expand toggles (▾/▸) on the Page text, QR codes, and Generate QR
  code panels, plus the page navigator (thumbnail strip) — each just hides its
  body and flips the arrow; the thumbnail strip additionally collapses its grid
  column so the page view gets the reclaimed width
- Detect QR codes in the uploaded file (`qrcode/detect`), or generate one from
  arbitrary text (`qrcode/generate`)
- Download the document back out (`Factory/DownloadDocument`), or as a single
  PDF with the annotations burned in (`Factory/DownloadAnnotatedDocument`)

**Why this exists instead of running the actual `DocumentViewerDemo`:** that
demo's `index.html` depends on LEADTOOLS' own compiled client SDK
(`Leadtools.Document.Viewer.js`, `Leadtools.Document.js`,
`Leadtools.Annotations.Engine.js`, etc.), which its build script pulls from
`LEADTOOLS_22/Bin/JS` — a path that doesn't exist in this checkout. There's no
`Leadtools*.js` file anywhere in `LEADTOOLS_22`, so the actual frontend logic
was never included in this export; only the demo's own UI-wiring TypeScript
(`ts/Main/*.ts`) is present, and that alone doesn't do anything without the
missing library. Even with that library in hand, it speaks a fixed proprietary
wire format (camelCase JSON, SVG-based page rendering, `.ann` XML annotations)
that this port intentionally diverges from (see **Honest limitations** below),
so wiring it up for real would mean building a compatibility adapter, not just
pointing `serviceConfig.json` at a new host.

Two UI bugs found while building this, both fixed:
- The annotation editor initially used `window.prompt()` for the label input,
  which throws in some embedded/automated browser contexts (and is generally
  poor UX/often blocked) — it's now a small inline input rendered in the
  annotation layer instead (see `showLabelEditor` in `web/app.js`).
- Zoom in/out repeatedly divides/multiplies the resolution by 1.25, which
  produces fractional values (e.g. `61.44`); `Page/GetImage`'s `resolution`
  query param is a strict server-side `int`, so an unrounded value was silently
  rejected with a 422 and the image just stopped updating. `setResolution()` in
  `web/app.js` now rounds before using it.

## Trying it against the original LEADTOOLS demo's sample files

```bash
SAMPLES=/Users/srihariakula/Downloads/mrr/LEADTOOLS_22/codebase/document-service/src/main/webapp/Samples

# docx -> pdf (needs LibreOffice installed)
curl -X POST http://127.0.0.1:8811/convert/to-pdf \
  -F "file=@$SAMPLES/ClientInfoSheet.docx" -o out.pdf

# rotate page 2 by 90 degrees, draw a rectangle + label on page 1, get a zip of JPEGs
curl -X POST http://127.0.0.1:8811/convert/embed-and-convert \
  -F "file=@$SAMPLES/W9.pdf" \
  -F 'annotations=[{"page":1,"type":"rect","x":50,"y":50,"width":200,"height":40}]' \
  -F 'rotation={"2":90}' \
  -o result.zip

# upload -> view pages -> get text -> annotate -> download (the viewer flow)
UPLOAD_URI=$(curl -s -X POST http://127.0.0.1:8811/Factory/BeginUpload -d '{}' \
  -H "Content-Type: application/json" | python3 -c "import sys,json; print(json.load(sys.stdin)['upload_uri'])")

curl -s -X POST http://127.0.0.1:8811/Factory/UploadDocumentBlob \
  -F "uri=$UPLOAD_URI" -F "file=@$SAMPLES/W9.pdf" -o /dev/null

DOC_ID=$(curl -s -X POST http://127.0.0.1:8811/Factory/EndUpload \
  -H "Content-Type: application/json" -d "{\"uri\":\"$UPLOAD_URI\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['document_id'])")

curl "http://127.0.0.1:8811/Page/GetImage?documentId=$DOC_ID&pageNumber=1" -o page1.jpg
curl "http://127.0.0.1:8811/Page/GetThumbnail?documentId=$DOC_ID&pageNumber=1" -o thumb1.jpg
curl -X POST http://127.0.0.1:8811/Page/GetText -H "Content-Type: application/json" \
  -d "{\"document_id\":\"$DOC_ID\",\"page_number\":1,\"build_text\":true}"

# QR code: generate a PNG, then detect it back
curl -X POST http://127.0.0.1:8811/qrcode/generate -H "Content-Type: application/json" \
  -d '{"qrcode":"https://example.com"}' -o qr.png

curl -X POST http://127.0.0.1:8811/qrcode/detect -F "file=@qr.png"

# detect against LEADTOOLS' own multi-QR sample (decodes all 4 codes on one page)
curl -X POST http://127.0.0.1:8811/qrcode/detect -F "file=@$SAMPLES/barcodes.pdf"
```

## Tests

```bash
pytest tests/ -v
```

- `tests/test_embed_convert.py` covers the rotate + annotate + zip pipeline against
  a synthetic in-memory PDF (no LibreOffice dependency, runs anywhere).
- `tests/test_factory_and_page.py` covers the upload/cache lifecycle (including a
  path-traversal rejection test on `documentId`), the Page viewing endpoints,
  `DownloadAnnotatedDocument` (asserts the returned PDF has real `Square`/`FreeText`
  annotation objects on the right pages, not just an unchanged copy of the source),
  `ExtractAnnotatedFields` (asserts labeled annotations resolve to the real
  underlying text, unlabeled ones are excluded, and the returned `index` is the
  position in the full per-page array rather than the filtered list),
  `UpdateAnnotatedField` (asserts label/value edits persist and an override
  value wins over recomputing from the page, plus the out-of-range-index 400),
  and `SearchDocument` (asserts matches and their bounding boxes, and the
  empty-result case).
- `tests/test_qrcode.py` covers generate→detect round-trips and a two-QR-codes-
  on-one-page detection case (the scenario that motivated unioning OpenCV's two
  detection APIs).
- `tests/test_concepts.py` covers the regex concepts (`email`, `chase_id`),
  `SearchDocument`'s case-sensitive/whole-word/regex flags (including the
  invalid-regex 400), `ListConcepts`/`SearchConcept`, `SearchMultiCriteria`'s
  AND intersection (including the no-overlap-across-pages case and the
  no-criteria-given 400), and the `DownloadAnnotationsXml` export (node
  shape, real-data fields mapped correctly, empty-page-has-no-`<Object>`, and
  the live endpoint). The
  AI-assisted NER path isn't covered here since it needs `ner_service/`
  running — see **AI-assisted NER (GLiNER2)** above; it was instead verified
  manually against a real GLiNER2 model and sidecar process (see that
  section).
