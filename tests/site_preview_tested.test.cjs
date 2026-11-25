// What each figure was tested on, on a place's page (docs/RESEARCH-ON-THE-SITE-2026-11.md, item 2): a row for each
// figure the page shows that day, from the research catalogue's rows, in the page's order; the basis in the
// catalogue's own words; nothing for a figure with no row, a measurement, or a page with no file.
//   node --test tests/site_preview_tested.test.cjs
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
const {prerender} = require(path.join(__dirname, '../scripts/prerender_preview.js'));
// The public file, as build_site.figures_doc makes it from the catalogue.
const CAT = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/research/research_catalogue.v1.json'), 'utf8'));
const FIGS = {schema: 'swimsignal.figures', bases: CAT.bases, figures: CAT.figures.map(({quotes, entries, models, ...f}) => f)};

const GEN = '2026-11-24T13:21:00+00:00', NOW = Date.parse('2026-11-24T14:00:00Z');
const DAYS = ['2026-11-24', '2026-11-25', '2026-11-26', '2026-11-27', '2026-11-28'];
const spot = (extra = {}, day = {}) => ({id: 'a', name: 'River Aire, Somewhere', kind: 'river', river: 'River Aire', area: 'Yorkshire', source: 'curated',
  lat: 53.9, lon: -1.8, upstream_summary: {overflows: 10}, location: {mode: 'river'}, assumptions: {max_upstream_km: 60, recent_spill_hours: 48},
  now: {label: 'low', risk: 0.02, discharging_upstream: 0, recent_upstream: 0, monitored_upstream: 8},
  water_temp_est: {temp_c: 7, date: DAYS[0], route: 'river_off_season', test: 'winter', typical_c: 1.6, within_c: 2},
  days: DAYS.map((d, i) => ({date: d, label: 'moderate', risk: 0.2, rain_48h_mm: 4, expected_spilling_overflows: 1, in_validated_season: false, p_ecoli_gt900: 0.3,
    ...(i === 0 ? day : {})})), ...extra});
const keys = (s, iso = DAYS[0]) => M.figuresShown(M.prepare({generated_at: GEN, spots: [s]}, NOW).spots[0], iso, NOW);

test('a river in winter, today with its winter word: the spill risk, its travel, the word and the winter water estimate', () => {
  assert.deepEqual(keys(spot({}, {ecoli_usual_winter: 'higher'})), ['spill', 'travel', 'ecoli-winter', 'water-temp-winter']);
  // Another day has no word, and no water estimate (today's only): the estimate's own row says it is not tested then.
  assert.deepEqual(keys(spot({}, {ecoli_usual_winter: 'higher'}), DAYS[4]), ['spill', 'travel', 'ecoli-off']);
});

test('in season the percentage is the figure; at a lake there is none', () => {
  const summer = spot({water_temp_est: {temp_c: 15, date: DAYS[0], route: 'river_model', within_c: 2}});
  summer.days.forEach(d => { d.in_validated_season = true; });
  assert.deepEqual(keys(summer), ['spill', 'travel', 'ecoli', 'water-temp-river']);
  const lake = spot({kind: 'lake', location: {mode: 'lake'}, water_temp_est: {temp_c: 15, date: DAYS[0], route: 'lake_curve', typical_c: 1.8}});
  lake.days.forEach(d => { d.in_validated_season = true; });
  assert.deepEqual(keys(lake), ['spill', 'travel', 'water-temp-lake']);
  const rows = M.testedRows(FIGS, lake, keys(lake));
  assert.deepEqual(rows.map(r => r.id), ['spill-risk', 'travel-lake', 'water-temp-lake-summer']);
  assert.equal(rows[1].said, 'Checked against samples: no gain shown');
});

test('a measured temperature, an untested route and a place with no daily level', () => {
  const sensed = spot({water_temp: {temp_c: 8.1, observed_at: '2026-11-24T12:00:00Z', where: 'at Ilkley'}});
  assert.deepEqual(keys(sensed), ['spill', 'travel', 'ecoli-off']);   // a reading is a measurement, with no row
  assert.deepEqual(keys(spot({water_temp_est: {temp_c: 7, date: DAYS[0], route: 'lake_off_season'}})).slice(-1), ['water-temp-untested']);
  const plain = spot({upstream_summary: {overflows: 0}, days: []});
  assert.deepEqual(keys(plain), ['water-temp-winter']);
  const untested = M.testedRows(FIGS, spot(), ['ecoli-off'])[0];
  assert.equal(untested.said, 'Not tested'); assert.equal(untested.tested_on, '');
  assert.deepEqual(M.testedRows(null, spot(), ['spill']), []);   // no file: no rows
  assert.deepEqual(M.testedRows(FIGS, spot(), ['no-such-figure']), []);   // a key with no row is left out
});

test('the built page holds the section, after the figures and before the record, with each row\'s lines', () => {
  const site = fs.mkdtempSync(path.join(os.tmpdir(), 'pv-tested-'));
  let out;
  try {
    fs.mkdirSync(path.join(site, 'data', 'spot'), {recursive: true}); fs.mkdirSync(path.join(site, 'data', 'upstream')); fs.mkdirSync(path.join(site, 'data', 'research')); fs.mkdirSync(path.join(site, 'preview'));
    fs.writeFileSync(path.join(site, 'data', 'spots-lite.json'), JSON.stringify({generated_at: GEN, spots: [spot({detail_file: 'spot/a.json'}, {ecoli_usual_winter: 'lower'})]}));
    fs.writeFileSync(path.join(site, 'data', 'spot', 'a.json'), JSON.stringify({id: 'a', contributors: []}));
    fs.writeFileSync(path.join(site, 'data', 'research', 'figures.json'), JSON.stringify(FIGS));
    out = prerender(site, '');
  } finally { fs.rmSync(site, {recursive: true, force: true}); }
  const page = out.spots.a, sec = page.slice(page.indexOf('id="tested"'), page.indexOf('</section>', page.indexOf('id="tested"')));
  assert.match(page, /<h2 id="tested-h">What each figure was tested on<\/h2>/);
  assert.deepEqual([...sec.matchAll(/<div class="tr" id="tested-([a-z-]+)">/g)].map(m => m[1]), ['spill-risk', 'travel-river', 'ecoli-river-winter', 'water-temp-winter']);
  assert.match(sec, /<span class="tr-basis">Tested on data it never saw<\/span>/);
  assert.match(sec, /<dd>Tested on: United Utilities&#39; overflows in 2025/);
  assert.match(sec, /<dd class="tr-gap">Not known: How much higher or lower/);
  assert.match(sec, /href="methods\.html#tested">Every figure, on the method page<\/a>/);
  assert.ok(page.indexOf('id="behind-h"') < page.indexOf('id="tested"') && page.indexOf('id="tested"') < page.indexOf('id="place"'));
});
