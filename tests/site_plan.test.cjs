// Plan a swim (src/dipcast/site/plan.js): the plan in the address, the places it starts from, and
// which spots it lists, in which order. The sentences each row gives are the page's (site_planner).
const {test} = require('node:test');
const assert = require('node:assert/strict');
const L = require('../src/dipcast/site/levels.js');
const P = require('../src/dipcast/site/plan.js');
L.setToday('2026-09-30');
const DATES = ['2026-09-30', '2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04'];

test('a plan survives the address it is written to, and your own position is never in it', () => {
  const plan = {day: '2026-10-03', from: {name: 'Newport, Isle of Wight', lat: 50.7, lon: -1.29}, within: 30, kind: 'lake'};
  assert.deepEqual(P.readPlan(P.planHash(plan), DATES), plan);
  const here = P.planHash({...plan, from: {here: true}});
  assert.match(here, /from=here/);
  assert.doesNotMatch(here, /at=/);
  assert.deepEqual(P.readPlan(here, DATES).from, {here: true});
  assert.equal(P.planHash({...plan, kind: 'all'}).includes('kind'), false);
});
test('an address with a plan is read on its own; one without keeps the plan last shown', () => {
  const was = {day: '2026-10-02', from: {name: 'Kendal', lat: 54.33, lon: -2.75}, within: 10, kind: 'lake'};
  assert.deepEqual(P.readPlan('', DATES, was), was);   // the header's link to plan/
  // A link to Ilkley's rivers and lakes is not Ilkley's lakes because lakes were picked a moment ago.
  assert.deepEqual(P.readPlan('#from=Ilkley&at=53.92,-1.82&within=30', DATES, was),
    {day: '2026-10-02', from: {name: 'Ilkley', lat: 53.92, lon: -1.82}, within: 30, kind: 'all'});
});
test('what an address cannot mean is left at the default', () => {
  const p = P.readPlan('#day=2026-12-25&within=7&kind=sea&from=Paris&at=48.86,2.35', DATES);
  assert.deepEqual(p, {day: DATES[0], from: null, within: 20, kind: 'all'});   // a day out of the forecast, a distance not offered, a place outside Britain
  assert.equal(P.readPlan('#from=Kendal', DATES).from, null);   // a name without a position
  assert.equal(P.readPlan('#within=0', DATES).within, 0);   // any distance
  assert.equal(P.readPlan('#from=' + 'x'.repeat(200) + '&at=54,-2', DATES).from.name.length, 80);
});

const index = P.placeIndex({places: [['Newport', 51.59, -3.0], ['Kendal', 54.33, -2.75], ['Ambleside', 54.43, -2.96],
  ['Pooley Bridge', 54.61, -2.82], ['Ynys Môn', 53.27, -4.33], ['Newport, Isle of Wight', 50.7, -1.29], ['Nowhere', 10, 10], 'junk']});
test('places are matched as typed, beginning first, without case, accents or punctuation counting', () => {
  assert.equal(index.length, 6);   // a position outside Britain, and an entry that is not a place, are dropped
  assert.deepEqual(P.placeMatches(index, 'new').map(p => p.name), ['Newport', 'Newport, Isle of Wight']);
  assert.deepEqual(P.placeMatches(index, 'BRIDGE').map(p => p.name), ['Pooley Bridge']);   // a later word
  assert.deepEqual(P.placeMatches(index, 'ynys mon').map(p => p.name), ['Ynys Môn']);
  assert.deepEqual(P.placeMatches(index, '  '), []);
  assert.equal(P.placeMatches(index, 'n', 1).length, 1);
});
test('a name on its own is the biggest place of that name; a name as offered is that place', () => {
  assert.equal(P.placeNamed(index, 'newport').lat, 51.59);
  assert.equal(P.placeNamed(index, 'Newport, Isle of Wight').lat, 50.7);
  assert.equal(P.placeNamed(index, 'Kendle'), null);
  assert.equal(P.placeNamed(index, ''), null);
});
test('postcodes are recognised, so the page can say they do not work yet', () => {
  for (const pc of ['LA22 9', 'la22', 'SW1A 1AA', 'M1', 'B33 8TH']) assert.equal(P.looksLikePostcode(pc), true, pc);
  for (const name of ['Bath', 'Ely', 'Kendal', 'A1 road']) assert.equal(P.looksLikePostcode(name), false, name);
});

// Spots on a line north of the start, a mile apart, with the levels given for 1 October.
const spot = (id, miles, l, extra = {}) => ({id, name: id, kind: 'river', source: 'curated', miles, upstream_summary: {overflows: 3},
  location: {mode: 'river'}, now: {label: 'low'}, ...extra,
  days: DATES.map(date => ({date, label: date === '2026-10-01' ? l : 'low', risk: {low: 0.05, moderate: 0.2, high: 0.5, 'very high': 0.8}[date === '2026-10-01' ? l : 'low']}))});
const milesOf = s => s.miles;
test('the spots nothing flags come first, nearest first, then the rest by level and distance', () => {
  const spots = [spot('far-low', 15, 'low'), spot('high', 3, 'high'), spot('near-low', 4, 'low'), spot('moderate', 9, 'moderate'),
    spot('clear', 6, 'low', {upstream_summary: {overflows: 0}}), spot('away', 40, 'low'), spot('failed', 2, 'low', {error: 'forecast failed: no rain'}),
    spot('poor', 1, 'low', {classification: {class: 'poor'}})];
  const r = P.planSpots(spots, {day: '2026-10-01', within: 20, kind: 'all'}, milesOf);
  assert.deepEqual(r.groups.map(g => g.map(o => o.s.id)), [['near-low', 'clear', 'far-low'], ['moderate', 'poor', 'high'], ['failed']]);
  assert.equal(r.count, 7);
  assert.equal(r.nearest, null);
  assert.deepEqual(r.groups[0].map(o => o.level), ['low', L.NO_OVERFLOWS, 'low']);
  assert.equal(P.planSpots(spots, {day: '2026-10-01', within: 0, kind: 'all'}, milesOf).count, 8);   // any distance
});
test('the kind narrows the plan; with nothing in reach, the nearest of that kind is named', () => {
  const spots = [spot('river', 2, 'low'), spot('lake', 25, 'low', {kind: 'lake'}), spot('bw', 31, 'low', {kind: 'lake', source: 'designated'})];
  const lakes = P.planSpots(spots, {day: '2026-10-01', within: 20, kind: 'lake'}, milesOf);
  assert.equal(lakes.count, 0);
  assert.equal(lakes.nearest.s.id, 'lake');
  assert.equal(P.reachFor(lakes.nearest.miles), 30);
  assert.deepEqual(P.planSpots(spots, {day: '2026-10-01', within: 50, kind: 'designated'}, milesOf).groups[0].map(o => o.s.id), ['bw']);
  assert.equal(P.planSpots([], {day: '2026-10-01', within: 5, kind: 'all'}, milesOf).nearest, null);
});
test('another day is suggested only when clearly more of the spots are low then', () => {
  // On 1 October: a spots high, the rest low; every other day all low.
  const mk = (n, high) => Array.from({length: n}, (_, i) => spot('s' + i, i, i < high ? 'high' : 'low'));
  assert.deepEqual(P.betterDay(mk(4, 3), '2026-10-01', DATES), {date: '2026-09-30', low: 4, was: 1});
  assert.equal(P.betterDay(mk(19, 1), '2026-10-01', DATES), null);   // 19 against 18
  assert.equal(P.betterDay(mk(4, 3), '2026-09-30', DATES), null);   // the day picked is the best
  // Spots whose forecast does not change from day to day do not count.
  assert.equal(P.betterDay([spot('clear', 1, 'low', {upstream_summary: {overflows: 0}})], '2026-10-01', DATES), null);
});
test('distances read as a person says them', () => {
  assert.deepEqual([0.4, 1, 1.04, 7.66, 12.4].map(P.milesAway), ['under a mile away', '1 mile away', '1 mile away', '7.7 miles away', '12 miles away']);
  assert.deepEqual([3, 5, 21, 50, 51].map(P.reachFor), [5, 5, 30, 50, 0]);
});
