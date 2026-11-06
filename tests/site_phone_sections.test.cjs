// A phone's spot page as one column with every section open (index.html, phoneFolds, PHONE_ORDER; 31 Oct 2026): the three
// folds after the nearby spots ("Why this level", "At the water", "What this forecast cannot see") are gone, the past spills
// open as a chart, and what the forecast cannot see under one heading. Long method text keeps its own folds.
// node --test tests/site_phone_sections.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const fn = html.slice(html.indexOf('function phoneFolds() {'), html.indexOf('\n}\n', html.indexOf('function phoneFolds() {')));

test("no outer folds: the sections follow the nearby spots in a swimmer's order", () => {
  assert.doesNotMatch(html, /fold-group|const FOLDS = /);
  // Why, how sure and what it cannot see first, after where the risk comes from (5 Nov 2026); the maps and history after the nearby spots.
  assert.match(html, /const PHONE_EARLY = \['#day-tiles', '#water-top', '#scores-host, #scores', '#limits'\];/);   // the rating with today's EA advice too
  assert.match(html, /const PHONE_ORDER = \['\.spot-map-tile', '#overflows', '#plume-host', '#now-tiles', '#lt-past', '#ls-past', '#seasonal'\];/);
  assert.match(fn, /for \(const q of PHONE_EARLY\)/);
  assert.match(html, /const PHONE_OPEN = \['#seasonal'\];/);
});

test('what it cannot see: the water-test line, what the level counts and Not known here, under one heading', () => {
  assert.match(fn, /\['#result \.stack p\.check', '#answer-after \.scope', '#unknowns'\]/);
  assert.match(fn, /What this forecast cannot see/);
  // A section the reader shut stays shut when showDay calls this again.
  assert.match(fn, /!e\.dataset\.phoneOpened/);
});

test('the repeated tiles are gone from the forecast and the readings: the conditions tiles say them', () => {
  assert.match(html, /const IN_CONDITIONS = o => o\.icon === ICON\.rain \|\| o\.icon === ICON\.sun \|\| o\.icon === ICON\.level \|\| o\.label === 'Water temperature';/);
  assert.match(html, /facts\(d\)\.filter\(o => o\.live && !IN_CONDITIONS\(o\)\)/);
});

test('the spots nearby stay high only when one is lower risk; the evidence goes under one heading (5 Nov 2026)', () => {
  // A fixed anchor keeps the sections after Nearby in place wherever Nearby goes.
  assert.match(fn, /near\.insertAdjacentHTML\('beforebegin', '<div id="near-at" hidden><\/div>'\)/);
  assert.match(fn, /if \(\/Lower risk\/\.test\(\(near\.querySelector\('#nearby-h'\) \|\| \{\}\)\.textContent \|\| ''\)\) at0\.after\(near\); else at\.after\(near\);/);
  assert.match(html, /const PHONE_EVIDENCE = \['#evidence', '#timeline', '#day-table', '\.lab-tile'\];/);
  assert.match(fn, /<h2 class="ev-phone-h" id="ev-phone-h">Evidence and history<\/h2>/);
  // The call for a guide follows the evidence; a guide itself (not section.know) stays where it is.
  assert.match(fn, /const know = stack\.querySelector\('section\.know'\); if \(know\) e0\.after\(know\);/);
  assert.match(html, /<details class="tile fold" id="day-table">/);
});
