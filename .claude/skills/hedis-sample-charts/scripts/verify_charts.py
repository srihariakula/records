"""Verify generated sample charts the way the app will actually use them.

For each .docx it:
  1. uploads it through the app's own Factory flow (BeginUpload ->
     UploadDocumentBlob -> EndUpload), which converts it with LibreOffice, and
     checks the page count and that page 1 renders;
  2. text-searches each expected evidence string and reports the pages it
     was found on (missing evidence = failure);
  3. renders every page to PNG and writes one contact sheet per chart to
     --render-dir so you can eyeball the layout against CBP.pdf.

Run from the repo root (needs requirements.txt + libreoffice-writer):
  python3 .claude/skills/hedis-sample-charts/scripts/verify_charts.py \
      samples/CBP.docx samples/GSD.docx --render-dir /tmp/charts \
      --expect CBP="136/84" --expect CBP="Essential (primary) hypertension" \
      --expect GSD="HEMOGLOBIN A1C"
Exit code is non-zero if any upload, render or expected string fails.
"""
import argparse
import io
import os
import sys
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True
sys.path.insert(0, os.getcwd())

import pymupdf  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.main import app  # noqa: E402


def contact_sheet(pdf_bytes: bytes, out_path: Path) -> None:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    pages = [Image.open(io.BytesIO(p.get_pixmap(dpi=70).tobytes("png"))) for p in doc]
    sheet = Image.new("RGB", (sum(p.width for p in pages) + 10 * (len(pages) - 1), max(p.height for p in pages)), "#888")
    x = 0
    for p in pages:
        sheet.paste(p, (x, 0))
        x += p.width + 10
    sheet.save(out_path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--render-dir", default=None)
    ap.add_argument("--expect", action="append", default=[], metavar="MEASURE=TEXT")
    args = ap.parse_args()

    expected = defaultdict(list)
    for item in args.expect:
        measure, _, text = item.partition("=")
        expected[measure.upper()].append(text)

    client = TestClient(app)
    failed = False
    for f in map(Path, args.files):
        measure = f.stem.upper()
        uri = client.post("/Factory/BeginUpload", json={"name": f.name}).json()["upload_uri"]
        with f.open("rb") as fh:
            client.post("/Factory/UploadDocumentBlob", data={"uri": uri}, files={"file": (f.name, fh)})
        doc = client.post("/Factory/EndUpload", json={"uri": uri}).json()
        doc_id, pages = doc["document_id"], doc.get("page_count", 0)
        img = client.get("/Page/GetImage", params={"documentId": doc_id, "pageNumber": 1})
        ok = pages > 0 and img.status_code == 200
        line = [f"{f.name}: {pages} page(s), page 1 image {img.status_code}"]
        if not ok:
            line.append("CONVERSION FAILED (is libreoffice-writer installed?)")
        for text in expected.get(measure, []):
            r = client.post("/Factory/SearchMultiCriteria", json={"document_id": doc_id, "query": text}).json()
            hit = ",".join(r["matches"].keys())
            ok &= bool(hit)
            line.append(f"{text!r}->p{hit}" if hit else f"{text!r}->MISSING")
        if args.render_dir and pages:
            Path(args.render_dir).mkdir(parents=True, exist_ok=True)
            pdf = client.get("/Factory/DownloadAnnotatedDocument", params={"documentId": doc_id}).content
            contact_sheet(pdf, Path(args.render_dir) / f"sheet-{f.stem}.png")
        client.post("/Factory/Delete", json={"document_id": doc_id, "allow_non_existing": True})
        failed |= not ok
        print(("PASS  " if ok else "FAIL  ") + " | ".join(line))
    if args.render_dir:
        print(f"contact sheets: {args.render_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
