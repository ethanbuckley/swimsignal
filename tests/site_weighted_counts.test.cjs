// Counts of overflows that carry weight, and levels from the score shown (23 Oct 2026).
//  - At Windermere, Waterhead, Grasmere WwTW reaches the spot with a weight of 0.00045 (0% reach), yet the
//    page said "About 2 of the 4 overflows upstream are expected to spill today", counting its spill chance,
//    and at Lakeside YMCA and Fellfoot "1 stopped lately" was an overflow with no weight there. The build
//    now counts only those with a weight of 0.005 or more (forecast.py, weighted_here), and the page says
//    once that the others are upstream (levels.js, tooFarSaid). Click-anywhere counts the same way.
//  - A score of 15 was labelled Low: the label came from the unrounded risk (0.1497). It now comes from the
//    score shown, as transport.risk_label does; the cases here are tests/test_weighted_counts.py's.
// The functions are index.html's own, run as scripts/prerender_spots.js runs them.
// node --test tests/site_weighted_counts.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const prerender = require('../scripts/prerender_spots.js');
const R = require('../src/dipcast/site/levels.js');
const A = require('../src/dipcast/site/anypoint.js');

const NOW = Date.parse('2026-10-23T15:20:00Z'), BUILT = '2026-10-23T16:20:00+01:00';
const DAYS = ['2026-10-23', '2026-10-24', '2026-10-25', '2026-10-26', '2026-10-27'];

function page() {
  const store = {getItem: () => null, setItem() {}, removeItem() {}}, root = 'https://example.org/swim/';
  const layer = {addTo() { return this; }, bindTooltip() { return this; }};
  const ctx = vm.createContext({console, URL, URLSearchParams, Intl, history: {state: null}, location: new URL(root),
    navigator: {onLine: true}, localStorage: store, sessionStorage: store, addEventListener() {}, setTimeout, clearTimeout,
    ROOT: new URL(root), map: null, TOUCH: false, STILL: false, L: {circleMarker: () => layer}, contribLayer: layer});
  ctx.window = ctx;
  vm.runInContext(`Date.now = () => ${NOW};`, ctx);
  for (const f of ['eatoday.js', 'experience.js', 'levels.js', 'lists.js'])
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site', f), 'utf8'), ctx);
  const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  vm.runInContext(prerender.reached(html, ['daysTile', 'dayTiles', 'nowTiles', 'overflowTile'], ['ROOT', 'map', 'TOUCH', 'STILL', 'L', 'contribLayer']), ctx);
  vm.runInContext('setToday("2026-10-23");', ctx);
  return ctx;
}
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ');
const row = (id, name, weight, p) => ({site_id: id, site_name: name, company: 'United Utilities', status: 0, data_state: 'live',
  distance_km: 2, lake_distance_km: 1, travel_h: 10, weight, p_spill_today: p, lat: 54.4, lon: -3});
// Waterhead as the build now writes it (the 23 Oct 16:20 forecast through the new rule): 3 overflows count,
// Grasmere does not.
const waterhead = (summary = {overflows: 3, too_far: 1, too_far_overflow: {site_id: 'UUP00829', site_name: 'Grasmere Waste Water Treatment Works', company: 'United Utilities'}}) => ({
  id: 'osm-windermere-waterhead', name: 'Windermere, Waterhead, Ambleside', kind: 'lake', source: 'openstreetmap',
  location: {mode: 'lake'}, upstream_summary: summary, assumptions: {max_upstream_km: 60, recent_spill_hours: 48},
  now: {risk: 0, label: 'low', discharging_upstream: 0, recent_upstream: 0, monitored_upstream: 3},
  contributors: [row('UUP00114', 'AMBLESIDE WwTW', 0.184, 0.61), row('UUP00804', 'Glebe Road PS', 0.101, 0.2),
    row('UUP00702', 'Elterwater pumping station (ELTER) (LAK0025)', 0.092, 0.55), row('UUP00829', 'Grasmere Waste Water Treatment Works', 0, 0.82)],
  days: DAYS.map((date, i) => ({date, risk: [0.133, 0.191, 0.158, 0.165, 0.149][i], label: ['low', 'moderate', 'moderate', 'moderate', 'moderate'][i],
    expected_spilling_overflows: [1.4, 1.9, 0.9, 1.4, 1.2][i]}))});

test('the counts leave out an overflow that carries too little weight to count, and the page says once that it is there', () => {
  const ctx = page();
  ctx.S = waterhead();
  ctx.DATA_IN = {generated_at: BUILT, spots: [ctx.S]};
  vm.runInContext('DATA = DATA_IN;', ctx);
  const days = text(vm.runInContext('daysTile(S)', ctx)), tiles = text(vm.runInContext('dayTiles(S) + nowTiles(S)', ctx));
  assert.match(days, /About 1 of the 3 overflows upstream is expected to spill today, about 2 tomorrow\. Grasmere sewage works overflow is upstream too, but too little of its water would reach here to count\./);
  assert.doesNotMatch(days + tiles, /of the 4 overflows|0 of 4|4 of 4/);
  assert.equal((days + tiles).split('would reach here to count').length - 1, 1);   // once
  assert.match(tiles, /0 of 3 discharging/);
  assert.match(tiles, /3 of 3 report live\./);
});

test('the overflow list keeps every row, and one with no reach says it does not count', () => {
  const ctx = page();
  ctx.S = waterhead();
  const ov = text(vm.runInContext('overflowTile(S, allUpstream(S))', ctx));
  assert.match(ov, /Grasmere sewage works overflow .* 0% reach too little reaches here to count/);
  assert.doesNotMatch(ov, /0% reach spill 82% today/);
  assert.match(ov, /18% reach spill 61% today/);
  assert.match(ov, /The 4 overflows upstream, most first/);
  // A list cut to the ten that matter most still gives the whole number upstream.
  ctx.S = waterhead({overflows: 59, too_far: 1});
  assert.match(text(vm.runInContext('overflowTile(S, allUpstream(S))', ctx)), /The 4 of the 60 overflows upstream that matter most this week/);
});

test('more than one left out: a number, not names', () => {
  assert.equal(R.tooFarSaid(waterhead({overflows: 2, too_far: 4})), '4 more overflows are upstream, but too little of their water would reach here to count.');
  assert.equal(R.tooFarSaid(waterhead({overflows: 2, too_far: 1, too_far_overflow: {site_id: 'X1', site_name: null}})),
    'One more overflow is upstream too, but too little of its water would reach here to count.');
  assert.equal(R.tooFarSaid(waterhead({overflows: 4})), '');
  assert.equal(R.allUpstream(waterhead({overflows: 2, too_far: 4})), 6);
});

// The same table as tests/test_weighted_counts.py: risk, the score shown, the level.
const LEVELS = [[0.1449, 14, 'low'], [0.1450, 14, 'low'], [0.146, 15, 'moderate'], [0.149, 15, 'moderate'], [0.1497, 15, 'moderate'],
  [0.15, 15, 'moderate'], [0.394, 39, 'moderate'], [0.3949, 40, 'high'], [0.3950, 40, 'high'], [0.40, 40, 'high'],
  [0.694, 69, 'high'], [0.6950, 70, 'very high'], [0.70, 70, 'very high']];

test('a level comes from the score shown, on the page and for a clicked point', () => {
  for (const [r, score, level] of LEVELS) {
    const shown = Math.round(Math.round(r * 1000) / 1000 * 100);   // spots.json's 3 dp, then the page's Math.round
    assert.equal(shown, score, `${r} shows as ${score}`);
    assert.equal(R.spillLevel(Math.round(r * 1000) / 1000), level, `page: ${r}`);
    assert.equal(A.riskLabel(r), level, `click-anywhere: ${r}`);
  }
});

test('click-anywhere counts only the overflows that carry weight, as the build does', () => {
  const fx = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'anypoint_spot.json'), 'utf8'));
  const base = A.forecast(fx.rows, fx.od, fx.cal);
  assert.equal(base.upstream_summary.too_far, undefined);
  // One overflow made to carry no weight here, and discharging: it no longer counts anywhere.
  const k = 4, rows = fx.rows.map((r, j) => j === k ? {...r, dil: 1e-7} : r);
  const od = {...fx.od, status: fx.od.status.map((s, i) => i === rows[k].i ? 1 : s)};
  const got = A.forecast(rows, od, fx.cal), withIt = A.forecast(fx.rows, od, fx.cal);
  assert.equal(withIt.now.discharging_upstream, 1);
  assert.equal(got.now.discharging_upstream, 0);
  assert.equal(got.upstream_summary.overflows, base.upstream_summary.overflows - 1);
  assert.equal(got.upstream_summary.too_far, 1);
  assert.equal(got.upstream_summary.too_far_overflow.site_id, String(rows[k].i));
  assert.equal(got.now.monitored_upstream, withIt.now.monitored_upstream - 1);
  got.days.forEach((d, j) => assert.ok(d.expected_spilling_overflows <= withIt.days[j].expected_spilling_overflows, d.date));
  assert.equal(got.contributors.length, withIt.contributors.length);   // the list is not cut
});
