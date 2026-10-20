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
// Compare these spots (20 Oct 2026): an open comparison is in the address, so a shared link opens on it.
test('a comparison survives the address, and is there only while it is open', () => {
  const plan = {day: '2026-10-03', from: {name: 'Oxford', lat: 51.752, lon: -1.2577}, within: 30, kind: 'all',
    compare: ['osm-thames-long-bridges', 'bw-ukj1403-11947', 'thames-port-meadow']};
  const hash = P.planHash(plan);
  assert.equal(hash, '#day=2026-10-03&from=Oxford&at=51.752%2C-1.2577&within=30&compare=osm-thames-long-bridges%2Cbw-ukj1403-11947%2Cthames-port-meadow');
  assert.deepEqual(P.readPlan(hash, DATES), plan);
  // Closed: no compare in the address, and none read from it.
  const {compare, ...closed} = plan;
  assert.doesNotMatch(P.planHash(closed), /compare/);
  assert.deepEqual(P.readPlan(P.planHash(closed), DATES), closed);
  // Open with nothing chosen yet: open, on the first spots shown (planCompareIds).
  assert.deepEqual(P.readPlan('#from=Oxford&at=51.752,-1.2577&compare=', DATES).compare, []);
  // At most three, each once, none empty or absurdly long.
  assert.deepEqual(P.readPlan('#compare=a,,a,b,' + 'x'.repeat(101) + ',c,d', DATES).compare, ['a', 'b', 'c']);
  // The header's link (no plan in the address) keeps the comparison last shown, as it keeps the rest.
  assert.deepEqual(P.readPlan('', DATES, plan).compare, plan.compare);
  // A plan's link without one is read on its own: the comparison open a moment ago is not carried over.
  assert.equal('compare' in P.readPlan('#from=Ilkley&at=53.92,-1.82&within=30', DATES, plan), false);
});
test('a comparison shows the spots asked for that are still in the plan, else the first three shown', () => {
  const shown = ['a', 'b', 'c', 'd', 'e'].map(id => ({id}));
  assert.deepEqual(P.planCompareIds(undefined, shown), ['a', 'b', 'c']);           // the default: the first three shown
  assert.deepEqual(P.planCompareIds([], shown), ['a', 'b', 'c']);
  assert.deepEqual(P.planCompareIds(['e', 'b'], shown), ['e', 'b']);               // two chosen, in the order chosen
  assert.deepEqual(P.planCompareIds(['d', 'gone', 'd', 'a', 'c'], shown), ['d', 'a', 'c']);   // out of reach, or twice: dropped
  assert.deepEqual(P.planCompareIds(['e', 'gone'], shown), ['e', 'a', 'b']);       // one left: filled from the top to three
  assert.deepEqual(P.planCompareIds(['gone'], shown.slice(0, 2)), ['a', 'b']);     // a plan of two
  assert.deepEqual(P.planCompareIds(['a'], shown.slice(0, 1)), ['a']);              // one spot: the page offers no comparison
});
// The day strip (index.html, planStrip; 20 Oct 2026) writes the day it marks to the address as day= did
// with the select, and a link opens on that day.
test('each of the five days the strip offers survives the address', () => {
  const plan = {from: {name: 'Oxford', lat: 51.752, lon: -1.2577}, within: 30, kind: 'all'};
  for (const day of DATES) {
    assert.match(P.planHash({...plan, day}), new RegExp(`^#day=${day}&`));
    assert.equal(P.readPlan(P.planHash({...plan, day}), DATES).day, day);
  }
  assert.equal(P.readPlan('#day=2026-10-09&from=Oxford&at=51.752,-1.2577', DATES).day, DATES[0]);   // a day the strip does not offer: the first
  assert.equal(P.readPlan('#from=Oxford&at=51.752,-1.2577', DATES, {day: DATES[3]}).day, DATES[3]);   // none in the link: the day last marked
});
test('what an address cannot mean is left at the default', () => {
  const p = P.readPlan('#day=2026-12-25&within=7&kind=sea&from=Paris&at=48.86,2.35', DATES);
  assert.deepEqual(p, {day: DATES[0], from: null, within: 20, kind: 'all'});   // a day out of the forecast, a distance not offered, a place outside Britain
  assert.equal(P.readPlan('#from=Kendal', DATES).from, null);   // a name without a position
  assert.equal(P.readPlan('#within=0', DATES).within, 0);   // any distance
  assert.equal(P.readPlan('#from=' + 'x'.repeat(200) + '&at=54,-2', DATES).from.name.length, 80);
});
// The plan last shown, kept in this browser (index.html, PLAN_KEY), opens again after a reload or on a later
// visit: until 20 Oct 2026 the header's link then opened an empty plan (post-deploy QA).
test('the plan kept in this browser opens again: a day gone by is left for today, and a day picked on the list comes first', () => {
  const plan = {day: DATES[2], from: {name: 'Kendal', lat: 54.33, lon: -2.75}, within: 10, kind: 'lake', compare: ['a', 'b']};
  const kept = P.planHash(plan);
  assert.deepEqual(P.planKept(kept, DATES), plan);
  assert.equal(P.planKept(kept, DATES, DATES[4]).day, DATES[4]);   // the day picked on the list in this visit
  assert.equal(P.planKept(kept, DATES, null).day, DATES[2]);       // "Today and tomorrow" on the list: the plan's own day
  const later = DATES.slice(3);                                    // a later visit, the plan's day gone by
  assert.equal(P.planKept(kept, later).day, null);
  assert.equal(P.readPlan('', later, P.planKept(kept, later)).day, later[0]);   // the header's link: the first day, the rest kept
  assert.deepEqual(P.readPlan('', later, P.planKept(kept, later)).from, plan.from);
  // Your own location is never kept: "here" asks again (index.html, planLocate).
  assert.deepEqual(P.planKept(P.planHash({...P.PLAN_DEFAULT, from: {here: true}}), DATES).from, {here: true});
  // Nothing kept, storage refused, or something no address could mean: the empty plan.
  assert.deepEqual(P.planKept(null, DATES), P.PLAN_DEFAULT);
  assert.deepEqual(P.planKept('#from=Paris&at=48.86,2.35&day=x', DATES), P.PLAN_DEFAULT);
  // The page starts its first plan from the kept one, and writes each plan shown back, with the address.
  const app = require('node:fs').readFileSync(require('node:path').join(__dirname, '..', 'src', 'dipcast', 'site', 'index.html'), 'utf8');
  assert.ok(app.includes("if (!PLAN_READ) { PLAN = planKept(stored(PLAN_KEY), planDates(), VIEW.day); PLAN_READ = true; }"));
  assert.ok(app.includes('try { localStorage.setItem(PLAN_KEY, h); }') && app.includes("const PLAN_KEY = 'dipcast.plan';"));
  assert.ok(!app.includes("history.replaceState(history.state, '', planPath() + planHash(PLAN))"));   // every write goes through planAddress
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
test('low risk first, then no monitored overflow found upstream, nearest first, then the rest by level and distance', () => {
  const spots = [spot('far-low', 15, 'low'), spot('high', 3, 'high'), spot('near-low', 4, 'low'), spot('moderate', 9, 'moderate'),
    spot('clear', 6, 'low', {upstream_summary: {overflows: 0}}), spot('away', 40, 'low'), spot('failed', 2, 'low', {error: 'forecast failed: no rain'}),
    spot('poor', 1, 'low', {classification: {class: 'poor'}})];
  const r = P.planSpots(spots, {day: '2026-10-01', within: 20, kind: 'all'}, milesOf);
  assert.deepEqual(r.groups.map(g => g.map(o => o.s.id)), [['near-low', 'far-low'], ['clear'], ['moderate', 'poor', 'high'], ['failed']]);
  assert.equal(r.count, 7);
  assert.equal(r.nearest, null);
  assert.deepEqual(r.groups[0].map(o => o.level), ['low', 'low']);
  assert.deepEqual(r.groups[1].map(o => o.level), [L.NO_OVERFLOWS]);   // never under a "low" heading (20 Oct 2026)
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

test('the search finds a river or lake by its name, its other name or the town it is near, never by a generic word', () => {
  const doc = {waters: [
    ['River Derwent', '', 'river', 'Malton', 54.0, -0.89, 54.17, -0.73, 54.0954, -0.8326, 119],
    ['River Derwent', '', 'river', 'Wirksworth', 52.87, -1.7, 53.36, -1.32, 53.0987, -1.5289, 92],
    ['River Wye', 'Afon Gwy', 'river', 'Monmouth', 51.62, -3.04, 52.12, -2.56, 51.8362, -2.6701, 125],
    ['River Kennet', '', 'river', 'Hungerford', 51.39, -1.85, 51.47, -1.03, 51.42, -1.5, 107],
    ['Rydal Water', '', 'lake', 'Ambleside', 54.44, -3.0, 54.45, -2.99, 54.4455, -2.9916, 1],
    ['Nowhere Beck', '', 'river', 'Paris', 48.8, 2.3, 48.9, 2.4, 48.85, 2.35, 3],   // outside GB: dropped
  ]};
  const ix = P.waterIndex(doc), names = q => P.waterMatches(ix, q).map(w => `${w.name} / ${w.near}`);
  assert.equal(ix.length, 5);
  assert.deepEqual(ix[3].box, [[51.39, -1.85], [51.47, -1.03]]);
  assert.equal(ix[4].kind, 'lake');
  assert.deepEqual(names('kennet'), ['River Kennet / Hungerford']);
  assert.deepEqual(names('River  KENNET'), ['River Kennet / Hungerford']);
  assert.deepEqual(names('derwent'), ['River Derwent / Malton', 'River Derwent / Wirksworth']);   // the longest first
  assert.deepEqual(names('derwent wirks'), ['River Derwent / Wirksworth']);   // the town tells them apart
  assert.deepEqual(names('gwy'), ['River Wye / Monmouth']);   // the other name
  assert.deepEqual(names('rydal'), ['Rydal Water / Ambleside']);
  assert.deepEqual(names('river'), []);   // a generic word alone
  assert.deepEqual(names('water'), []);
  assert.deepEqual(names('malton'), []);   // a town alone is offered as a place, not as its rivers
  assert.deepEqual(names('ke'), []);   // under three letters
  assert.equal(P.waterMatches(ix, 'derwent', 1).length, 1);
  assert.deepEqual(P.waterIndex(null), []);
});
