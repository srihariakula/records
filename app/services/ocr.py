"""
OCR for scanned / image-only pages, via Tesseract.

Ports the role of LEADTOOLS' OCR engine integration (DocumentFactory loading
with an OCR engine attached) for this repo's needs: make scanned pages
searchable. It uses the "sandwich" approach (as OCRmyPDF does): each page
with no text layer but with images is rendered to a bitmap, Tesseract finds
the words and their pixel boxes (TSV output), a text-only page is built with
each word as invisible text stretched to exactly its box, and that page is
overlaid onto the original. (Tesseract's own text-only PDF output was tried
first, but its word widths came out up to ~10% short, so search highlights
missed the ends of words.) The page looks exactly the
same, but now has a real text layer, so everything downstream that reads
PDF text -- Page/GetText, SearchDocument, regex concepts, NER, extracted
fields -- works on scans without any changes of its own.

OCR is best-effort: if Tesseract isn't installed, is disabled, or fails on a
page, the page is simply left image-only (conversion never fails because of
OCR). Pages that already have text are never touched.

Config (env vars):
  DOCSVC_OCR            "auto" (default: OCR when tesseract is on PATH) or "off"
  DOCSVC_OCR_LANG       Tesseract language(s), default "eng" (e.g. "eng+spa";
                        each needs its tesseract-ocr-<lang> package)
  DOCSVC_OCR_DPI        render resolution for OCR, default 300
  DOCSVC_OCR_MAX_PAGES  cap per document, default 200
  DOCSVC_OCR_TIMEOUT    seconds per page, default 120

PHI note: OCR output is raw page content. Nothing here logs recognized text,
and the temporary page images are deleted as soon as each page is done.
"""
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import fitz  # PyMuPDF

OCR_MODE = os.environ.get("DOCSVC_OCR", "auto").strip().lower()
OCR_LANG = os.environ.get("DOCSVC_OCR_LANG", "eng")
OCR_DPI = int(os.environ.get("DOCSVC_OCR_DPI", "300"))
OCR_MAX_PAGES = int(os.environ.get("DOCSVC_OCR_MAX_PAGES", "200"))
OCR_TIMEOUT_SECONDS = int(os.environ.get("DOCSVC_OCR_TIMEOUT", "120"))

# Pages whose images cover less than this share of the page are logos or
# signatures on an otherwise-empty page, not scans; skip them.
_MIN_IMAGE_COVERAGE = 0.10
# Fax servers and scanners stamp a line of real text (header, page number) on
# top of the scanned image, so "has any text" can't be the test on its own: a
# page that's mostly image with only a little text is still a scan.
_STAMP_MAX_CHARS = 100
_STAMPED_SCAN_MIN_COVERAGE = 0.50


@dataclass
class OcrResult:
    pdf_bytes: bytes
    ocr_pages: int  # pages that got a text layer added


@lru_cache(maxsize=1)
def _tesseract() -> Optional[str]:
    return shutil.which("tesseract")


def is_available() -> bool:
    return OCR_MODE != "off" and _tesseract() is not None


def page_needs_ocr(page: "fitz.Page") -> bool:
    """Images covering a meaningful part of the page, and no text layer (or
    just a stamped header on an otherwise-scanned page)."""
    text_chars = len("".join(page.get_text("text").split()))
    if text_chars > _STAMP_MAX_CHARS:
        return False
    page_area = abs(page.rect)
    if not page_area:
        return False
    covered = sum(abs(fitz.Rect(info["bbox"]) & page.rect) for info in page.get_image_info())
    coverage = covered / page_area
    return coverage >= (_STAMPED_SCAN_MIN_COVERAGE if text_chars else _MIN_IMAGE_COVERAGE)


@dataclass
class _Word:
    text: str
    left: int
    top: int
    width: int
    height: int


def _ocr_words(png_bytes: bytes) -> Optional[List[_Word]]:
    """Runs tesseract on one page image; returns its words with pixel boxes
    (None if tesseract failed)."""
    with tempfile.TemporaryDirectory(prefix="docsvc-ocr-") as tmp:
        image_path = Path(tmp) / "page.png"
        image_path.write_bytes(png_bytes)
        out_base = Path(tmp) / "page"
        try:
            result = subprocess.run(
                [_tesseract(), str(image_path), str(out_base), "-l", OCR_LANG, "--dpi", str(OCR_DPI), "tsv"],
                capture_output=True,
                timeout=OCR_TIMEOUT_SECONDS,
                # Tesseract's OpenMP threads fight each other when pages run in
                # parallel; one thread per process + a thread pool is faster.
                env=dict(os.environ, OMP_THREAD_LIMIT="1"),
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError):
            return None
        tsv = out_base.with_suffix(".tsv")
        if result.returncode != 0 or not tsv.exists():
            return None
        words = []
        # level page block par line word left top width height conf text; level 5 = word
        for row in tsv.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
            cols = row.split("\t")
            if len(cols) == 12 and cols[0] == "5" and cols[11].strip():
                left, top, width, height = map(int, cols[6:10])
                if width > 0 and height > 0:
                    words.append(_Word(cols[11].strip(), left, top, width, height))
        return words


_FONT = fitz.Font("helv")


def _text_layer_page(words: List[_Word], width: float, height: float) -> "fitz.Document":
    """A text-only page the size of the displayed page: every word as
    invisible text whose extracted box matches Tesseract's box exactly
    (font size from the box height, horizontal scale from its width)."""
    layer = fitz.open()
    page = layer.new_page(width=width, height=height)
    shape = page.new_shape()
    scale = 72.0 / OCR_DPI
    span = _FONT.ascender - _FONT.descender
    for w in words:
        x0, y0 = w.left * scale, w.top * scale
        x1, y1 = (w.left + w.width) * scale, (w.top + w.height) * scale
        fontsize = (y1 - y0) / span
        baseline = fitz.Point(x0, y1 + _FONT.descender * fontsize)
        natural = _FONT.text_length(w.text, fontsize=fontsize)
        if natural <= 0:
            continue
        shape.insert_text(baseline, w.text, fontname="helv", fontsize=fontsize, render_mode=3,
                          morph=(baseline, fitz.Matrix((x1 - x0) / natural, 1)))
    shape.commit()
    return layer


def add_text_layer(pdf_bytes: bytes) -> OcrResult:
    """Returns the PDF with an invisible OCR text layer on every image-only
    page (up to OCR_MAX_PAGES). Returns the input bytes unchanged (same
    object) when OCR is unavailable or no page needs it."""
    if not is_available():
        return OcrResult(pdf_bytes, 0)
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except (fitz.FileDataError, RuntimeError, ValueError):
        return OcrResult(pdf_bytes, 0)  # damaged PDFs are reported by the page counter, not here
    try:
        targets: List[int] = [p.number for p in doc if page_needs_ocr(p)][:OCR_MAX_PAGES]
        if not targets:
            return OcrResult(pdf_bytes, 0)

        # Render in this thread (PyMuPDF documents aren't thread-safe) and OCR in
        # parallel, a batch at a time so a long scan never holds every 300 DPI
        # page image in memory at once.
        workers = max(1, min(len(targets), os.cpu_count() or 1))
        page_words: List[Optional[List[_Word]]] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for start in range(0, len(targets), workers * 2):
                batch = targets[start:start + workers * 2]
                images = [doc[n].get_pixmap(dpi=OCR_DPI, colorspace=fitz.csGRAY).tobytes("png") for n in batch]
                page_words.extend(pool.map(_ocr_words, images))

        done = 0
        for n, words in zip(targets, page_words):
            if not words:
                continue  # tesseract failed, or a blank/unreadable page: leave it as-is
            page = doc[n]
            with _text_layer_page(words, page.rect.width, page.rect.height) as layer:
                # page.rect is in the page's displayed (rotated) orientation, the
                # same orientation the pixmap was rendered in; PyMuPDF handles
                # /Rotate itself, so no extra rotate= here (verified on a
                # 90-degree page: text lands where it is displayed).
                page.show_pdf_page(page.rect, layer, 0, overlay=True)
            done += 1
        if not done:
            return OcrResult(pdf_bytes, 0)
        return OcrResult(doc.tobytes(garbage=3, deflate=True), done)
    finally:
        doc.close()
