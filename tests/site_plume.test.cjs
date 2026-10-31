// The spill map (src/dipcast/site/plume.js, docs/PLUME-MAP-2026-10.md): a spill's water reaches the end of its route
// when the forecast says it reaches the spot, unconfirmed water is told apart, and the words always say it is a model
// estimate and never call the water clean or safe. The data step is tests/test_plume.py.
// node --test tests/site_plume.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const L = require('../src/dipcast/site/levels.js');
global.overflowNames = L.overflowNames;
global.companyName = L.companyName;
const P = require('../src/dipcast/site/plume.js');

const GEN = Date.parse('2026-10-31T18:00Z'), H = 36e5;
const row = (spills, extra = {}) => ({ site_id: 'A', name: 'MILL LANE/CSO', company: 'United Utilities', km: 10, travel_h: 10, weight: 0.4, state: 'live', spills, ...extra });
const ended = { start: '2026-10-31T06:00Z', end: '2026-10-31T08:00Z', running: false, end_known: true,
  arrival: { from: '2026-10-31T16:00Z', to: '2026-10-31T18:00Z', state: 'passed' } };
const running = { start: '2026-10-31T16:00Z', end: null, running: true, end_known: false, arrival: { from: '2026-11-01T02:00Z', to: null, state: 'due' } };
const unclosed = { start: '2026-10-31T10:00Z', end: null, running: false, end_known: false, end_after: '2026-10-31T11:00Z',
  arrival: { from: '2026-10-31T20:00Z', to: null, state: 'due' } };

test('the water reaches the end of its route after the travel time, and leaves it as the spill ends', () => {
  const [rel] = P.plumeReleases(ended, GEN);
  assert.deepEqual(P.plumeWater(rel, 10, Date.parse('2026-10-31T06:00Z')), null);   // not released yet
  const half = P.plumeWater(rel, 10, Date.parse('2026-10-31T11:00Z'));               // 5 h after the start: half way
  assert.equal(half.f1, 0.5); assert.equal(half.f0, 0.3); assert.equal(half.past, false);
  const at = P.plumeWater(rel, 10, Date.parse('2026-10-31T17:00Z'));                 // head past the spot, tail 90% down
  assert.equal(at.f1, 1); assert.ok(Math.abs(at.f0 - 0.9) < 1e-9); assert.equal(at.past, true);
  assert.equal(P.plumeWater(rel, 10, Date.parse('2026-10-31T18:00Z')), null);         // all passed: the replay's arrival end
  assert.equal(P.plumeStand(row([ended]), GEN, Date.parse('2026-10-31T17:00Z')), 'at');
  assert.equal(P.plumeStand(row([ended]), GEN, Date.parse('2026-10-31T12:00Z')), 'coming');
  assert.equal(P.plumeStand(row([ended]), GEN, Date.parse('2026-11-01T12:00Z')), 'passed');
  assert.equal(P.plumeStand(row([ended]), GEN, Date.parse('2026-11-03T12:00Z')), null);   // past recent_h: no longer counted
});

test('a spill running at the update is reported up to it and unconfirmed after it', () => {
  const rels = P.plumeReleases(running, GEN);
  assert.equal(rels.length, 2);
  assert.deepEqual([rels[0].sure, rels[0].b], [true, GEN]);
  assert.deepEqual([rels[1].sure, rels[1].b, rels[1].kept], [false, Infinity, true]);
  const later = P.plumeWater(rels[1], 10, GEN + 4 * H);   // water released after the update: from the overflow down
  assert.equal(later.f0, 0); assert.ok(Math.abs(later.f1 - 0.4) < 1e-9); assert.equal(later.sure, false);
});

test('an end the feed never gave is unconfirmed, from the last poll that saw it', () => {
  const rels = P.plumeReleases(unclosed, GEN);
  assert.deepEqual(rels.map(r => r.sure), [true, false]);
  assert.equal(rels[1].a, Date.parse('2026-10-31T11:00Z')); assert.equal(rels[1].b, GEN);
});

test('a lake route or a row with no travel time has no water drawn', () => {
  assert.equal(P.plumeStand(row([ended], { travel_h: null, lake_route: true }), GEN, GEN), null);
  assert.equal(P.plumeWater(P.plumeReleases(ended, GEN)[0], null, GEN), null);
});

test('the slider runs 48 h either side of the update on quarter hours', () => {
  const r = P.plumeRange(Date.parse('2026-10-31T18:14Z'));
  assert.equal(r.min, Date.parse('2026-10-29T18:00Z')); assert.equal(r.max, Date.parse('2026-11-02T18:15Z'));
  assert.equal(r.steps, 385);
});

test('the words say model estimate, count the gaps and never say clean or safe', () => {
  const some = P.plumeSaid([row([ended])], GEN, Date.parse('2026-10-31T17:00Z'), 2);
  assert.match(some, /reaching the spot/); assert.match(some, /Model estimate/); assert.match(some, /2 overflows upstream had no current reading/);
  const none = P.plumeSaid([row([ended])], GEN, Date.parse('2026-10-31T05:00Z'), 0);
  assert.match(none, /no reported spill's water is modelled/); assert.match(none, /not a measurement/);
  const doc = { pin: [54, -2.7], river_velocity_ms: 0.2, t90_hours: 72, overflows: [], unrouted: 1, gaps: [] };
  const replay = { overflows: [row([ended]), row([ended], { site_id: 'L', lake_route: true, travel_h: null })], quiet: { offline: { n: 3 } }, more_with_events: 2 };
  const html = P.plumeTile({ id: 'x' }, doc, replay, GEN, GEN);
  assert.match(html, new RegExp(P.PLUME_ESTIMATE.replace(/[.()]/g, '\\$&')));
  assert.match(html, /3 counted overflows have no current reading/);
  assert.match(html, /2 more overflows with reported spills or gaps/);
  assert.match(html, /1 route down to the spot could not be drawn/);
  assert.match(html, /crosses a lake/);
  for (const s of [some, none, html]) assert.doesNotMatch(s, /\b(clean|safe|safely)\b/i);
  assert.match(html, /<input type="range"[^>]*aria-label=/);
});

test('an official notice comes first', () => {
  global.eaTodayBrief = () => 'Advice against bathing'; global.eaTodayFirst = () => 'Follow it first';
  try {
    const html = P.plumeTile({ id: 'x' }, { pin: [54, -2], overflows: [], gaps: [] }, { overflows: [], quiet: {} }, GEN, GEN);
    assert.ok(html.indexOf('Official: Advice against bathing') < html.indexOf(P.PLUME_ESTIMATE));
    assert.match(html, /Follow it first; this map is SwimSignal's model estimate only/);
  } finally { delete global.eaTodayBrief; delete global.eaTodayFirst; }
});

test('a route is cut by fraction of its length', () => {
  const pts = [[54, -2], [54, -1.99], [54, -1.98]], cum = P.plumeMeasure(pts);
  const half = P.plumeSlice(pts, cum, 0, 0.5);
  assert.equal(half.length, 2); assert.ok(Math.abs(half[1][1] - -1.99) < 1e-9);
  assert.equal(P.plumeSlice(pts, cum, 0.6, 0.6).length, 0);
});

test('the page asks for plume.js only near the screen, and has no motion under reduced motion', () => {
  const page = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  assert.match(page, /function mountPlume\(d\)/);
  assert.match(page, /new IntersectionObserver/);
  assert.match(page, /'#overflows', '#plume-host'/);
  const src = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/plume.js'), 'utf8');
  assert.match(src, /prefers-reduced-motion: reduce/);
  assert.match(src, /if \(still\) play\.hidden = true/);
  for (const bad of ['box-shadow', 'linear-gradient', 'text-transform', 'letter-spacing']) assert.ok(!P.PLUME_CSS.includes(bad), bad);
});
