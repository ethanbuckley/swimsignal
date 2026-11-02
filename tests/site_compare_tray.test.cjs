// Plan a swim's comparison (docs/DESIGN.md, "Home and Plan as reference screens", 2 November 2026): the tray at the
// head of the results says what is chosen and what to do, nothing is chosen until ticked, and the table's water row
// says each value as what it is.
// node --test tests/site_compare_tray.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { join } = require('node:path');

const html = fs.readFileSync(join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const slice = (from, to) => html.slice(html.indexOf(from), html.indexOf(to, html.indexOf(from)));
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

test('the tray: what to do with none or one chosen, the names, a way out for each, Compare and Clear with two', () => {
  const el = { innerHTML: '' };
  const src = slice('function planTray(ids, miles) {', '\nfunction planTrayClick(e) {');
  const byId = new Map([['a', { id: 'a', name: 'River <A>' }], ['b', { id: 'b', name: 'B' }]]);
  const planTray = new Function('document', 'planById', 'esc', 'milesAway', 'COMPARE_MAX', src + '\nreturn planTray;')(
    { getElementById: () => el }, () => byId, esc, m => `${m} miles away`, 3);
  planTray([], new Map());
  assert.match(el.innerHTML, /Tick two or three spots below/);
  assert.match(el.innerHTML, /<button type="button" class="btn primary" data-cmp-open disabled>Compare<\/button>/);
  assert.doesNotMatch(el.innerHTML, /data-cmp-clear/);
  planTray(['a'], new Map([['a', 2]]));
  assert.match(el.innerHTML, /Tick one or two more spots below\./);
  assert.match(el.innerHTML, /River &lt;A&gt; <span class="k">2 miles away<\/span>/);
  assert.match(el.innerHTML, /aria-label="Take River &lt;A&gt; out of the comparison"/);
  assert.match(el.innerHTML, /data-cmp-clear/);
  planTray(['a', 'b'], new Map());
  assert.match(el.innerHTML, /<button type="button" class="btn primary" data-cmp-open>Compare 2 spots<\/button>/);
  assert.match(el.innerHTML, /<p class="cmp-say"><\/p>/);
});

test('nothing is chosen until ticked; ticks are kept for the visit, never stored; the ticks always show', () => {
  const cmp = slice('function planCompare(groups, heads) {', '\n}\n');
  assert.match(cmp, /ids: PLAN\.compare \? planCompareIds\(PLAN\.compare, shown\.map\(o => o\.s\)\) : PLAN_PICKS\.filter\(id => miles\.has\(id\)\)\.slice\(0, COMPARE_MAX\)/);
  assert.match(cmp, /chose: x => \{ c\.ids = x; PLAN_PICKS = x;/);
  assert.match(cmp, /box\.classList\.toggle\('comparing', shown\.length >= 2\);/);
  assert.doesNotMatch(html, /localStorage\.setItem\([^)]*PLAN_PICKS/);
});

test('the water row: measured or an estimate, the gauge named, and "no reading" where there is none', () => {
  const src = slice('function compareWater(s) {', '\n// "Plan here" in a comparison');
  const make = (w, lv) => new Function('waterTile', 'riverTile', 'esc', src + '\nreturn compareWater;')(() => w, () => lv, esc);
  const river = { kind: 'river', river_state: { station: 'Sutton Courtenay' } };
  assert.equal(make({ fig: '12°', unit: 'C, provisional estimate' }, { fig: '1.99', label: 'River level', word: 'Low water' })(river),
    'Water 12°, provisional estimate<br>River level 1.99&nbsp;m, low water <span class="k">at Sutton Courtenay</span>');
  assert.equal(make({ fig: '14°', live: true }, null)({ kind: 'river' }), 'Water 14°, measured<br>No river gauge');
  assert.equal(make(null, { fig: '–' })({ kind: 'lake', river_state: { water: 'lake' } }), 'No water temperature<br>No current level reading');
});
