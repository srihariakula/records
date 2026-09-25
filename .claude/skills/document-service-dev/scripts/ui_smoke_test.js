// End-to-end browser check of the viewer (search bar, NER checkbox, concept
// dropdown, downloads, layout). Driven by run_ui_check.sh, which starts the
// app + fake_ner_sidecar.py and sets:
//   WORK_DIR       folder holding sample.pdf (2 pages, see run_ui_check.sh)
//   NER_LABEL_LOG  file the fake sidecar appends received labels to
//   BASE_URL       viewer URL (default http://127.0.0.1:8811/viewer/)
// Usage: node ui_smoke_test.js up|down   (sidecar running / stopped)
const { chromium } = require('playwright-core');
const fs = require('fs');
const S = process.env.WORK_DIR || __dirname, BASE = process.env.BASE_URL || 'http://127.0.0.1:8811/viewer/';
const LABEL_LOG = process.env.NER_LABEL_LOG || `${S}/ner_labels.log`;
const phase = process.argv[2] || 'up';
let pass = 0, fail = 0;
const check = (name, ok, detail = '') => { ok ? pass++ : fail++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`); };
const labels = () => fs.existsSync(LABEL_LOG) ? fs.readFileSync(LABEL_LOG, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse) : [];
const resetLabels = () => fs.existsSync(LABEL_LOG) && fs.unlinkSync(LABEL_LOG);

(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium' });
  const ctx = await b.newContext({ viewport: { width: 1400, height: 900 }, acceptDownloads: true });
  const p = await ctx.newPage();
  const errors = [];
  p.on('pageerror', e => errors.push(e.message));
  p.on('console', m => m.type() === 'error' && !/favicon|status of 404/.test(m.text() + (m.location().url || '')) && errors.push(m.text()));
  await p.goto(BASE);
  await p.waitForLoadState('networkidle');

  if (phase === 'down') {
    check('NER checkbox disabled when sidecar is down', await p.isDisabled('#search-ner'));
    check('"service isn\'t running" hint shown', (await p.getAttribute('#ner-unavailable-hint', 'hidden')) === null);
    await p.setInputFiles('#file-input', `${S}/sample.pdf`);
    await p.click('#upload-btn');
    await p.waitForSelector('#viewer:not([hidden])');
    await p.fill('#search-input', 'Metformin'); await p.click('#search-btn');
    await p.waitForFunction(() => !/Searching/.test(document.querySelector('#search-results').textContent));
    check('plain text search still works without sidecar', /Page 1: 1 match/.test(await p.textContent('#search-results')));
    await p.screenshot({ path: `${S}/5-sidecar-down.png`, clip: { x: 1060, y: 120, width: 340, height: 220 } });
    check('no JS errors', errors.length === 0, errors.join(' | '));
    console.log(`\n${pass} passed, ${fail} failed`); await b.close(); process.exit(fail ? 1 : 0);
  }

  // 1. Layout / dropdown
  const row = await p.$eval('#search-bar-row', r => [...r.children].map(c => c.id));
  check('NER checkbox sits right after the search box', row[0] === 'search-input' && row[1] === 'search-ner-label', row.join(','));
  check('NER checkbox enabled (sidecar up)', !(await p.isDisabled('#search-ner')));
  check('NER hint hidden (sidecar up)', (await p.getAttribute('#ner-unavailable-hint', 'hidden')) !== null);

  await p.setInputFiles('#file-input', `${S}/sample.pdf`);
  await p.click('#upload-btn');
  await p.waitForSelector('#viewer:not([hidden])');
  await p.waitForSelector('#page-image[src]');

  await p.click('#concept-dropdown-btn');
  const dd = (await p.textContent('#concept-dropdown-panel')).replace(/\s+/g, ' ').trim();
  check('dropdown has no AI-assisted section', !/AI-assisted|NER|Person|Medication|Vitals/i.test(dd), dd);
  check('dropdown still lists regex concepts', ['Email', 'Phone', 'DOB', 'Visit Date', 'Chase ID'].every(x => dd.includes(x)));
  await p.screenshot({ path: `${S}/1-dropdown.png`, clip: { x: 1060, y: 120, width: 340, height: 330 } });
  await p.click('#concept-dropdown-btn');

  const search = async () => {
    await p.click('#search-btn');
    await p.waitForFunction(() => !/Searching/.test(document.querySelector('#search-results').textContent));
    return (await p.textContent('#search-results')).replace(/\s+/g, ' ').trim();
  };

  // 2. Literal search, NER off -> sidecar untouched
  resetLabels();
  await p.fill('#search-input', 'Metformin');
  let res = await search();
  check('literal search (NER off) finds text', /Page 1: 1 match/.test(res), res);
  check('literal search does not call GLiNER2', labels().length === 0, JSON.stringify(labels()));

  // 3. NER on: option states + placeholder
  await p.check('#search-ner');
  const dis = await Promise.all(['#search-case-sensitive', '#search-whole-word', '#search-regex'].map(s => p.isDisabled(s)));
  check('case/whole-word/regex disabled while NER ticked', dis.every(Boolean), dis.join(','));
  check('placeholder switches to entity-type hint', /Entity type/.test(await p.getAttribute('#search-input', 'placeholder')));

  // 4. NER search: typed text is the GLiNER2 label, hits on both pages
  resetLabels();
  await p.fill('#search-input', 'medication');
  res = await search();
  const sent = labels();
  check('typed text sent to GLiNER2 as the label', sent.length === 2 && sent.every(l => l === 'medication'), JSON.stringify(sent));
  check('NER search finds entities on both pages', /Page 1: 1 match/.test(res) && /Page 2: 1 match/.test(res), res);
  check('page 1 entity highlighted', (await p.locator('#search-layer .search-highlight').count()) === 1);
  await p.screenshot({ path: `${S}/2-ner-medication.png` });
  await p.click('#search-results >> text=Page 2');
  await p.waitForFunction(() => /2/.test(document.querySelector('#page-indicator').textContent.split('/')[0]));
  await p.waitForTimeout(300);
  check('clicking Page 2 result shows its highlight', (await p.locator('#search-layer .search-highlight').count()) === 1);
  await p.screenshot({ path: `${S}/3-ner-page2.png` });

  // 5. Enter key in NER mode, different label
  resetLabels();
  await p.fill('#search-input', 'diagnosis');
  await p.press('#search-input', 'Enter');
  await p.waitForFunction(() => /Page/.test(document.querySelector('#search-results').textContent) && !/Searching/.test(document.querySelector('#search-results').textContent));
  res = (await p.textContent('#search-results')).replace(/\s+/g, ' ');
  check('Enter key runs NER search', labels().includes('diagnosis') && /Page 1/.test(res) && /Page 2/.test(res), res);

  // 6. NER AND regex concept (Email only on page 1)
  await p.click('#concept-dropdown-btn');
  await p.check('#concept-dropdown-panel input[value=email]');
  await p.click('#concept-dropdown-btn');
  await p.fill('#search-input', 'medication');
  res = await search();
  check('NER + Email concept ANDs to page 1 only', /Page 1: 2 match/.test(res) && !/Page 2/.test(res), res);
  await p.click('#concept-dropdown-btn');
  await p.uncheck('#concept-dropdown-panel input[value=email]');
  await p.click('#concept-dropdown-btn');

  // 7. NER label with no entities
  await p.fill('#search-input', 'vehicle identification number');
  res = await search();
  check('NER label with no entities shows no page hits', !/Page \d/.test(res), res);

  // 8. Untick NER -> literal behaviour restored
  await p.uncheck('#search-ner');
  const en = await Promise.all(['#search-case-sensitive', '#search-whole-word', '#search-regex'].map(s => p.isDisabled(s)));
  check('options re-enabled after unticking NER', en.every(x => !x));
  check('placeholder restored', (await p.getAttribute('#search-input', 'placeholder')) === 'Search this document...');
  resetLabels();
  await p.fill('#search-input', 'Hypertension');
  res = await search();
  check('literal search works again, no GLiNER2 call', /Page 2: 1 match/.test(res) && labels().length === 0, res);

  // 9. Download with a non-Latin, quote-containing name (header fix)
  // Buffer form: playwright-core can't attach from a non-ASCII disk path;
  // the browser sees the same File (name + bytes) a user would pick.
  await p.setInputFiles('#file-input', { name: '報告 "final".pdf', mimeType: 'application/pdf', buffer: fs.readFileSync(`${S}/sample.pdf`) });
  await p.click('#upload-btn');
  await p.waitForFunction(() => /報告/.test(document.querySelector('#doc-info').textContent));
  const [dl] = await Promise.all([p.waitForEvent('download'), p.click('#download-link')]);
  // Chromium itself swaps the " for _ when saving (not a filesystem-safe char).
  check('download of 報告 "final".pdf keeps its real name', dl.suggestedFilename() === '報告 _final_.pdf', dl.suggestedFilename());
  const [dl2] = await Promise.all([p.waitForEvent('download'), p.click('#download-annotated-link')]);
  check('annotated-PDF download works for that name', dl2.suggestedFilename() === '報告 _final__annotated.pdf', dl2.suggestedFilename());

  // 10. Any file type converts to PDF (images via Pillow/PyMuPDF, office via LibreOffice)
  check('upload hint lists supported formats', /images \(PNG, JPEG, TIFF/.test(await p.textContent('#upload-hint')));
  const uploadAndWait = async (file) => {
    await p.setInputFiles('#file-input', file);
    await p.click('#upload-btn');
    await p.waitForFunction(() => !/Uploading/.test(document.querySelector('#doc-info').textContent), null, { timeout: 60000 });
    return (await p.textContent('#doc-info')).trim();
  };
  let info = await uploadAndWait(`${S}/sample.png`);
  await p.waitForSelector('#page-image[src]');
  check('PNG upload converts and opens', /image\/png, 1 page/.test(info), info);
  info = await uploadAndWait(`${S}/sample.tif`);
  await p.waitForFunction(() => document.querySelectorAll('#thumbnails img').length === 3);
  check('multi-page TIFF opens with one page per frame', /image\/tiff, 3 page/.test(info) && (await p.locator('#thumbnails img').count()) === 3, info);
  info = await uploadAndWait(`${S}/unsupported.bin`);
  check('unsupported file shows the conversion error', /Could not open unsupported\.bin: .*unsupported file type/.test(info), info);
  check('previous document stays open after a failed upload', !(await p.isHidden('#viewer')) && (await p.locator('#thumbnails img').count()) === 3);

  // 11. OCR: a scanned image gets a text layer, so literal search finds its words
  if (process.env.OCR_EXPECTED === '1') {
    info = await uploadAndWait(`${S}/scan.png`);
    check('scanned image reports OCR in the status line', /text recognized \(OCR\) on 1 scanned page/.test(info), info);
    await p.waitForSelector('#page-image[src]');
    await p.waitForFunction(() => /HEMOGLOBIN/.test(document.querySelector('#page-text').textContent));
    check('OCR text shows in the page text panel', /Nguyen/.test(await p.textContent('#page-text')));
    if (await p.isChecked('#search-ner')) await p.uncheck('#search-ner');
    await p.fill('#search-input', 'Metformin');
    res = await search();
    check('literal search finds a word that only exists in the scan pixels', /Page 1: 1 match/.test(res), res);
    await p.waitForTimeout(300);
    await p.screenshot({ path: `${S}/6-ocr-search.png`, clip: { x: 150, y: 120, width: 700, height: 360 } });
  } else {
    console.log('SKIP  OCR checks (tesseract not installed)');
  }

  // 12. Narrow window: row wraps, nothing overflows
  await p.setViewportSize({ width: 1024, height: 800 });
  await p.waitForTimeout(200);
  const ov = await p.$eval('#search-bar-row', r => r.scrollWidth > r.clientWidth + 1);
  const inputW = await p.$eval('#search-input', i => i.getBoundingClientRect().width);
  check('search row does not overflow at 1024px', !ov);
  check('search box stays usably wide', inputW >= 150, `${Math.round(inputW)}px`);
  await p.screenshot({ path: `${S}/4-narrow.png`, clip: { x: 700, y: 120, width: 324, height: 260 } });

  check('no JS errors', errors.length === 0, errors.join(' | '));
  console.log(`\n${pass} passed, ${fail} failed`);
  await b.close(); process.exit(fail ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
