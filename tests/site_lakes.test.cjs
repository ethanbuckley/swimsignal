// Satellite lake observations (src/dipcast/site/lakes.js, the viewer on lakes.html): what a monitoring location's
// readings say, and only that. Five records cut from the research export, contract 1.1
// (tests/fixtures/lake_observations_v1_sample.json, docs/LAKE-OBSERVATIONS-CONTRACT-v1.md): Derwent Water at Crow Park
// (every image read), Barton Broad (images chosen near laboratory samples), a location too narrow for a reading, and
// the two Rutland Water locations, one of them read again in October (out of season, experimental).
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const K = require('../src/dipcast/site/lakes.js');

const DOC = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'lake_observations_v1_sample.json'), 'utf8'));
const lake = id => DOC.lakes.find(x => x.lake_id === id);
const FULL = lake('bw-ukd1101-45800'), SEL = lake('wqa-AN-ANT160'), SMALL = lake('bw-uki1101-11910'), RUT = lake('bw-ukf2208-09702');
const plain = h => h.replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').replace(/&#39;/g, "'");

test('how old a reading is goes by its image date on the day the page is read, so a frozen file never stays recent', () => {
  const L = { date: '2026-09-30' }, R = DOC.freshness_rules;
  assert.deepEqual(K.lakesFresh(L, '2026-10-05', R), { age: 5, freshness: 'recent' });
  assert.deepEqual(K.lakesFresh(L, '2026-10-30', R), { age: 30, freshness: 'older' });
  assert.deepEqual(K.lakesFresh(L, '2027-03-01', R), { age: 152, freshness: 'stale' });
  assert.deepEqual(K.lakesFresh(null, '2026-10-30', R), { age: null, freshness: 'none' });
  // The export says Rutland's October reading is "recent" as of 30 Oct; read in March, the page says stale.
  assert.equal(RUT.latest.freshness, 'recent');
  assert.match(plain(K.lakesLatest(RUT, DOC, '2027-03-01')), /125 days ago \(stale: more than two months old\)/);
});

test('the latest is the latest in the dataset; a selected series says historical dataset, with the selection beside it', () => {
  const full = plain(K.lakesLatest(FULL, DOC, '2026-10-30')), sel = plain(K.lakesLatest(SEL, DOC, '2026-10-30'));
  assert.ok(full.startsWith(`Latest in this dataset: ${K.lakesTime(FULL.latest.datetime)}, 30 days ago (older).`));
  assert.doesNotMatch(full, /historical dataset|chosen near laboratory|experimental/);
  assert.match(sel, /^Latest in this historical dataset: /);
  assert.ok(sel.indexOf(K.LAKES_SELECTED) > 0 && sel.indexOf(K.LAKES_SELECTED) < sel.indexOf('NDCI'));
  assert.match(plain(K.lakesSeasons(SEL)), /The selected images each season \(near laboratory sample dates, not every image\)/);
  assert.match(plain(K.lakesChart(SEL.series, 600, true)), /gaps between dots are not gaps in the satellite record, and the dots are not a trend/);
});

test('an out-of-season reading is experimental, said before its figure, and drawn hollow on a widened axis', () => {
  const t = plain(K.lakesLatest(RUT, DOC, '2026-10-30'));
  assert.match(t, /^Latest in this dataset: 27 Oct 2026, 11:16 UTC, 3 days ago \(recent\)\./);
  assert.ok(t.indexOf(K.LAKES_EXPERIMENTAL) > 0 && t.indexOf(K.LAKES_EXPERIMENTAL) < t.indexOf('NDCI'));
  assert.doesNotMatch(t, /Images are read for May to September, the season/);   // not said beside a reading from October
  const svg = K.lakesChart(RUT.series, 600);
  assert.equal((svg.match(/class="lk-dot-exp"/g) || []).length, 4);
  assert.match(svg, />Oct</);
  assert.match(plain(svg), /Hollow dots are from outside May to September, experimental\./);
  // The refresh, and the clear image left out, with why: not an observation of the water.
  assert.equal(plain(K.lakesRefreshed(RUT)),
    'Images from 1 Oct 2026 to 30 Oct 2026 were read later: 18 images, 4 shown. 1 clear image left out (1 for too little of the water classed as water): not shown, and not an observation of the water.');
  assert.equal(K.lakesRefreshed(FULL), '');
  // The season's own line keeps to the season: October is the refresh's sentence, not "May to September up to 30 Oct".
  assert.match(plain(K.lakesLake(RUT, DOC, '2026-10-30', 600, DOC)), /Every image from May to September was read here, up to 30 Sept 2026\./);
});

test("only one reading a date is drawn: the test's primary rule", () => {
  const dup = [{ date: '2025-06-01', ndci: 0.1, primary: true }, { date: '2025-06-01', ndci: 0.3, primary: false }, { date: '2025-07-01', ndci: 0.2 }];
  assert.deepEqual(K.lakesShown(dup).map(p => p.ndci), [0.1, 0.2]);   // a reading from before 1.1 has no `primary`, and is shown
});

test('locations sharing a water body say so, by name, and are counted as locations on named waters', () => {
  assert.match(plain(K.lakesShares(RUT, DOC)), /^Rutland Water has 1 other location here: Rutland Water[^.]*\. They share images and weather, so they are not independent readings of separate lakes\.$/);
  assert.equal(K.lakesShares(FULL, DOC), '');
  const t = plain(K.lakesSummary({ ...DOC, available: true }, '2026-10-30'));
  // Five locations, four named waters: the two Rutland locations are one water.
  assert.match(t, /^5 monitoring locations on 4 named waters; 4 have a usable reading\. Every image was read at 4 of them; at the other one, only images near laboratory sample dates\./);
  assert.match(t, /This is a historical dataset: images are read up to 30 Sept 2026, and to 30 Oct 2026 at 1 location read again later\. Nothing after that is in it\./);
  assert.doesNotMatch(t, /\blakes?\b/i);
  assert.match(plain(K.lakesSummary({ available: false, why: 'no export in this build' }, '2026-10-30')), /No satellite observations are published in this update \(no export in this build\)\./);
});

test('every gap says why, and how far one reading can be trusted is said under the dots', () => {
  const t = plain(K.lakesLatest(SMALL, DOC, '2026-10-30'));
  assert.match(t, /^No usable satellite reading at this location\./);
  assert.match(t, /too narrow for the satellite's 20 m pixels/);
  assert.match(t, /No images after 30 Sept 2026 have been read here\./);
  assert.match(plain(K.lakesQuality(DOC)), /^Two readings of one location on the same date differ by 0\.03 in the middle case, and by 0\.17 or more one time in ten \(393 pairs\)\. So a small change between dates may be the measurement, not the water\.$/);
  assert.match(plain(K.lakesSeasons(FULL)), /2022No images read this season\./);
});

test('laboratory values are measurements, shown apart, in their own unit, with censoring said', () => {
  const t = plain(K.lakesLab(SEL, DOC));
  assert.match(t, /^Measured in a laboratory/);
  assert.match(t, /µg\/l/);
  assert.match(t, /These are measurements; the satellite index above is not, and the two are not on one scale\./);
  const censored = { ...SEL, lab: [{ sample_time: '2024-06-01T10:00:00', value: 2, censored: '<', purpose: 'x' }] };
  assert.match(plain(K.lakesLab(censored, DOC)), /below 2/);
});

test('nothing reads as safe, algae-free or a chlorophyll figure; the approved sentence stands beside every reading', () => {
  for (const L of DOC.lakes) {
    const t = plain(K.lakesLake(L, DOC, '2026-10-30', 600, DOC));
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
