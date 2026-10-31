// One date on a spot's page (22 Oct 2026). An outside review picked Saturday at Long Bridges: the
// answer and the day's rows said Saturday, but the Sewage spills, Rain here and Weather tiles further
// down still gave today. The forecast's tiles now follow the open day (facts(d, iso), dayTiles), under a
// heading that names it; the readings (Right now, River level, Water temperature, Algae) stay on now,
// under a heading of their own (nowTiles). The functions are index.html's own, run as
// scripts/prerender_spots.js runs them.
// node --test tests/site_day_tiles.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const prerender = require('../scripts/prerender_spots.js');

const NOW = Date.parse('2026-10-22T13:30:00Z'), BUILT = '2026-10-22T14:05:00+01:00';
const DAYS = ['2026-10-22', '2026-10-23', '2026-10-24', '2026-10-25', '2026-10-26'];
const RISK = [0.30, 0.31, 0.39, 0.45, 0.33], RAIN = [17, 22, 17, 12, 4], TMAX = [14, 13, 15, 12, 11];

function page() {
  const store = {getItem: () => null, setItem() {}, removeItem() {}}, root = 'https://example.org/swim/';
  const ctx = vm.createContext({console, URL, URLSearchParams, Intl, history: {state: null}, location: new URL(root),
    navigator: {onLine: true}, localStorage: store, sessionStorage: store, addEventListener() {}, setTimeout, clearTimeout,
    ROOT: new URL(root), map: null, TOUCH: false, STILL: false});
  ctx.window = ctx;
  vm.runInContext(`Date.now = () => ${NOW};`, ctx);
  for (const f of ['eatoday.js', 'experience.js', 'levels.js', 'lists.js'])
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site', f), 'utf8'), ctx);
  const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  vm.runInContext(prerender.reached(html, ['facts', 'tile', 'dayTiles', 'nowTiles'], ['ROOT', 'map', 'TOUCH', 'STILL']), ctx);
  vm.runInContext('setToday("2026-10-22");', ctx);
  ctx.S = {id: 'osm-thames-long-bridges', name: 'Long Bridges', kind: 'river', source: 'osm', upstream_summary: {overflows: 45},
    location: {mode: 'river'}, now: {label: 'low', discharging_upstream: 1, monitored_upstream: 43, recent_upstream: 4}, contributors: [],
    assumptions: {max_upstream_km: 60, recent_spill_hours: 48},
    river_state: {station: 'Sutton Courtenay', river: 'River Thames', level_m: 2.09, typical_low_m: 1.91, typical_high_m: 3.51, label: 'low',
      observed_at: '2026-10-22T13:00:00Z', age_hours: 0.5, stale: false, distance_km: 10, same_river: true},
    weather: {days: DAYS.map((date, i) => ({date, tmax: TMAX[i], sunrise: '07:41', sunset: '17:56'}))},
    days: DAYS.map((date, i) => ({date, risk: RISK[i], label: RISK[i] >= 0.4 ? 'high' : 'moderate', rain_48h_mm: RAIN[i],
      expected_spilling_overflows: [7, 12, 20, 25, 9][i]}))};
  ctx.DATA_IN = {generated_at: BUILT, spots: [ctx.S]};
  vm.runInContext('DATA = DATA_IN;', ctx);
  return ctx;
}
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ');

test('with no day open, the forecast tiles give today, under a heading that says so', () => {
  const ctx = page(), h = text(vm.runInContext('dayTiles(S)', ctx));
  assert.match(h, /^ Forecast for today /);
  assert.match(h, /Sewage spills 30 of 100/);
  assert.match(h, /About 7 of the 45 overflows upstream are expected to spill today\./);
  // The rain and the air are in each day's row and the conditions tiles since 31 Oct 2026 (dayWx, conditionsSummary).
  assert.doesNotMatch(h, /Rain here|Weather/);
});

test('a picked day moves every forecast tile to that day, and names it', () => {
  const ctx = page(), raw = vm.runInContext('dayTiles(S, "2026-10-24")', ctx), h = text(raw);
  assert.match(h, /^ Forecast for Saturday 24 October /);
  assert.match(h, /Sewage spills 39 of 100/);
  assert.match(h, /About 20 of the 45 overflows upstream are expected to spill on Saturday\./);
  assert.doesNotMatch(h, /Rain here|Weather/);   // in Saturday's row (dayWx)
  assert.doesNotMatch(h, /today/);
  // A day that has left the five days opens today's.
  assert.match(text(vm.runInContext('dayTiles(S, "2026-10-30")', ctx)), /^ Forecast for today .*Sewage spills 30 of 100/);
});

test('the readings stay on now whichever day is open, under their own heading', () => {
  const ctx = page(), h = text(vm.runInContext('nowTiles(S)', ctx));
  assert.match(h, /^ Latest readings Measured, not forecast: they stay the same whichever day you pick\. Right now 1 /);
  assert.doesNotMatch(h, /River level/);   // in the conditions tiles since 31 Oct 2026
  for (const iso of DAYS) {
    const day = text(vm.runInContext(`dayTiles(S, "${iso}")`, ctx));
    assert.doesNotMatch(day, /Right now|River level/);
  }
});
