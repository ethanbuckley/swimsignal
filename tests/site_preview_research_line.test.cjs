// The research line on the redesign's home page (docs/RESEARCH-ON-THE-SITE-2026-11.md, item 4; docs/DESIGN.md, "After
// the review", 12 November 2026): the earlier page's rule and words, word for word, with the way to the scorecard and
// the Lab; the plain line in the built page and whenever the scorecard cannot be read.
//   node --test tests/site_preview_research_line.test.cjs
process.env.TZ = 'Europe/London';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const SITE = path.join(__dirname, '../src/dipcast/site');
const L = require(path.join(SITE, 'levels.js')), EA = require(path.join(SITE, 'eatoday.js'));
Object.assign(globalThis, L, EA);
const M = require(path.join(SITE, 'preview/model.js'));
const LIVE = fs.readFileSync(path.join(SITE, 'index.html'), 'utf8'), JS = fs.readFileSync(path.join(SITE, 'preview/app.js'), 'utf8');
const live = new Function(LIVE.slice(LIVE.indexOf('function researchNow(doc, iso) {'), LIVE.indexOf('function researchLine() {')) + '; return researchNow;')();
const {prerender} = require(path.join(__dirname, '../scripts/prerender_preview.js'));

test('the line says what the earlier page says, for the same scorecard and day', () => {
  const shadow = (id, read_on) => ({id, stage: 'shadow', window: {read_on}});
  const docs = [{models: [shadow('a', '2026-11-16'), shadow('b', '2026-11-28'), {id: 'c', stage: 'live'}]}, {models: [shadow('a', '2026-11-28')]},
    {models: [shadow('a', '2026-11-01')]}, {models: []}, null];
  for (const doc of docs) for (const iso of ['2026-11-12', '2026-11-25']) assert.equal(M.researchNow(doc, iso), live(doc, iso));
  assert.equal(M.researchNow(docs[0], '2026-11-12'), 'Research: 2 candidate models are being scored beside the live forecast, without changing it. The next test is read on 16 November.');
  assert.ok(LIVE.includes(`<span id="research-now">${M.RESEARCH_PLAIN}</span> <a href="models.html">What is being tested now</a> · <a href="lab/">Research Lab</a>.`));
});

test('the home page has the plain line in its built copy, after the list, and asks for the scorecard on the home page only', () => {
  const site = fs.mkdtempSync(path.join(os.tmpdir(), 'pv-research-'));
  let out;
  try {
    fs.mkdirSync(path.join(site, 'data'), {recursive: true}); fs.mkdirSync(path.join(site, 'preview'));
    fs.writeFileSync(path.join(site, 'data', 'spots-lite.json'), JSON.stringify({generated_at: '2026-11-24T13:21:00+00:00', spots: []}));
    out = prerender(site, '');
  } finally { fs.rmSync(site, {recursive: true, force: true}); }
  assert.match(out.home, /<p class="meta research-line"><span id="research-now">Research: a model is tested before it changes a forecast\.<\/span> <a href="models\.html">What is being tested now<\/a> · <a href="lab\/">Research Lab<\/a>\.<\/p>/);
  assert.ok(out.home.indexOf('research-line') > out.home.indexOf('id="results"'));
  assert.match(JS, /if \(route\.screen === 'find' && !route\.view\) researchLine\(\);/);
});
