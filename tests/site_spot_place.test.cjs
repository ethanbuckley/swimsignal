// A spot's page: the place first (11 Nov 2026; docs/DESIGN.md). The guide's overview photo opens the answer, in the
// build's copy too; "Where the risk comes from" draws the river as a sketch of the overflows on it; past spills say
// this month in a sentence; "Lower risk nearby" never offers a spot at high risk; and on a phone a low day's page puts
// the conditions first, with the way to log a swim. No level, count or forecast changes.
// node --test tests/site_spot_place.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const spots = require('../scripts/prerender_spots.js');
const G = require('../src/dipcast/site/guide.js');
const S = require('../src/dipcast/site/seasonal.js');

const ROOT = path.join(__dirname, '..');
const PAGE = fs.readFileSync(path.join(ROOT, 'src/dipcast/site/index.html'), 'utf8');
const GEN = '2026-11-11T06:56:11+00:00', NOW = Date.parse(GEN);
const DAYS = ['2026-11-11', '2026-11-12', '2026-11-13', '2026-11-14', '2026-11-15'];
const RISK = {low: 0.03, moderate: 0.2, high: 0.5, 'very high': 0.72};
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();
// Dartington Pontoon's photo, as guides/osm-dart-dartington.toml gives it (data/spot/osm-dart-dartington.json, 11 Nov 2026).
const PHOTO = {file: 'geograph-6482389.jpg', w: 640, h: 413, topic: 'overview', caption: 'River Dart at The Weir, looking north-west.',
  credit: 'Derek Harper', taken: '2020-05-20', status: 'historical', source: 'https://www.geograph.org.uk/photo/6482389', source_name: 'Geograph',
  title: 'River Dart at The Weir', licence: 'https://creativecommons.org/licenses/by-sa/2.0/',
  changes: 'Re-encoded as a JPEG at the same size, 640 x 413, with all metadata removed.', labels: []};
const ov = (site_id, site_name, km, start, end, extra = {}) => ({site_id, company: 'South West Water', site_name, receiving_watercourse: 'RIVER DART',
  lat: 50.47, lon: -3.76, status: 0, has_live: true, data_state: 'live', feed_updated_at: '2026-11-11T06:47:05+00:00', distance_km: km, lake_distance_km: 0,
  travel_h: km / 0.72, weight: 0.5, p_spill_today: 0.2, latest_event_start: start, latest_event_end: end, ...extra});
const KILBURY = ov('SBB00179', 'KILBURY STW_SO_BUCKFASTLEIGH', 10.2, '2026-11-10T09:30:40+00:00', '2026-11-10T09:52:39+00:00');
const TANK = ov('SBB00178', 'KILBURY STW_SSO_BUCKFASTLEIGH', 10.2, '2026-10-24T14:04:31+00:00', '2026-10-25T00:33:04+00:00');
const PEAR = ov('SBB00917', 'PEAR TREE CROSS_CSO_ASHBURTON', 14.1, '2026-11-10T07:08:05+00:00', '2026-11-10T07:10:05+00:00', {weight: 0.13});
const STAVERTON = ov('SBB01166', 'STAVERTON STW_SSO_STAVERTON', 3.4, '2026-03-13T00:23:21+00:00', '2026-03-13T02:23:01+00:00', {weight: 0.83});
const DARTC = ov('SBB00350', 'DARTINGTON C_CSO_DARTINGTON', 1.2, '2026-11-09T14:06:05+00:00', '2026-11-09T14:10:05+00:00', {weight: 0.2});
const WOOLLEN = ov('SBB00001', 'OLD WOOLLEN MILL_CSO_BUCKFASTLEIGH', 11.9, '2026-01-29T21:40:05+00:00', '2026-01-29T22:18:05+00:00');
const RATTERY = ov('SBB01016', 'RATTERY STW_SO_RATTERY', 7.6, '2026-10-27T00:14:30+00:00', '2026-10-27T10:08:50+00:00', {weight: 0.1});
const spot = (id, name, labels, extra = {}) => ({id, name, kind: 'river', river: 'River Dart', source: 'curated', area: 'South West', lat: 50.44, lon: -3.69,
  upstream_summary: {overflows: 20}, location: {mode: 'river'}, contributors: [], assumptions: {max_upstream_km: 60, recent_spill_hours: 48},
  now: {label: labels[0], risk: RISK[labels[0]], discharging_upstream: 0, recent_upstream: 0, monitored_upstream: 20, monitored_weight: 1, upstream_weight: 1},
  days: DAYS.map((date, i) => ({date, label: labels[i], risk: RISK[labels[i]], expected_spilling_overflows: 0, rain_48h_mm: 1})), ...extra});
const five = l => [l, l, l, l, l];
const DART = spot('dart', 'River Dart, Dartington Pontoon', ['very high', 'high', 'moderate', 'low', 'low'],
  {contributors: [STAVERTON, KILBURY, TANK, DARTC, PEAR, RATTERY, WOOLLEN], guide: {checked: '2026-11-10', how: 'desk', facts: [], photos: [PHOTO]}});

function page(all, roots) {
  const store = {getItem: () => null, setItem() {}, removeItem() {}}, root = 'https://example.org/swim/';
  const ctx = vm.createContext({console, URL, URLSearchParams, Intl, history: {state: null}, location: new URL(root),
    navigator: {onLine: true}, localStorage: store, sessionStorage: store, addEventListener() {}, setTimeout, clearTimeout,
    ROOT: new URL(root), map: null, TOUCH: false, STILL: false});
  ctx.window = ctx;
  vm.runInContext(`Date.now = () => ${NOW};`, ctx);
  for (const f of ['eatoday.js', 'experience.js', 'levels.js', 'lists.js', 'guide.js', 'plan.js'])
    vm.runInContext(fs.readFileSync(path.join(ROOT, 'src/dipcast/site', f), 'utf8'), ctx);
  vm.runInContext(spots.reached(PAGE, roots, ['ROOT', 'map', 'TOUCH', 'STILL']), ctx);
  ctx.SPOTS = all;
  vm.runInContext(`setToday("${DAYS[0]}"); DATA = {generated_at: "${GEN}", spots: SPOTS};`, ctx);
  return ctx;
}
const call = (ctx, f, ...a) => vm.runInContext(f, ctx)(...a);

test("the place's photo: the guide's overview photo, with whose it is, its day, its licence and that it shows that day only", () => {
  const h = G.guideHero(DART);
  assert.equal(h, '<figure class="hero"><img src="guides/photos/geograph-6482389.jpg" width="640" height="413" decoding="async" fetchpriority="high" '
    + 'alt="River Dart at The Weir, looking north-west.">'
    + '<figcaption>Historical photo by Derek Harper, 20 May 2020, <a href="https://creativecommons.org/licenses/by-sa/2.0/">CC BY-SA 2.0</a>. '
    + 'It shows that day only. <a href="#guide">About this photo</a></figcaption></figure>');
  assert.doesNotMatch(h, /loading="lazy"/, 'it is the first picture on the page');
  const withPhoto = p => ({guide: {photos: [p]}});
  // A licence the page does not know is not named; the line still says whose and when.
  assert.match(G.guideHero(withPhoto({...PHOTO, licence: 'https://example.org/terms'})), /by Derek Harper, 20 May 2020\. It shows that day only\./);
  for (const p of [{...PHOTO, topic: 'rules'}, {...PHOTO, status: 'confirmed'}, {...PHOTO, status: 'suggested'}, {...PHOTO, labels: [{x: 10, y: 10, text: 'The steps'}]},
    {...PHOTO, file: '../x.jpg'}, {...PHOTO, credit: ''}, {...PHOTO, taken: ''}])
    assert.equal(G.guideHero(withPhoto(p)), '', JSON.stringify(p).slice(0, 80));
  for (const d of [null, {}, {guide: null}, {guide: {photos: []}}]) assert.equal(G.guideHero(d), '');
  // The guide keeps the photo, with its full line, which the hero's link goes to.
  assert.match(G.guideTile(DART, DAYS[0]), /id="guide"[\s\S]*<span class="g-who">Historical photo<\/span> by Derek Harper, taken 20 May 2020/);
});

test("the photo is first inside the answer, in the build's copy of the page too, so it is painted once", () => {
  const out = spots.prerender({generated_at: GEN, spots: [DART, spot('plain', 'River Barle, Tarr Steps', five('low'))]}, 'https://example.org/swim/');
  assert.match(out.dart, /<section class="answer" id="risk-hero" aria-labelledby="risk-headline"><figure class="hero"><img src="guides\/photos\/geograph-6482389\.jpg" /);
  assert.match(out.dart, /<\/figcaption><\/figure><h1 class="spot-name" tabindex="-1">River Dart, Dartington Pontoon<\/h1>/);
  assert.match(out.plain, /<section class="answer" id="risk-hero" aria-labelledby="risk-headline"><h1 class="spot-name"/, 'no photo: the answer as before');
  assert.match(fs.readFileSync(path.join(ROOT, 'scripts/prerender_spots.js'), 'utf8'), /const SCRIPTS = \['eatoday\.js', 'experience\.js', 'levels\.js', 'lists\.js', 'guide\.js'\];/);
  assert.match(PAGE, /const hero = typeof guideHero === 'function' \? guideHero\(d\) : '';\n\s+return h \+ `<section class="answer" id="risk-hero" aria-labelledby="risk-headline">\$\{hero\}<h1 class="spot-name"/);
  // With the photo the page has no sky: the tiles are cards on the paper.
  assert.match(PAGE, /\.answer:has\(\.hero\)::before \{ display:none; \}/);
  assert.match(PAGE, /body\.view-spot #result:has\(\.hero\) \.tile \{ background:var\(--card\);/);
});

test('the river as a sketch: the overflows in order along the water, any that spilled in the last 48 hours first in the choice', () => {
  const ctx = page([DART], ['riverSketch', 'whereFrom']);
  const h = call(ctx, 'riverSketch', DART, NOW), t = text(h);
  const rows = [...h.matchAll(/<li class="(\w+)"><span class="rk">([^<]*)<\/span>.*?<b>([^<]*)<\/b>(?:<span>([^<]*)<\/span>)?/g)].map(m => [m[1], m[2].replace('&nbsp;', ' '), m[3], m[4] || '']);
  assert.deepEqual(rows, [
    ['on', '14.1 km', 'Pear Tree Cross, Ashburton storm overflow', 'Spilled Tuesday 07:08, for 2 minutes.'],
    ['on', '10.2 km', 'Kilbury, Buckfastleigh sewage works overflow', 'Spilled Tuesday 09:30, for 22 minutes.'],
    ['quiet', '10.2 km', 'Kilbury, Buckfastleigh sewage works storm tank overflow', 'Not discharging. Last spill ended 25 Oct.'],
    ['quiet', '3.4 km', 'Staverton sewage works storm tank overflow', 'Not discharging. Last spill ended 13 Mar.'],
    ['on', '1.2 km', 'Dartington C storm overflow', 'Spilled Monday 14:06, for 4 minutes.'],
    ['here', 'Here', 'River Dart, Dartington Pontoon', ''],
  ]);
  assert.match(t, /A sketch of the water, not to scale: 5 of the 20 monitored overflows upstream, any that spilled in the last 48 hours first, then by model weight\. The overflows that matter most , with each one's weight\.$/);
  assert.match(h, /<a href="#overflows">The overflows that matter most<\/a>/);
  // One discharging now says since when, in the overflows list's own words.
  const live = {...STAVERTON, status: 1, latest_event_start: '2026-11-11T05:40:00+00:00', latest_event_end: null};
  assert.match(text(call(ctx, 'riverSketch', {...DART, contributors: [live]}, NOW)), /3\.4 km Staverton sewage works storm tank overflow Discharging since Wed 11 Nov, 05:40\./);
  // All of them shown: the line says so, with no "of".
  const one = {...DART, upstream_summary: {overflows: 1}, contributors: [STAVERTON]};
  assert.match(text(call(ctx, 'riverSketch', one, NOW)), /not to scale: the monitored overflow upstream\. /);
  // Through a lake, how its water comes, in overflowWhere's words.
  const lake = {...DART, upstream_summary: {overflows: 2}, contributors: [{...STAVERTON, distance_km: 0, lake_distance_km: 2.6}, {...TANK, distance_km: 8.7, lake_distance_km: 2.6}]};
  const lt = text(call(ctx, 'riverSketch', lake, NOW));
  assert.match(lt, /11\.3 km Kilbury, Buckfastleigh sewage works storm tank overflow Upstream by river and lake\. Not discharging\./);
  assert.match(lt, /2\.6 km Staverton sewage works storm tank overflow Across the lake\. Not discharging\./);
  assert.equal(call(ctx, 'riverSketch', {...DART, contributors: []}, NOW), '');
  assert.equal(call(ctx, 'riverSketch', {...DART, contributors: [{...STAVERTON, weight: 0}]}, NOW), '', 'one too far to count is not drawn');
});

test('"Where the risk comes from" ends with the sketch on today\'s view; on a low day the sketch stands alone under its own heading', () => {
  const ctx = page([DART], ['riverSketch', 'whereFrom']);
  const raised = {...DART, days: DART.days.map((x, i) => i ? x : {...x, source: {site_id: 'SBB00178', site_name: TANK.site_name, receiving_watercourse: 'RIVER DART', status: 0,
    distance_km: 10.2, lake_distance_km: 0, travel_h: 14.1, share: 0.3, spread_over: 11}})};
  const h = call(ctx, 'whereFrom', raised);
  assert.match(h, /<span>Where the risk comes from<\/span><\/h2><p class="t-say">.*<\/p><ol class="sketch">/);
  const low = {...spot('low', 'Windermere, Millerground Landing', five('low')), contributors: [STAVERTON]};
  assert.match(call(ctx, 'whereFrom', low), /^<section class="tile" aria-labelledby="whence-h"><h2 class="t-lab" id="whence-h">.*<span>Where a spill would come from<\/span><\/h2><ol class="sketch">/);
  assert.equal(call(ctx, 'whereFrom', {...low, contributors: []}), '', 'nothing to say and nothing to draw: no tile');
  // A day picked: the sentence for that day, and no sketch, which is of now.
  vm.runInContext(`DAY = "${DAYS[1]}";`, ctx);
  assert.doesNotMatch(call(ctx, 'whereFrom', raised), /class="sketch"/);
});

test('"Lower risk nearby" never offers a spot that is itself at high or very high risk', () => {
  const near = (id, name, labels) => spot(id, name, labels, {lat: 50.45, lon: -3.7});
  const high = near('high', 'River Teign, Fingle Bridge', ['high', 'high', 'moderate', 'low', 'low']);
  const mod = near('mod', 'River Dart, Spitchwick', ['moderate', 'moderate', 'low', 'low', 'low']);
  const ctx = page([DART, high, mod], ['nearby']);
  const h = call(ctx, 'nearby', DART);
  assert.match(h, /<span>Lower risk nearby<\/span>/);
  assert.match(h, /data-id="mod"/);
  assert.doesNotMatch(h, /data-id="high"/, 'high is lower than very high, and still not offered');
  const only = page([DART, high], ['nearby']);
  assert.equal(call(only, 'nearby', DART), '', 'nothing at low or moderate risk in reach: no tile');
  assert.match(PAGE, /rank\(lv\(s\)\) < Math\.min\(mine, rank\('high'\)\)/);
});

test('past spills say this month in a sentence, and the month with the smallest share', () => {
  // The Dart above Dartington, 2024 and 2025 (data/spot/osm-dart-dartington.json, 11 Nov 2026).
  const s = {years: [2024, 2025], overflows: 20, covered_min: 17, days: [62, 57, 62, 60, 62, 60, 62, 62, 60, 62, 60, 62],
    spill: [54, 50, 39, 43, 17, 11, 14, 12, 30, 39, 42, 57], short: {}};
  const w = S.seasonalWords(s, 20);
  assert.equal(w.now(10), 'November in those years: a spill reported on 42 of 60 days. The smallest share: June, 11 of 60.');
  assert.equal(w.now(5), 'June in those years: a spill reported on 11 of 60 days, the smallest share of any month.');
  assert.equal(S.seasonalWords({...s, days: s.days.map((d, i) => i === 10 ? 0 : d)}, 20).now(10), '', 'no days counted this month: nothing said');
  const tile = S.seasonalTile({seasonal: s, upstream_summary: {overflows: 20}});
  assert.match(tile, /<p class="t-say">History, not a forecast\..*?<\/p><p class="t-say s-now">[A-Z][a-z]+ in those years: a spill reported on \d+ of \d+ days/);
});

test('a phone: today at low risk, or with no monitored overflow found upstream, puts the conditions first, with the way to log a swim', () => {
  const folds = PAGE.slice(PAGE.indexOf('function phoneFolds() {'), PAGE.indexOf("\nPHONE.addEventListener('change'"));
  assert.match(PAGE, /const lowNow = d => \{ const l = level\(d\); return l === 'low' \|\| plainLevel\(l\); \};/);
  assert.match(folds, /const cond = stack\.querySelector\('\.cond'\), calm = current && !DAY && lowNow\(current\), log = document\.getElementById\('log-here'\);/);
  assert.match(folds, /if \(cond && days\) \{ if \(calm\) days\.closest\('section'\)\.before\(cond\); else if \(early\) early\.after\(cond\); \}/);
  assert.match(folds, /<p class="log-here" id="log-here"><button type="button" class="btn">Log a swim here<\/button><\/p>/);
  assert.match(folds, /document\.getElementById\('swam'\)\.click\(\);/, "it opens the journal's own form: nothing new is kept or sent");
  assert.ok(folds.indexOf('if (cond && days)') > folds.indexOf('for (const q of PHONE_EARLY)'), 'after the early sections are placed');
});
