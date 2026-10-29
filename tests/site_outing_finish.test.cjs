// A paddle's finish (Swim Together S4): another listed river spot downstream, picked for a paddle or a board, with
// what drains into the water between in three groups the build works out (src/dipcast/stretches.py), never as a level.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const L = require('../src/dipcast/site/levels.js');
const P = require('../src/dipcast/site/plan.js');
const O = require('../src/dipcast/site/outing.js');
L.setToday('2026-10-26');
const DATES = ['2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30'];
const BASE = '#day=2026-10-28&from=Ilkley&at=53.92,-1.82&within=20&spot=wharfe-ilkley';

test('a finish is read only for a paddle or a board, and only with its own start', () => {
  assert.equal(P.readPlan(`${BASE}&act=paddle&finish=wharfe-greenholme`, DATES).finish, 'wharfe-greenholme');
  assert.equal(P.readPlan(`${BASE}&act=sup&finish=wharfe-greenholme`, DATES).finish, 'wharfe-greenholme');
  assert.equal('finish' in P.readPlan(`${BASE}&finish=wharfe-greenholme`, DATES), false);   // a swim has no finish
  assert.equal('finish' in P.readPlan(`${BASE}&act=paddle&finish=wharfe-ilkley`, DATES), false);   // not its own start
  assert.equal('finish' in P.readPlan('#day=2026-10-28&act=paddle&finish=wharfe-greenholme', DATES), false);   // no start
  const p = P.readPlan(`${BASE}&act=paddle&finish=wharfe-greenholme`, DATES);
  assert.match(P.planHash(p), /&act=paddle&finish=wharfe-greenholme/);
  // A different finish is a different outing (a link with one is not your own).
  assert.notEqual(P.planOutingKey(p), P.planOutingKey({...p, finish: undefined}));
  // A new start drops the finish, as it does where to meet.
  assert.equal('finish' in O.outingChanged({...p, meet: 'parking'}, 'spot'), false);
  assert.equal(O.outingChanged(p, 'when').finish, 'wharfe-greenholme');
});

test('the finishes offered are the listed ones the build traced, nearest first', () => {
  const byId = new Map([['wharfe-greenholme', {name: 'River Wharfe, Greenholme'}], ['wharfe-wilderness', {name: 'Wharfe at Wilderness Carpark'}]]);
  assert.deepEqual(O.outingFinishes({downstream: [['wharfe-greenholme', 5.5], ['gone', 9], ['wharfe-wilderness', 39.8]]}, byId),
    [{id: 'wharfe-greenholme', name: 'River Wharfe, Greenholme', km: 5.5}, {id: 'wharfe-wilderness', name: 'Wharfe at Wilderness Carpark', km: 39.8}]);
  assert.deepEqual(O.outingFinishes({}, byId), []);
  const tile = O.outingSection({day: DATES[2], spot: 'a', act: 'paddle', groups: [], backupGroups: [], missing: [], issued: '', open: true,
    main: {id: 'a', name: 'Ilkley', href: '', tone: 'low', headline: 'Low', meta: ''}, finishes: [], nowMs: 0});
  assert.match(tile, /No listed spot downstream of Ilkley that SwimSignal can trace the route to, so there is no finish to pick\./);
  const swim = O.outingSection({day: DATES[2], spot: 'a', groups: [], backupGroups: [], missing: [], issued: '', open: true,
    main: {id: 'a', name: 'Ilkley', href: '', tone: 'low', headline: 'Low', meta: ''}, finishes: null, nowMs: 0});
  assert.doesNotMatch(swim, /Finish/);
});

const rows = new Map([['R1', {site_name: 'Ilkley STW', company: 'Yorkshire Water', receiving_watercourse: 'River Wharfe', has_live: true}],
  ['S1', {site_name: 'Burley CSO', company: 'Yorkshire Water', receiving_watercourse: 'Mill Beck', has_live: false}],
  ['S2', {site_name: 'Canal side', company: 'Yorkshire Water', receiving_watercourse: 'Leeds and Liverpool Canal', has_live: true}]]);
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();

test('the stretch says what is on the route, what joins it, and that neither level is the water between', () => {
  const st = {to: 'g', km: 5.5, route: [['R1', 1.2]], side: [['S1', 4.1], ['S2', null]], above: 16};
  const t = text(O.outingStretch({start: 'Ilkley', finish: 'Greenholme', st, rows, state: 'ok'}));
  assert.match(t, /Between Ilkley and Greenholme About 5\.5 km down the river, by the way the water goes\./);
  assert.match(t, /On the route: 1 monitored overflow\. Ilkley STW \(Yorkshire Water\), 1\.2 km below the start/);
  assert.match(t, /From side streams or another arm of the river: 2\. Their water reaches the finish, and the route below where each joins\./);
  assert.match(t, /Burley CSO, on Mill Beck, joining 4\.1 km below the start, no live feed/);
  assert.match(t, /Canal side, on Leeds and Liverpool Canal, reaching the finish another way/);
  assert.match(t, /Above the start: 16 more, counted in both spots' levels\./);
  assert.match(t, /The finish's level counts all of these; the start's counts only those above it\. Neither is a level for the water between/);
  assert.match(t, /from side streams only those within 60 km of the finish by water: not unmonitored outfalls, or farm and road runoff\./);
  // None on the route is said as none known, not as none.
  assert.match(text(O.outingStretch({start: 'A', finish: 'B', st: {km: 2.7, route: [], side: [], above: 8}, rows, state: 'ok'})),
    /On the route: no monitored overflow that SwimSignal knows of\./);
  // A long list is cut, and says how many more.
  const many = {km: 40, route: Array.from({length: 11}, (_, i) => [`X${i}`, i]), side: [], above: 0};
  assert.match(text(O.outingStretch({start: 'A', finish: 'B', st: many, rows, state: 'ok'})), /and 3 more\./);
  assert.match(text(O.outingStretch({start: 'A', finish: 'B', state: 'missing'})), /could not be loaded here/);
});

test('the build puts the stretches in each spot\'s own file and the finishes in the lite one', () => {
  const build = fs.readFileSync(path.join(__dirname, '../scripts/build_site.py'), 'utf8');
  assert.match(build, /DETAIL_FIELDS = \("contributors", "guide", "measured", "linked", "seasonal", "stretches"\)/);
  assert.match(build, /health\["stretches"\] = attach_stretches\(results, spots, upstream, _net\(\), _overflows\(\)\)/);
  const privacy = fs.readFileSync(path.join(__dirname, '../src/dipcast/pages/privacy.html'), 'utf8');
  assert.ok(privacy.includes('the spot where a paddle finishes'));
});

// ------------------------------------------------------------------------------ the finish is followed like the spot
const W = require('../src/dipcast/site/outingwatch.js');
const K = require('../src/dipcast/site/outingpack.js');

test('a shared link stamps the finish\'s level, and the invitation compares it', () => {
  const plan = P.readPlan(`${BASE}&act=paddle&finish=wharfe-greenholme`, DATES);
  const main = {name: 'Ilkley', lat: 53.92, lon: -1.82};
  const shared = O.outingShared(plan, main, {sent: '20261026T0700Z', lv: 'low', flv: 'moderate'});
  assert.equal(shared.flv, 'moderate');
  // No stamp at all when the finish's level is missing: a stamp that is not whole would compare half the outing.
  assert.equal('sent' in O.outingShared(plan, main, {sent: '20261026T0700Z', lv: 'low'}), false);
  const back = P.readPlan(P.planHash(shared), DATES);
  assert.equal(back.flv, 'moderate');
  assert.deepEqual(W.outingWatchShared(back).items.map(i => [i.id, i.level]), [['wharfe-ilkley', 'low'], ['wharfe-greenholme', 'moderate']]);
  // Any change drops it with the rest of the stamp; a finish without its own level reads none.
  assert.equal('flv' in O.outingChanged(back, 'when'), false);
  assert.equal('flv' in P.readPlan(`${BASE}&sent=20261026T0700Z&lv=low&flv=low`, DATES), false);
});

test('the note, the alerts and the offline copy follow the finish', () => {
  const day = DATES[2], mk = (id, name) => ({id, name, kind: 'river', upstream_summary: {overflows: 1}, location: {mode: 'river'}, official: [],
    now: {label: 'low', risk: 0}, days: DATES.map(date => ({date, label: 'low', risk: 0.05}))});
  const a = mk('a', 'Ilkley'), f = mk('f', 'Greenholme'), b = mk('b', 'Backup');
  const note = W.outingWatchNote(null, {day}, {main: a, finish: f, backup: b}, new Date(2026, 9, 26, 7).toISOString(), Date.now());
  assert.deepEqual(note.items.map(i => i.id), ['a', 'f', 'b']);
  assert.equal(W.outingWatchRead(JSON.stringify(note)).items.length, 3);   // all three read back
  // Alerts for a date: the spot, then the finish, then the backup, each once.
  assert.deepEqual(O.outingPairs({day, spot: 'a', finish: 'f', backup: 'b'}).map(p => p.spot), ['a', 'f', 'b']);
  assert.deepEqual(O.outingPairs({day, spot: 'a', finish: 'a'}).map(p => p.spot), ['a']);
  // The offline copy: the finish's page, its file and its list of overflows; a pack without the finish is another outing's.
  const fl = K.files({shell: [], spots: [{id: 'a', page: true, file: 'spot/a.json'}, {id: 'f', page: true, file: 'spot/f.json', upstream: true}]});
  assert.ok(fl.need.includes('spot/f/') && fl.need.includes('data/spot/f.json') && fl.may.includes('data/upstream/f.json'));
  assert.equal(fl.may.includes('data/upstream/a.json'), false);
  assert.equal(K.same({day, spot: 'a', backup: null}, {day, spot: 'a', backup: null, finish: 'f'}), false);
  assert.equal(K.same({day, spot: 'a', backup: null, finish: 'f'}, {day, spot: 'a', backup: null, finish: 'f'}), true);
  assert.equal(K.covers({day, spot: 'a', finish: 'f'}, 'spot/f'), true);
});
