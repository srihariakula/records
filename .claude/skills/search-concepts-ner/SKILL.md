---
name: search-concepts-ner
description: Work on the viewer's document search in document-service-py. That covers literal text search (case, whole-word and regex flags), regex concepts in the "Select concepts" dropdown (Email, Phone, DOB, Chase ID...), the NER checkbox that sends the typed text to the GLiNER2 sidecar as an entity label, and predefined NER concepts. Use it whenever adding or changing a concept, pattern, entity label or threshold, touching Factory/SearchMultiCriteria, SearchConcept or ListConcepts, debugging wrong or missing highlights, or changing how search results map to page boxes.
---

# Search, concepts and NER

## How a search flows

Viewer (`web/app.js`, search button or Enter) → `POST /Factory/SearchMultiCriteria` with:

```json
{"document_id": "...", "query": "text or null", "case_sensitive": false,
 "whole_word": false, "use_regex": false, "use_ner": false, "concept_ids": ["email"]}
```

→ `app/services/multi_criteria_search.py` runs each criterion and keeps only the pages where **every** criterion matched (AND). On those pages it merges all the boxes. The response is `{"matches": {page: [[x0,y0,x1,y1], ...]}, "total_matches": n}`. Criteria:

- **Literal text** (`query`, NER off): `search_text.py`. Plain search uses PyMuPDF `search_for`. The case, whole-word and regex flags switch to a regex path over `page_text_index.py`.
- **NER text** (`query` with `use_ner: true`): `ner_search.find_label_matches(pdf, query)`. The typed text is the GLiNER2 zero-shot entity label ("medication", "healthcare quality measure name"); it is not matched literally. The literal flags are ignored, and the viewer disables them while NER is ticked.
- **Concept ids:** regex concepts via `regex_concepts.py`, predefined NER concepts via `ner_search.find_concept_matches`. Predefined NER concepts are **not shown in the viewer** (the dropdown is regex-only), but they remain callable by id through the API.

## Scanned pages

Scans get an invisible Tesseract text layer at upload (`app/services/ocr.py`), with each word stretched to its OCR box. Search, concepts and NER therefore work on scans unchanged. When a search misses on a scan, check `Page/GetText` for OCR misreads (e.g. `O` read as `0`) before suspecting the matcher.

## Mapping matches to boxes: always use page_text_index

Don't relocate a matched string with `page.search_for`. A repeated name or date on the same page would resolve to the wrong occurrence. Build `page_text_index.build_page_index(page)` once per page, match or extract on `index.text`, and convert each `(start, end)` char span with `index.bbox_for_range(start, end)`. Regex concepts, NER and flagged text search all share this.

## Adding a regex concept

Add a `RegexConcept(id, label, re.compile(...))` to `REGEX_CONCEPTS` in `app/services/concepts_registry.py`. That file is the single source of truth: `ListConcepts` exposes it, and the dropdown renders from it with no HTML changes. For patterns that vary by customer, read an env override the way `DOCSVC_CHASE_ID_REGEX` does. Add a test in `tests/test_concepts.py` using the in-memory PDF fixtures there, covering both a hit and a miss.

## Adding or tuning a predefined NER concept

Add `NerConcept(id, label, gliner_label, threshold=None)` to `NER_CONCEPTS`. The `gliner_label` is the literal text sent to the model, and a descriptive phrase works better than a single word. Leave `threshold` as `None` to use the global default (0.4). Lower it only when testing shows the label misses (Vitals needed 0.25).

## NER sidecar facts

- The sidecar is `ner_service/` (GLiNER2 model `fastino/gliner2.5-small-v1`, Python 3.10+, port 8801). It loads the model at startup (about 25 s cold). Until it's ready, `ListConcepts` reports `ner_available: false` and the viewer greys out the NER checkbox.
- The client is `app/services/ner_client.py`. Timeouts return 503 and error responses return 502. Pages are sent one at a time so offsets map back through that page's index.
- **Patient data:** the text sent and the entities returned are raw page content, possibly real patient data. Never log `text`, labels or entity text in `ner_client.py` or `ner_service/main.py`, and never persist extraction results.

## Testing

- **Unit tests:** monkeypatch `ner_client.extract_entities` (see the `use_ner` tests in `tests/test_concepts.py`). Assert both the label that was sent and the pages returned. Never require a live sidecar in pytest.
- **UI:** run `document-service-dev`'s `run_ui_check.sh`. Its fake sidecar logs received labels, so the test can check the exact typed text reached GLiNER2. When you add a vocabulary word or check, extend `VOCAB` in `fake_ner_sidecar.py`.
- **Real model:** results depend heavily on the label phrasing. Say so when reporting, and try it against the real sidecar when that matters.
- **Caller-supplied regex** (the literal `regex=true` path) has no timeout, which is a known ReDoS risk noted in the README. Don't widen its exposure without adding a guard.
