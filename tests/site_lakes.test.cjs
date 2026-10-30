// Satellite lake observations (src/dipcast/site/lakes.js, the viewer on lakes.html): what a monitoring location's
// readings say, and only that. Three records cut from the research export (tests/fixtures/lake_observations_v1_sample.json,
// docs/LAKE-OBSERVATIONS-CONTRACT-v1.md): Derwent Water at Crow Park (every image read), Barton Broad (images chosen
// near laboratory samples) and a location too narrow for a reading.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const K = require('../src/dipcast/site/lakes.js');

const DOC = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'lake_observations_v1_sample.json'), 'utf8'));
const lake = id => DOC.lakes.find(x => x.lake_id === id);
const FULL = lake('bw-ukd1101-45800'), SEL = lake('wqa-AN-ANT160'), SMALL = lake('bw-uki1101-11910');
const plain = h => h.replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').replace(/&#39;/g, "'");

test('how old a reading is goes by its image date on the day the page is read, so a frozen file never stays recent', () => {
  const L = { date: '2026-09-30' }, R = DOC.freshness_rules;
  assert.deepEqual(K.lakesFresh(L, '2026-10-05', R), { age: 5, freshness: 'recent' });
  assert.deepEqual(K.lakesFresh(L, '2026-10-30', R), { age: 30, freshness: 'older' });
  assert.deepEqual(K.lakesFresh(L, '2027-03-01', R), { age: 152, freshness: 'stale' });
  assert.deepEqual(K.lakesFresh(null, '2026-10-30', R), { age: null, freshness: 'none' });
  // The same record read on two days says two ages: the export's own age_days is never shown.
  assert.match(plain(K.lakesLatest(FULL, DOC, '2027-03-01')), /152 days ago \(stale: more than two months old\)/);
});

test('a full record says latest image read; a selected one says historical dataset, with the selection beside it', () => {
  const full = plain(K.lakesLatest(FULL, DOC, '2026-10-30')), sel = plain(K.lakesLatest(SEL, DOC, '2026-10-30'));
  assert.match(full, /^Latest usable image read: 30 Sept 2026, 11:26 UTC, 30 days ago \(older\)\./);
  assert.doesNotMatch(full, /historical dataset|chosen near laboratory/);
  assert.match(sel, /^Latest in this historical dataset: /);
  // The selection comes before any figure, and says what it is not.
  assert.ok(sel.indexOf(K.LAKES_SELECTED) > 0 && sel.indexOf(K.LAKES_SELECTED) < sel.indexOf('NDCI'));
  assert.match(K.LAKES_SELECTED, /not every image: its readings and season medians are not full monitoring of the lake/);
  // The seasons table and the chart say so too.
  assert.match(plain(K.lakesSeasons(SEL)), /The selected images each season \(near laboratory sample dates, not every image\)/);
  assert.match(plain(K.lakesChart(SEL.series, 600, true)), /gaps between dots are not gaps in the satellite record, and the dots are not a trend/);
  assert.doesNotMatch(plain(K.lakesChart(FULL.series, 600, false)), /not gaps in the satellite record/);
});

test('every gap says why: too narrow for the pixels, the season closed, not refreshed', () => {
  const t = plain(K.lakesLatest(SMALL, DOC, '2026-10-30'));
  assert.match(t, /^No usable satellite reading at this location\./);
  assert.match(t, /too narrow for the satellite's 20 m pixels/);
  assert.match(t, /Images are read for May to September only/);
  assert.match(t, /No newer images have been read since this export, which runs to 30 Sept 2026\./);
});

test('the summary counts monitoring locations and water bodies, and anchors the date the images run to', () => {
  const index = { ...DOC, available: true };
  const t = plain(K.lakesSummary(index, '2026-10-30'));
  assert.match(t, /^3 monitoring locations on 3 named waters; 2 have a usable reading\. Every image was read at 2 of them; at the other one, only images near laboratory sample dates\./);
  assert.match(t, /Images are read up to 30 Sept 2026: this is a historical dataset, and nothing after that date is in it\./);
  assert.doesNotMatch(t, /\blakes?\b/i);   // locations, not lakes: several can share one water body
  // Two locations on one water body count once.
  const two = { ...index, lakes: [FULL, { ...FULL, lake_id: 'bw-other' }] };
  assert.match(plain(K.lakesSummary(two, '2026-10-30')), /^2 monitoring locations on 1 named water;/);
  assert.match(plain(K.lakesSummary({ available: false, why: 'no export in this build' }, '2026-10-30')), /No satellite observations are published in this update \(no export in this build\)\./);
});

test('laboratory values are measurements, shown apart, in their own unit, with censoring said', () => {
  const t = plain(K.lakesLab(SEL, DOC));
  assert.match(t, /^Measured in a laboratory/);
  assert.match(t, /µg\/l/);
  assert.match(t, /These are measurements; the satellite index above is not, and the two are not on one scale\./);
  const censored = { ...SEL, lab: [{ sample_time: '2024-06-01T10:00:00', value: 2, censored: '<', purpose: 'x' }] };
  assert.match(plain(K.lakesLab(censored, DOC)), /below 2/);
  assert.equal(K.lakesLab(FULL.lab.length ? { ...FULL, lab: [] } : FULL, DOC), '');
});

test('nothing reads as safe, algae-free or a chlorophyll figure; the approved sentence stands beside the reading', () => {
  for (const L of [FULL, SEL, SMALL]) {
    const t = plain(K.lakesLake(L, DOC, '2026-10-30', 600));
    assert.doesNotMatch(t, /\bsafe\b|algae-free|\bclean\b|no algae|toxin-free/i);
    if (L.latest.date) assert.ok(t.includes(DOC.claim.public_wording));
    assert.doesNotMatch(t.replace(/Measured in a laboratory[\s\S]*$/, ''), /µg\/l/);   // the unit only in the lab block
  }
});

test('the picker groups full records first and calls each a monitoring location', () => {
  const html = K.lakesPicker({ lakes: DOC.lakes }, 'wqa-AN-ANT160');
  assert.match(html, /Monitoring location<select/);
  assert.ok(html.indexOf('every image read') < html.indexOf('images near lab samples only'));
  assert.match(html, /value="wqa-AN-ANT160" selected/);
});

test('a season with no images between the first and the last is said, not left out', () => {
  const ys = K.lakesYears([{ year: 2020, scenes: 1 }, { year: 2023, scenes: 2 }]);
  assert.deepEqual(ys.map(y => [y.year, !!y.missing]), [[2020, false], [2021, true], [2022, true], [2023, false]]);
  assert.match(plain(K.lakesSeasons(FULL)), /2022No images read this season\./);
  assert.match(K.lakesChart([{ date: '2021-06-01', ndci: 0.1 }, { date: '2023-06-01', ndci: 0.2 }], 600), /No clear image this season/);
});
