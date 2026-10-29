// The outing link (Swim Together stage 1, S2: docs/SWIM-TOGETHER-2026-10.md): what for and where to meet as fixed
// choices, and a shared link stamped with the forecast it was sent from and each spot's level then.
// node --test tests/site_outing_link.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const L = require('../src/dipcast/site/levels.js');
const P = require('../src/dipcast/site/plan.js');
const O = require('../src/dipcast/site/outing.js');
L.setToday('2026-10-31');   // a Saturday
const DATES = ['2026-10-31', '2026-11-01', '2026-11-02', '2026-11-03', '2026-11-04'];
const FROM = {name: 'Oxford', lat: 51.752, lon: -1.2577};
const PLAN = {day: '2026-11-01', from: FROM, within: 20, kind: 'all', when: 'morning', spot: 'a', backup: 'b'};

// ------------------------------------------------------------------------------ the address
test('what for, where to meet and a send stamp survive the address', () => {
  const plan = {...PLAN, act: 'paddle', meet: 'parking', sent: '20261031T1216Z', lv: 'very high', blv: 'low'};
  const hash = P.planHash(plan);
  assert.match(hash, /&act=paddle&meet=parking&sent=20261031T1216Z&lv=very\+high&blv=low$/);
  assert.deepEqual(P.readPlan(hash, DATES), plan);
  // An outing without them writes no new keys: links from before read and write back the same.
  assert.doesNotMatch(P.planHash(PLAN), /act=|meet=|sent=|lv=/);
});

test('only the fixed choices are read: anything else, words above all, is dropped', () => {
  const r = h => P.readPlan('#from=Oxford&at=51.752,-1.2577&spot=a&backup=b&' + h, DATES);
  assert.equal(r('act=kayak').act, undefined);
  assert.equal(r('act=Swim').act, undefined);
  assert.equal(r('act=sup').act, 'sup');
  assert.equal(r('meet=the+cafe+at+10').meet, undefined);
  assert.equal(r('meet=entry').meet, 'entry');
  assert.equal(r('sent=yesterday&lv=low').sent, undefined);
  assert.equal(r('sent=20261031T1216Z&lv=fine').lv, undefined);
  assert.equal(r('sent=20261031T1216Z&lv=fine').sent, '20261031T1216Z');
  assert.deepEqual(P.PLAN_LEVELS, [...Object.keys(L.ORDER), L.NO_FORECAST, L.NO_OVERFLOWS, L.NOT_COVERED, L.NO_RIVER]);   // every level a spot can have
  for (const lv of P.PLAN_LEVELS)
    assert.equal(r(`sent=20261031T1216Z&lv=${encodeURIComponent(lv)}`).lv, lv);
  // A meeting place, a stamp and a level each need the spot they are of.
  const bare = h => P.readPlan('#from=Oxford&at=51.752,-1.2577&' + h, DATES);
  assert.equal(bare('meet=parking').meet, undefined);
  assert.equal(bare('sent=20261031T1216Z&lv=low').sent, undefined);
  assert.equal(r('sent=20261031T1216Z&lv=low&blv=high').blv, 'high');
  assert.equal(P.readPlan('#spot=a&sent=20261031T1216Z&lv=low&blv=high', DATES).blv, undefined);   // no backup
  // A level without a stamp says nothing of when it was: dropped.
  assert.equal(r('lv=low').lv, undefined);
});

test('a kept send stamp is for its own day, as the time is', () => {
  const kept = P.planHash({...PLAN, day: '2026-10-28', sent: '20261028T0700Z', lv: 'low', blv: 'moderate', act: 'sup'});
  const p = P.planKept(kept, DATES);
  assert.deepEqual([p.sent, p.lv, p.blv, p.act], [undefined, undefined, undefined, 'sup']);
  const today = P.planKept(kept.replace('2026-10-28', '2026-11-01'), DATES);
  assert.deepEqual([today.sent, today.lv, today.blv], ['20261028T0700Z', 'low', 'moderate']);
});

// ------------------------------------------------------------------------------ changing the outing
test('a day changed in the page drops the stamp with the time', () => {
  const plan = {...PLAN, act: 'paddle', meet: 'entry', sent: '20261031T1216Z', lv: 'low', blv: 'low'};
  assert.equal(O.outingForDay(plan, '2026-11-01'), plan);
  const moved = O.outingForDay(plan, '2026-10-31');
  assert.deepEqual([moved.when, moved.sent, moved.lv, moved.blv, moved.act, moved.meet], [undefined, undefined, undefined, undefined, 'paddle', 'entry']);
  const {when, ...noTime} = plan;
  assert.equal(O.outingForDay(noTime, '2026-10-31').sent, undefined);   // a stamp alone is dropped too
});

test('changing the outing drops the stamp, and a new spot drops the meeting place', () => {
  const plan = {...PLAN, act: 'paddle', meet: 'entry', sent: '20261031T1216Z', lv: 'low', blv: 'low'};
  for (const k of ['when', 'backup', 'act', 'meet']) {
    const n = O.outingChanged(plan, k);
    assert.deepEqual([n.sent, n.lv, n.blv, n.meet], [undefined, undefined, undefined, 'entry'], k);
  }
  assert.equal(O.outingChanged(plan, 'spot').meet, undefined);
  assert.equal(O.outingChanged(plan, 'spot').act, 'paddle');
});

// ------------------------------------------------------------------------------ the shared link
test('the shared link is stamped with the issue time and each spot\'s level, whole or not at all', () => {
  const main = {name: 'Port Meadow', lat: 51.77, lon: -1.28};
  const sent = O.outingSent('2026-10-31T12:16:42.123Z');
  assert.equal(sent, '20261031T1216Z');
  assert.equal(O.outingSent('not a time'), null);
  const s = O.outingShared({...PLAN, act: 'sup', meet: 'parking', compare: ['x']}, main, {sent, lv: 'moderate', blv: 'low'});
  assert.deepEqual(s, {...PLAN, act: 'sup', meet: 'parking', from: {name: 'Port Meadow', lat: 51.77, lon: -1.28}, sent, lv: 'moderate', blv: 'low'});
  // What the one who opens it reads back is what was sent.
  assert.deepEqual(P.readPlan(P.planHash(s), DATES), s);
  // A stamp missing a level, or the time: none at all, rather than half of one.
  assert.equal('sent' in O.outingShared(PLAN, main, {sent, lv: 'low'}), false);
  assert.equal('sent' in O.outingShared(PLAN, main, {lv: 'low', blv: 'low'}), false);
  // No backup: no backup level; and a stamp the plan already carried is replaced, never kept.
  const {backup, ...one} = PLAN;
  assert.deepEqual(O.outingShared({...one, sent: '20261030T0000Z', lv: 'high'}, main, {sent, lv: 'low', blv: 'high'}),
    {...one, from: {name: 'Port Meadow', lat: 51.77, lon: -1.28}, sent, lv: 'low'});
  // Never where you start from, and never anything typed.
  const hash = P.planHash(s);
  assert.doesNotMatch(hash, /Oxford|51\.752/);
  assert.deepEqual([...new URLSearchParams(hash.slice(1)).keys()].sort(),
    ['act', 'at', 'backup', 'blv', 'day', 'from', 'lv', 'meet', 'sent', 'spot', 'when', 'within'].sort());
});

// ------------------------------------------------------------------------------ the tile and the calendar
const BY = new Map(['a', 'b'].map(id => [id, {id, name: id.toUpperCase()}]));
const col = (id, name) => ({id, name, href: `spot/${id}/`, tone: 'low', headline: 'Low risk tomorrow', why: '', ev: '', meta: ''});
const tile = (o = {}) => O.outingSection({day: '2026-11-01', when: 'morning', spot: 'a', backup: 'b',
  groups: [['In this plan', [BY.get('a'), BY.get('b')]]], backupGroups: [['In this plan', [BY.get('b')]]],
  main: col('a', 'Port Meadow'), alt: col('b', 'Wolvercote'), missing: [], issued: '15:29, 2 h ago', open: true,
  nowMs: new Date(2026, 9, 31, 9).getTime(), ...o});

test('the tile offers what for and where to meet, and says them', () => {
  const h = tile({act: 'paddle', meet: 'parking'});
  assert.match(h, /<label>What for<select data-outing="act"><option value="">Swim<\/option><option value="paddle" selected>Paddle<\/option><option value="sup">Paddleboard<\/option><\/select><\/label>/);
  assert.match(h, /<label>Meet \(optional\)<select data-outing="meet"><option value="">Not set<\/option><option value="parking" selected>At the parking<\/option><option value="entry">Where you get in<\/option><\/select><\/label>/);
  assert.match(h, /<p class="outing-said">Tomorrow morning, paddling: your spot and a backup, side by side\.<\/p>/);
  assert.match(h, /Meet at the parking at Port Meadow: the Access part under it says what its guide knows\./);
  assert.match(h, /The level is for the water, the same whatever you do on it\./);
  // A swim, the default, says nothing new; and no spot yet, no meeting place to pick.
  const swim = tile();
  assert.match(swim, /<p class="outing-said">Tomorrow morning: your spot/);
  assert.doesNotMatch(swim, /whatever you do on it|Meet at/);
  assert.doesNotMatch(tile({main: null, alt: null, spot: undefined}), /data-outing="meet"/);
  // The words for the link: what it holds, and that none of them are yours.
  assert.match(swim, /what for and where to meet, as you picked them, with the forecast's issue time and each spot's level when you share it/);
  assert.match(swim, /no words of yours/);
});

test('the calendar file says what for and where to meet, never a level', () => {
  const ics = O.outingIcs({day: '2026-11-01', when: 'morning', act: 'sup', meet: 'entry', main: {id: 'a', name: 'Port Meadow', url: 'https://x/spot/a/'},
    backup: null, plan: 'https://x/plan/#day=2026-11-01', host: 'x'}, Date.UTC(2026, 9, 31, 9)).replace(/\r\n /g, '');
  assert.match(ics, /SUMMARY:Paddleboard: Port Meadow/);
  assert.match(ics, /Meet where you get in\./);
  assert.doesNotMatch(ics, /risk|moderate|low/i);
  assert.match(O.outingIcs({day: '2026-11-01', main: {id: 'a', name: 'P', url: 'u'}, backup: null, plan: 'p', host: 'x'}), /SUMMARY:Swim: P/);
});

test('the page keeps the outing\'s changes through outingChanged and stamps the shared link from the live data', () => {
  const js = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/outing.js'), 'utf8');
  assert.match(js, /const k = el\.dataset\.outing, next = outingChanged\(PLAN, k\);/);
  assert.match(js, /outingShared\(PLAN, pair\.main, \{ sent: outingSent\(DATA\.generated_at\),\s+lv: dayLevel\(pair\.main, PLAN\.day\), blv: pair\.backup && dayLevel\(pair\.backup, PLAN\.day\), flv: fin && dayLevel\(fin, PLAN\.day\) \}\)/);
  assert.match(js, /`\$\{outingVerb\(PLAN\.act\)\}: \$\{pair\.main\.name\} · \$\{BRAND\}`/);
});
