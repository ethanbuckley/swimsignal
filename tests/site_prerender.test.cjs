// The build's copies of what the pages' scripts draw (docs/REVIEW-2026-10-16.md, F3 and F4): a spot's
// answer and five days (scripts/prerender_spots.js) and the Accuracy page's figures
// (scripts/prerender_verification.js), each made by running the page's own code in Node.
process.env.TZ = 'Europe/London';   // as the build runs them
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const spots = require('../scripts/prerender_spots.js');
const accuracy = require('../scripts/prerender_verification.js');

const PAGE = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const VER = fs.readFileSync(path.join(__dirname, '../src/dipcast/api/static/verification.html'), 'utf8');

test('a name used only in words, comments or a regular expression is not a use of it', () => {
  const c = spots.codeOnly("const a = x => `Open map at ${esc(x.name)}` + 'the map' + \"map\"; // map\n/* map */ const r = /map[/]x/g.test(s) ? map2 : y;");
  assert.ok(!/\bmap\b/.test(c), c);
  assert.ok(c.includes('esc') && c.includes('map2') && c.includes('x.name'));
});

test("the spot's opening runs the page's own definitions, and none that needs a browser as it loads", () => {
  const code = spots.reached(PAGE);
  for (const name of ['function spotTop(', 'const daysTile =', 'const answerWords =', 'const dayRows =', 'const ageReadings =', 'function saveButton('])
    assert.ok(code.includes(name), name);
  assert.ok(!code.includes("L.map('map'") && !code.includes('const ROOT =') && !code.includes('function render('));
});

const SPOT = {id: 'a', name: 'A & B', kind: 'river', source: 'curated', upstream_summary: {overflows: 3}, location: {mode: 'river'},
  now: {label: 'low', discharging_upstream: 0}, contributors: [],
  days: ['2026-09-29', '2026-09-30', '2026-10-01', '2026-10-02', '2026-10-03'].map((date, i) => ({date, risk: i === 2 ? 0.5 : 0.01, label: i === 2 ? 'high' : 'low'}))};

test("a spot's opening: its name, its headline from levels.js, its five days, issued when but not how long ago", () => {
  const out = spots.prerender({generated_at: '2026-09-29T08:00:00+01:00', spots: [SPOT]}, 'https://example.org/swim/');
  const h = out.a;
  assert.ok(h.startsWith('<div class="top-row"><a href="/swim/" class="back" id="back">All spots</a><button type="button" class="save" id="save" aria-pressed="false">'), h);
  assert.ok(h.includes('<h1 class="spot-name" tabindex="-1">A &amp; B</h1>'));
  assert.match(h, /<h2 class="big low" id="risk-headline">Low risk<\/h2><p class="why">Today and tomorrow<\/p>/);
  assert.ok(h.includes('<p class="next">High risk on Thursday</p>'));   // the week, as levels.js weekNext says it
  assert.ok(h.includes('<p class="t-sent">Low risk today. High risk on Thursday. Back to low risk on Friday.</p>'));   // levels.js backToLow
  assert.equal((h.match(/<button class="drow /g) || []).length, 5);
  assert.ok(h.includes('<button class="drow high" type="button" data-day="2026-10-01"'));
  assert.ok(h.includes('<p class="issued">Issued Tue 08:00</p>'), h.match(/<p class="issued">[^<]*/)[0]);
  assert.ok(!/ ago</.test(h));
});

// The Accuracy page's script, as tests/site_verification.test.cjs runs it, with <main>'s data-built.
async function draw(data, built) {
  const els = {};
  const document = {getElementById: id => (els[id] = els[id] || {innerHTML: ''}), querySelectorAll: () => [],
    querySelector: () => ({dataset: built ? {built} : {}})};
  vm.runInNewContext(VER.match(/<script>([\s\S]*?)<\/script>/)[1], {document, location: {hash: ''}, fetch: async () => ({json: async () => data}), console});
  for (let i = 0; i < 5; i++) await new Promise(r => setImmediate(r));
  return els;
}
const DATA = {live: {generated_at: '2026-10-04T00:15:52+01:00', n_scored: 0}};

test('the Accuracy page draws again only from scores newer than the ones the build wrote in', async () => {
  assert.ok((await draw(DATA)).short.innerHTML.includes('<dl class="stats">'));   // no copy from the build: it draws
  assert.ok((await draw(DATA, '2026-10-03T23:00:00+01:00')).short.innerHTML.includes('<dl class="stats">'));   // newer scores
  assert.equal((await draw(DATA, '2026-10-04T00:15:52+01:00')).short, undefined);   // the same: left as the build wrote it
  assert.equal((await draw(DATA, '2026-10-05T00:00:00+01:00')).short, undefined);   // older (a stored copy offline): left too
});

test("the build's copy of the Accuracy page: its four boxes and when its scores were made, with the contents list", async () => {
  const data = {...DATA, holdout: [{auc: 0.93, brier_skill_vs_clim: 0.4, n: 826000, model: 'dipcast'}]};
  const out = await accuracy.prerender(VER, data);
  assert.equal(out.built, '2026-10-04T00:15:52+01:00');
  assert.ok(out.short.includes('<dd class="v">93 in 100</dd>') && out.short.includes('<h2 id="short-h">In short</h2>'));
  assert.ok(out.offline.includes('<section id="holdout"><h2>Offline test: held-out year</h2>'));
  assert.ok(out.short.includes('<li><a href="#holdout">Offline test: held-out year</a></li>'), out.short);   // contents(), from the sections
  await assert.rejects(accuracy.prerender(VER.replace(/main\(\)\.catch/, 'go().catch'), data), /no longer ends with main\(\)\.catch/);
});
