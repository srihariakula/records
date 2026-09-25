---
name: security-conventions
description: Security and data-handling rules for document-service-py. They cover caller-supplied file names, document ids and paths in the disk cache, Content-Disposition download headers, server-side URL fetching (SSRF), caller regexes (ReDoS), patient data (PHI) in NER traffic, and how to write tests that can't damage the filesystem. Use this whenever code touches cache_store, file paths, uploads, downloads, response headers, LoadFromUri, to-pdf-path, regex search, ner_client or ner_service, or when writing a test that creates or deletes cached documents.
---

# Security conventions

This is an unauthenticated local PoC (see the README's "Honest limitations"). The rules below still matter because each one has already caused a real bug here. Keep new code consistent with them rather than adding one-off checks.

## Caller-supplied names and ids → filesystem paths

- **`document_id`** becomes a directory: `CACHE_ROOT/<document_id>/`. It's validated by `_validate_document_id` (`^[A-Za-z0-9_-]{1,128}$`). Any new code path that takes an id must go through `cache.get`, `cache.require` or `_validate_document_id`.
- **Document `name`** (BeginUpload, UploadDocument, SaveToCache) must never be joined onto a path raw. `_safe_file_name` keeps only the final component (splitting on both `/` and `\`) and maps `""`, `.`, `..` and the reserved `rendered.pdf` to `document.bin`. Keep the original only as display data (`entry.name`).
- **Why this matters:** `cache.delete()` `rmtree`s the parent of the stored file. Before the fix, the name `../../x` made `Factory/Delete` or TTL expiry delete an arbitrary directory. It deleted all of `/tmp` during development. Anything that deletes must derive its target from validated ids, never from a stored path that came from caller input.
- `/convert/to-pdf-path` takes a server-local path by design (it mirrors the Java API). Don't expose it further without an allowlist.

## Download headers

Build every `Content-Disposition` with `app.services.content_disposition.attachment(filename)`, never with an f-string. Raw interpolation let a `"` inject a second `filename=`, passed CR/LF through, and caused a 500 on any non-Latin-1 name. The helper emits an ASCII `filename=` fallback plus an RFC 6266 `filename*=UTF-8''…`, with directory parts and control characters stripped. A constant name like `result.zip` is fine as a literal.

## Server-side fetching (SSRF)

`Factory/LoadFromUri` → `app/services/uri_fetch.py`:
- only http and https are allowed;
- the host is resolved and rejected if it's private, loopback, link-local, reserved or multicast;
- redirects are disabled;
- downloads are capped at 100 MB, with a 30 s timeout.

It doesn't stop DNS rebinding. If you add another outbound fetch, reuse `fetch_uri_bytes` rather than calling `requests` directly.

## Caller regexes

`SearchDocument` / `SearchMultiCriteria` with `use_regex` run caller patterns through `re` with no timeout. That's a known ReDoS risk, bounded to one page's text per attempt and documented in the README. Invalid patterns must return 400. Don't add new caller-regex entry points without a complexity check or timeout.

## Patient data (PHI)

Documents can hold real patient data even though the bundled samples are synthetic. `ner_client.py` and `ner_service/main.py` must never log request or response bodies, page text, labels or entity text, and extraction results are never persisted. Only uploaded documents live in the cache, and they expire by TTL. New sample files must be clearly synthetic: fictitious names, generated MRNs, and a "not PHI" footer (see `hedis-sample-charts`).

## Tests must be safe even if the fix regresses

When testing a path or deletion bug:
- Root the cache in `tmp_path`: `monkeypatch.setattr(cache_store, "CACHE_ROOT", tmp_path / "cache")`.
- Make absolute-path cases point inside `tmp_path`, never at `/` or `/tmp`.
- Clean up with `cache._entries.pop(id, None)`, not `cache.delete()`, which could `rmtree` an escaped parent.
- Prove the test catches the bug by stashing the fix and watching it fail. It must fail harmlessly.

`tests/test_factory_and_page.py::test_document_name_path_traversal_stays_inside_entry_dir` is the reference example.
