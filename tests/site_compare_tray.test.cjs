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

test('the water rows: each value with its kind (measured where and when, estimate, too old, none), the gauge named', () => {
  const src = slice('function compareWater(s) {', '\n// "Plan here" in a comparison');
  const tag = (k, w) => `<span class="vt vt-${k}">${w}</span>`;
  const make = (w, lv) => new Function('waterTile', 'riverTile', 'esc', 'valueTag', 'dpAgo', src + '\nreturn compareWater;')(() => w, () => lv, esc, tag, h => `${Math.round(h)} h ago`);
  const river = { kind: 'river', river_state: { station: 'Sutton Courtenay', age_hours: 2 } };
  assert.deepEqual(make({ fig: '12°', unit: 'C, provisional estimate' }, { fig: '1.99', label: 'River level', word: 'Low water' })(river),
    ['12&nbsp;°C <span class="vt vt-estimate">Provisional estimate</span>', '1.99&nbsp;m, low water <span class="vt vt-measured">Measured at Sutton Courtenay, 2 h ago</span>']);
  const now = Date.now(), at = new Date(now - 3 * 3.6e6).toISOString();
  assert.deepEqual(make({ fig: '14°', live: true }, null)({ kind: 'river', water_temp: { where: 'at Bures Mill', observed_at: at } }),
    ['14&nbsp;°C <span class="vt vt-measured">Measured at Bures Mill, 3 h ago</span>', '<span class="vt vt-none">No gauge</span>']);
  assert.deepEqual(make(null, { fig: '–' })({ kind: 'lake', river_state: { water: 'lake', stale: true, station: 'Bowness', age_hours: 30 } }),
    ['<span class="vt vt-none">No reading</span>', '<span class="vt vt-none">No current reading</span> <span class="vt vt-stale">Last reading at Bowness 30 h ago: too old to use</span>']);
});

test('a forecast that did not load says why in words, offers Try again, and points to official advice', () => {
  const fail = slice('main().catch(e => {', '\n// Opened from the home screen');
  assert.match(fail, /The forecast did not load/);
  assert.match(fail, /e instanceof TypeError \? 'The forecast could not be reached'/);   // not the browser's "Failed to fetch"
  assert.match(fail, /No level is shown rather than an old one\./);
  assert.match(fail, /onclick="location\.reload\(\)">Try again<\/button>/);
  assert.match(fail, /the Environment Agency's bathing water pages<\/a>, and the signs at the water/);
  assert.doesNotMatch(fail, /\bcap\(/);   // levels.js may be what failed
});

// 2 Nov 2026: "possible, not expected" said once for a group where every row has it; each row keeps its count.
test('a group whose rows all say a spill is possible, not expected says it once; each row keeps its own count', () => {
  const why = slice('const PLAN_QUIET =', '\n// How much evidence sits');
  assert.match(why, /if \(t && quiet && t\.endsWith\(PLAN_QUIET\)\) out\.push\(`\$\{total\} overflow\$\{total === 1 \? '' : 's'\} upstream\.`\);/);
  assert.match(why, /else if \(t\) out\.push\(`\$\{cap\(t\)\}/);   // otherwise the sentence as before
  const draw = slice('function drawPlan(fit = false) {', '\n// Compare these spots');
  assert.match(draw, /const quiet = displayGroups\.map\(g => g\.length >= 2 && g\.every\(o => planQuiet\(o\.s, PLAN\.day\)\)\);/);
  assert.match(draw, /At each spot here a spill from an overflow upstream is \$\{PLAN_QUIET\}\./);
  assert.match(draw, /g\.map\(o => planItem\(o, quiet\[i\]\)\)/);
  assert.match(draw, /restrictedLow\.map\(planItem\)/);   // the restricted group is never shortened (official advice first)
});

// The value-kind treatment is defined once (docs/DESIGN.md, "What kind of value"): a second copy left by a rebase
// would be a SyntaxError that stops the whole app.
test('valueTag and VALUE_KINDS are defined exactly once, and every kind says its kind in words', () => {
  assert.equal((html.match(/\bconst valueTag\b/g) || []).length, 1);
  assert.equal((html.match(/\bconst VALUE_KINDS\b/g) || []).length, 1);
  const tag = new Function(slice('const VALUE_KINDS =', '\nfunction waterTile(') + '\nreturn valueTag;')();
  assert.equal(tag('estimate', 'Estimate'), '<span class="vt vt-estimate">Estimate</span>');
  assert.equal(tag('anything', 'Not known'), '<span class="vt vt-none">Not known</span>');
  for (const k of ['vt-none', 'vt-stale']) assert.ok(html.includes(`.${k}`), k);
});
