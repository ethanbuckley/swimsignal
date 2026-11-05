// What the first screen-reader pass (5 Nov 2026) changed. Checked in headless Chrome's accessibility tree,
// not heard: a spot's tiles were h2 under an h2, the scale and the river's range said their tile's figure a
// second time, "112 spots." and "Starting from Reading." were read out again on every redraw, and the day's
// "Close" did not say what it closes. The functions are index.html's own, run as scripts/prerender_spots.js runs them.
// node --test tests/site_screen_reader.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const prerender = require('../scripts/prerender_spots.js');

const HTML = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const NOW = Date.parse('2026-10-22T13:30:00Z');
const DAYS = ['2026-10-22', '2026-10-23', '2026-10-24', '2026-10-25', '2026-10-26'];

function page() {
  const store = {getItem: () => null, setItem() {}, removeItem() {}}, root = 'https://example.org/swim/';
  const ctx = vm.createContext({console, URL, URLSearchParams, Intl, history: {state: null}, location: new URL(root),
    navigator: {onLine: true}, localStorage: store, sessionStorage: store, addEventListener() {}, setTimeout, clearTimeout,
    ROOT: new URL(root), map: null, TOUCH: false, STILL: false});
  ctx.window = ctx;
  vm.runInContext(`Date.now = () => ${NOW};`, ctx);
  for (const f of ['eatoday.js', 'experience.js', 'levels.js', 'lists.js'])
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site', f), 'utf8'), ctx);
  vm.runInContext(prerender.reached(HTML, ['facts', 'tile', 'dayTiles', 'nowTiles', 'scaleBar', 'rangeBar', 'sayOnChange'],
    ['ROOT', 'map', 'TOUCH', 'STILL']), ctx);
  vm.runInContext('setToday("2026-10-22");', ctx);
  ctx.S = {id: 'osm-thames-long-bridges', name: 'Long Bridges', kind: 'river', source: 'osm', upstream_summary: {overflows: 45},
    location: {mode: 'river'}, now: {label: 'low', discharging_upstream: 1, monitored_upstream: 43, recent_upstream: 4}, contributors: [],
    assumptions: {max_upstream_km: 60, recent_spill_hours: 48},
    weather: {days: DAYS.map(date => ({date, tmax: 14, sunrise: '07:41', sunset: '17:56'}))},
    days: DAYS.map((date, i) => ({date, risk: 0.3 + i / 100, label: 'moderate', rain_48h_mm: 10, expected_spilling_overflows: 7}))};
  ctx.DATA_IN = {generated_at: '2026-10-22T14:05:00+01:00', spots: [ctx.S]};
  vm.runInContext('DATA = DATA_IN;', ctx);
  return ctx;
}

test("a spot's tiles are h3 under their group's h2, so a list of headings nests them", () => {
  const ctx = page();
  for (const call of ['dayTiles(S)', 'dayTiles(S, "2026-10-24")', 'nowTiles(S)']) {
    const h = vm.runInContext(call, ctx);
    assert.match(h, /<h2 class="grp-h"/, call);
    assert.match(h, /<h3 class="t-lab">/, call);
    assert.doesNotMatch(h, /<h2 class="t-lab"/, call);
  }
  // A tile standing on its own (the rating) keeps its h2; map() passing an index does not become a level.
  assert.match(vm.runInContext('tile({icon: "", label: "Environment Agency rating"})', ctx), /^<div class="tile"><h2 class="t-lab">/);
  assert.match(vm.runInContext('[{icon: "", label: "x"}].map(tile)[0]', ctx), /<h2 class="t-lab">/);
});

test('the scale is hidden from a screen reader: the figure and level word above it are read once', () => {
  const ctx = page(), h = vm.runInContext('dayTiles(S)', ctx);
  assert.match(h, /<div class="scale" aria-hidden="true">/);
  assert.doesNotMatch(h, /role="img" aria-label="Sewage spill risk/);
  assert.match(h, /30<small>of 100<\/small><span class="t-word[^"]*">Moderate risk<\/span>/);   // still said, as text
});

test("the river's range says the range, not the level its tile has just read", () => {
  const ctx = page();
  const h = vm.runInContext('rangeBar({level_m: 0.1, typical_low_m: 0, typical_high_m: 3})', ctx);
  assert.match(h, /role="img" aria-label="Usual range 0\.00 to 3\.00 m"/);
  assert.doesNotMatch(h, /aria-label="0\.10 m/);
});

test('a live region is written only when its words change, so a redraw does not read it out again', () => {
  const ctx = page(), writes = [];
  const el = {set textContent(v) { writes.push(['text', v]); }, set innerHTML(v) { writes.push(['html', v]); }};
  ctx.el = el;
  vm.runInContext('sayOnChange(el, "112 spots."); sayOnChange(el, "112 spots."); sayOnChange(el, "Showing 6 of 112 spots.");', ctx);
  assert.deepEqual(writes, [['text', '112 spots.'], ['text', 'Showing 6 of 112 spots.']]);
  writes.length = 0;
  vm.runInContext('sayOnChange(el, "<b>6 spots</b> near Reading.", true); sayOnChange(el, "<b>6 spots</b> near Reading.", true); sayOnChange(null, "x");', ctx);
  assert.deepEqual(writes, [['html', '<b>6 spots</b> near Reading.']]);
});

test('the list count and the plan lines go through it', () => {
  assert.match(HTML, /sayOnChange\(document\.getElementById\('count'\), /);
  assert.match(HTML, /sayOnChange\(document\.getElementById\('plan-where'\), [^\n]*, true\);/);
  assert.match(HTML, /sayOnChange\(sum, \(!r\.count \? '' : /);
  assert.doesNotMatch(HTML, /getElementById\('count'\)\.textContent =|getElementById\('plan-where'\)\.innerHTML =|sum\.innerHTML =/);
});

test("the open day's heading sits under the five days' h2, and its Close says which day", () => {
  const head = HTML.match(/<div class="dd-head">[^\n]*<\/div>`/)[0];
  assert.match(head, /<h3 class="dd-t">\$\{when\}<\/h3>/);
  assert.match(head, /id="day-close">Close<span class="sr"> \$\{when\}<\/span><\/button>/);
});
