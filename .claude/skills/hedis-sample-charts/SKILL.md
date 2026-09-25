---
name: hedis-sample-charts
description: Generate synthetic HEDIS / CMS quality-measure sample medical records (.docx) in the same chart format as the repo's CBP.pdf sample, one per measure (CBP, COA, GSD, PPC, TRC, WCC already exist in samples/; BPD, EED, CCS, COL, BCS etc. can be added). Each chart holds the record evidence its measure is abstracted for, so it can drive upload, search, NER and field-extraction testing. Use this whenever someone asks for sample charts, test documents, mock medical records, abstraction test data, or "a document like CBP" for any measure, or wants existing samples changed or regenerated.
---

# Synthetic HEDIS sample charts

The samples in `samples/*.docx` are generated from `scripts/specs.js` (the content) by `scripts/layout.js` (the CBP-style format) via `scripts/build.js`. Edit the spec and rebuild; don't hand-edit the `.docx` files.

## The format (it must match CBP.pdf)

The user supplied `CBP.pdf` as the reference and asked for this exact look:

- **Page header, repeated on every page:**
  - `Last, First - (DOB: mm/dd/yyyy)`
  - `Date of Visit: mm/dd/yyyy`
  - `Gender: ...`
  - `MRN: <32 hex chars>`
  - `PROVIDER NAME, MD`
- **Body:**
  - `Section - ` headings and `Sub:` headings;
  - `Label: value` lines;
  - a `Comment:` line followed by the text;
  - lab and vitals grids: the test name, then one column per date, newest first, with `H`/`L` flags;
  - status lines like `HbA1c: 7.6 H-09/18/24 - Improved`;
  - `Problem List -` entries as `Diagnosis (ICD-10) : comment`;
  - `Electronically Signed by: NAME, MD on mm/dd/yyyy hh:mm AM`.
- **Page footer:** `Doc ID: ########`, then `Page X of Y` with `Printed: mm/dd/yyyy`, plus a small italic "synthetic, not PHI" line.
- **Multi-visit charts** (PPC, TRC) put one encounter per docx section, so each visit's header shows its own Date of Visit.

`layout.js` renders all of this from simple blocks (`section`, `sub`, `kv`, `comment`, `text`, `grid`, `status`, `bullets`, `problems`, `pageBreak`); its header comment documents the block types. The MRN is derived from name + DOB, so it stays stable across rebuilds.

## Content rules

1. **Put in the evidence the measure is abstracted for**, with dates inside the measurement year (2024 unless asked otherwise). `references/measures.md` lists the evidence for each existing chart and notes for adding others. Check the current HEDIS technical specs when the measure or year is new. Make the compliance outcome deliberate, and say in the spec comment what it is (e.g. "most recent A1c 7.6% → <8.0").
2. **Make it realistic** in the CBP style: HPI, vitals, a physical exam with `Status:` lines, labs with trends, medications, and a problem list with ICD-10 codes. Realistic distractors, like an elevated first BP before a controlled repeat, make better abstraction tests.
3. **Keep everything fictitious:** patient and provider names, facilities, IDs. Keep the footer disclaimer. Never copy details from a real record, even one the user shares as a style reference.

## Build

```bash
W=$(mktemp -d) && (cd "$W" && npm init -y >/dev/null && npm i -s docx)   # docx isn't a repo dependency
NODE_PATH="$W/node_modules" node .claude/skills/hedis-sample-charts/scripts/build.js samples            # all
NODE_PATH="$W/node_modules" node .claude/skills/hedis-sample-charts/scripts/build.js samples BPD GSD    # some
```

To add a measure, add a spec object to `specs.js` (copy the closest existing one) and include it in `module.exports`. Then add a row to `samples/README.md` and to `references/measures.md`.

## Verify (every time)

This needs `pip install -r requirements.txt` and `libreoffice-writer`; `libreoffice-core` alone can't open documents.

```bash
python3 .claude/skills/hedis-sample-charts/scripts/verify_charts.py samples/*.docx \
    --render-dir /tmp/charts --expect CBP="136/84" --expect GSD="HEMOGLOBIN A1C"   # one --expect per key evidence string
```

The script uploads each chart through the app's real Factory flow (so the LibreOffice conversion is exercised), checks that the key evidence can be found by text search, and writes one contact sheet per chart. **Look at the contact sheets** and compare them against `CBP.pdf`, checking the header, the footer and "Page X of Y", that grids aren't split badly, and that no page is empty.

For an XSD check, if the docx skill is available: `python <docx-skill>/scripts/office/validate.py samples/X.docx`. It needs `defusedxml` and `lxml`.
