// Builds synthetic HEDIS chart .docx files from specs.js.
// Usage: NODE_PATH=<dir-with-docx>/node_modules node build.js <outDir> [MEASURE ...]
//   e.g. node build.js samples            -> all measures in specs.js
//        node build.js samples CBP GSD    -> only those
const path = require('path');
const { buildChart } = require('./layout');
const specs = require('./specs');

const [outDir, ...only] = process.argv.slice(2);
if (!outDir) { console.error('usage: node build.js <outDir> [MEASURE ...]'); process.exit(2); }
const wanted = only.map((m) => m.toUpperCase());
const unknown = wanted.filter((m) => !specs.some((s) => s.measure === m));
if (unknown.length) { console.error(`no spec for: ${unknown.join(', ')} (add one to specs.js)`); process.exit(2); }

(async () => {
  for (const s of specs.filter((s) => !wanted.length || wanted.includes(s.measure))) {
    const out = path.join(outDir, `${s.file || s.measure}.docx`); // `file` lets one measure have variants, e.g. CBP_noncompliant
    await buildChart(s, out);
    console.log('wrote', out);
  }
})();
