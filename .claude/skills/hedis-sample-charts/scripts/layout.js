// Renders a synthetic chart in the same format as the CBP.pdf sample:
//   page header  -> "Last, First - (DOB: ..)", Date of Visit, Gender, MRN, PROVIDER
//   body         -> "Section -" headings, "Sub:" headings, "Label: value" lines,
//                   "Comment:" + text, lab/vitals grids (one column per date),
//                   "Test: value-date - Status" lines, "Problem List -"
//   page footer  -> "Doc ID: ..." / "Page X of Y   Printed: ..."
// Each encounter becomes its own docx section so it can carry its own
// Date of Visit / provider in the header, like a multi-visit chart print.
const fs = require('fs');
const crypto = require('crypto');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType,
  BorderStyle, Header, Footer, PageNumber, LevelFormat, AlignmentType, TabStopType, PageBreak,
} = require('docx');

const FONT = 'Arial';
const PAGE_W = 12240, MARGIN = 1080, CONTENT_W = PAGE_W - 2 * MARGIN;

const run = (text, o = {}) => new TextRun({ text, font: FONT, size: o.size || 19, bold: o.bold, italics: o.italics, color: o.color });
const para = (children, o = {}) => new Paragraph({
  children: Array.isArray(children) ? children : [children],
  spacing: { before: o.before ?? 0, after: o.after ?? 40 }, keepNext: o.keepNext, tabStops: o.tabStops,
});

const mrnFor = (p) => crypto.createHash('md5').update(`${p.name}|${p.dob}`).digest('hex').toUpperCase();

const noBorder = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
const hair = { style: BorderStyle.SINGLE, size: 2, color: 'BFBFBF' };

// Lab/vitals grid: first column is the test name, then one column per date.
function grid(headers, rows) {
  const first = 3000;
  const rest = Math.floor((CONTENT_W - first) / (headers.length - 1));
  const widths = [first, ...Array(headers.length - 1).fill(rest)];
  const cell = (text, w, bold) => new TableCell({
    width: { size: w, type: WidthType.DXA },
    borders: { top: noBorder, left: noBorder, right: noBorder, bottom: hair },
    margins: { top: 20, bottom: 20, left: 60, right: 60 },
    children: [para(run(String(text ?? ''), { bold, size: 17 }), { after: 0 })],
  });
  return new Table({
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, widths[i], true)) }),
      ...rows.map((r) => new TableRow({ cantSplit: true, children: headers.map((_, i) => cell(r[i], widths[i], i === 0)) })),
    ],
  });
}

// Block types:
//   { section: 'Physical Exam' }        -> "Physical Exam -"
//   { sub: 'Lungs' }                    -> "Lungs:"
//   { kv: [['Status', 'Normal'], ...] } -> "Status: Normal"
//   { comment: '...' , label? }         -> "Comment:" then the text
//   { text: '...' }                     -> plain line
//   { grid: { headers, rows } }         -> date-column table
//   { status: ['KT/V: 1.50-10/10/17 - Satisfactory', ...] }
//   { bullets: [...] }
//   { problems: [['Type 2 diabetes mellitus', 'comment'], ...] } -> "Dx : comment"
//   { pageBreak: true }
function renderBlocks(blocks) {
  const out = [];
  for (const b of blocks) {
    if (b.section) out.push(para(run(`${b.section} - `, { bold: true, size: 22 }), { before: 220, after: 100, keepNext: true }));
    if (b.sub) out.push(para(run(`${b.sub}:`, { bold: true }), { before: 140, after: 30, keepNext: true }));
    if (b.kv) for (const [l, v] of b.kv) out.push(para([run(`${l}: `), run(v)]));
    if (b.comment !== undefined) {
      out.push(para(run(`${b.label || 'Comment'}:`), { keepNext: true, after: 0 }));
      out.push(para(run(b.comment)));
    }
    if (b.text) out.push(para(run(b.text)));
    if (b.grid) { out.push(grid(b.grid.headers, b.grid.rows)); out.push(para(run(''), { after: 60 })); }
    if (b.status) for (const s of b.status) out.push(para(run(s)));
    if (b.bullets) for (const t of b.bullets) out.push(new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 30 }, children: [run(t)] }));
    if (b.problems) for (const [dx, c] of b.problems) out.push(para([run(`${dx} : `, { bold: true }), run(c)], { after: 80 }));
    if (b.pageBreak) out.push(new Paragraph({ children: [new PageBreak()] }));
  }
  return out;
}

function headerFor(patient, enc) {
  const line = (t, bold) => para(run(t, { bold, size: 18 }), { after: 0 });
  return new Header({ children: [
    line(`${patient.name} - (DOB: ${patient.dob})`, true),
    line(`Date of Visit: ${enc.visitDate}`),
    line(`Gender: ${patient.gender}`),
    line(`MRN: ${mrnFor(patient)}`),
    line(enc.provider, true),
    new Paragraph({ spacing: { after: 0 }, border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: '808080', space: 2 } }, children: [] }),
  ] });
}

function footerFor(spec) {
  return new Footer({ children: [
    new Paragraph({ spacing: { after: 0 }, border: { top: { style: BorderStyle.SINGLE, size: 4, color: '808080', space: 2 } }, children: [] }),
    para(run(`Doc ID: ${spec.docId}`, { size: 17 }), { after: 0 }),
    para([
      new TextRun({ children: ['Page ', PageNumber.CURRENT, ' of ', PageNumber.TOTAL_PAGES], font: FONT, size: 17 }),
      run(`\tPrinted: ${spec.printed}`, { size: 17 }),
    ], { after: 0, tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W }] }),
    para(run('Synthetic sample record for testing - fictitious patient and provider, not PHI.', { size: 13, italics: true, color: '8C8C8C' }), { after: 0 }),
  ] });
}

async function buildChart(spec, outPath) {
  const footer = footerFor(spec);
  const sections = spec.encounters.map((enc, i) => ({
    properties: {
      page: { size: { width: PAGE_W, height: 15840 }, margin: { top: 1900, bottom: 1300, left: MARGIN, right: MARGIN, header: 500, footer: 400 } },
    },
    headers: { default: headerFor(spec.patient, enc) },
    footers: { default: footer },
    children: [
      ...renderBlocks(enc.blocks),
      para(run(`Electronically Signed by: ${enc.provider} on ${enc.signedAt}`, { bold: true }), { before: 280 }),
    ],
  }));
  const doc = new Document({
    creator: 'document-service-py samples',
    title: `${spec.measure} sample record (synthetic)`,
    subject: `${spec.measureName} (${spec.measure})`,
    description: 'Synthetic chart for HEDIS medical record abstraction testing. Fictitious patient; not PHI.',
    styles: { default: { document: { run: { font: FONT, size: 19 } } } },
    numbering: { config: [{ reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 500, hanging: 250 } } } }] }] },
    sections,
  });
  fs.writeFileSync(outPath, await Packer.toBuffer(doc));
}

module.exports = { buildChart, mrnFor };
