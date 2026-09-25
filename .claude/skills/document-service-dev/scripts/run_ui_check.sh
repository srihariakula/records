#!/usr/bin/env bash
# Full browser check of the viewer: starts the app (:8811) and the fake GLiNER2
# sidecar (:8801), runs ui_smoke_test.js with the sidecar up, stops it, runs the
# "sidecar down" checks, then shuts everything down. Exit code is non-zero if
# any check fails.
#
# Usage: run_ui_check.sh [WORK_DIR]
#   WORK_DIR defaults to a fresh temp dir; screenshots (1-dropdown.png,
#   2-ner-medication.png, 3-ner-page2.png, 4-narrow.png, 5-sidecar-down.png)
#   are written there -- look at them, don't just trust PASS lines.
set -uo pipefail

SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
REPO="$(git -C "$SCRIPTS" rev-parse --show-toplevel)"
WORK_DIR="${1:-$(mktemp -d)}"
mkdir -p "$WORK_DIR"
export WORK_DIR NER_LABEL_LOG="$WORK_DIR/ner_labels.log"
# Chromium can't save non-ASCII download names under a non-UTF-8 locale and
# falls back to "download"; keep the download-name checks meaningful.
export LANG=C.UTF-8 LC_ALL=C.UTF-8
CHROMIUM="${CHROMIUM_PATH:-/opt/pw-browsers/chromium}"

if [ ! -d "$WORK_DIR/node_modules/playwright-core" ]; then
  (cd "$WORK_DIR" && npm init -y >/dev/null 2>&1 && npm i -s playwright-core >/dev/null 2>&1) || { echo "npm install playwright-core failed"; exit 2; }
fi
export NODE_PATH="$WORK_DIR/node_modules"

# 2-page sample: page 1 has an email + Metformin/Diabetes, page 2 has
# Lisinopril/Hypertension and no email (the AND-with-concept check relies on it).
python3 -W ignore - <<EOF
import pymupdf
d = pymupdf.open()
d.new_page().insert_text((50, 72), "Member: Jane Doe\nEmail: jane@example.com\nDiagnosis: Type 2 Diabetes\nMedication: Metformin 500mg", fontsize=12)
d.new_page().insert_text((50, 72), "Diagnosis: Hypertension\nMedication: Lisinopril 10mg", fontsize=12)
d.save("$WORK_DIR/sample.pdf")
# Non-PDF uploads for the any-format conversion checks.
from PIL import Image, ImageDraw
def page(text):
    im = Image.new("RGB", (850, 1100), "white"); ImageDraw.Draw(im).text((60, 60), text, fill="black"); return im
page("PNG upload").save("$WORK_DIR/sample.png")
frames = [page(f"TIFF page {i}") for i in (1, 2, 3)]
frames[0].save("$WORK_DIR/sample.tif", save_all=True, append_images=frames[1:])
open("$WORK_DIR/unsupported.bin", "wb").write(bytes(range(256)) * 4)
# A "scanned" page (text flattened to pixels) for the OCR check.
s = pymupdf.open(); sp = s.new_page(width=612, height=792)
for i, line in enumerate(["HEMOGLOBIN A1C 7.6 H", "Patient: Nguyen, Thomas", "Medication: Metformin 500mg"]):
    sp.insert_text((72, 100 + 40 * i), line, fontsize=18)
sp.get_pixmap(dpi=200, colorspace=pymupdf.csGRAY).save("$WORK_DIR/scan.png")
EOF
# OCR checks only make sense where tesseract is installed.
if command -v tesseract >/dev/null; then export OCR_EXPECTED=1; else export OCR_EXPECTED=0; fi

cleanup() { kill "${APP_PID:-}" "${NER_PID:-}" 2>/dev/null; }
trap cleanup EXIT

(cd "$SCRIPTS" && exec python3 -m uvicorn fake_ner_sidecar:app --port 8801 >"$WORK_DIR/ner.log" 2>&1) &
NER_PID=$!
(cd "$REPO" && PYTHONDONTWRITEBYTECODE=1 exec python3 -m uvicorn app.main:app --port 8811 >"$WORK_DIR/app.log" 2>&1) &
APP_PID=$!
for _ in $(seq 60); do
  curl -sf localhost:8811/health >/dev/null && curl -sf localhost:8801/health >/dev/null && break
  sleep 0.5
done

export CHROMIUM_PATH="$CHROMIUM"
echo "===== NER sidecar UP ====="
node "$SCRIPTS/ui_smoke_test.js" up; UP=$?

kill "$NER_PID" 2>/dev/null; wait "$NER_PID" 2>/dev/null; NER_PID=
echo "===== NER sidecar DOWN ====="
node "$SCRIPTS/ui_smoke_test.js" down; DOWN=$?

echo "Screenshots + logs: $WORK_DIR"
[ "$UP" -eq 0 ] && [ "$DOWN" -eq 0 ]
