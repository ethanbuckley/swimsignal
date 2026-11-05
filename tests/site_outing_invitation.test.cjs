// A shared outing opened as an invitation (Swim Together stage 1, S3: docs/SWIM-TOGETHER-2026-10.md): the link's
// stamp (S2: sent=, lv=, blv=) stands in for this browser's note, so the one who opens it is told what has changed
// since it was shared. node --test tests/site_outing_invitation.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const L = require('../src/dipcast/site/levels.js');
const W = require('../src/dipcast/site/outingwatch.js');
const O = require('../src/dipcast/site/outing.js');
L.setToday('2026-10-31');   // a Saturday
const SITE = path.join(__dirname, '../src/dipcast/site');
const PLAN = {day: '2026-11-01', spot: 'a', backup: 'b', sent: '20261031T0700Z', lv: 'low', blv: 'moderate'};
const NOW = '2026-10-31T13:00:00Z';
const now = (id, level, official = null, forecast = NOW) => ({id, day: '2026-11-01', level, official, river: null, forecast, at: Date.parse(forecast)});
const ADVICE = {key: 'EA|x|', brief: 'Advice against swimming', publisher: 'Environment Agency', restricts: true};

// ------------------------------------------------------------------------------ the stamp as a note
test('the stamp reads as what each spot showed when the link was sent', () => {
  const s = W.outingWatchShared(PLAN);
  assert.equal(s.forecast, '2026-10-31T07:00:00Z');
  assert.deepEqual(s.items.map(r => [r.id, r.day, r.level, r.official, r.river, r.forecast]),
    [['a', '2026-11-01', 'low', undefined, null, '2026-10-31T07:00:00Z'], ['b', '2026-11-01', 'moderate', undefined, null, '2026-10-31T07:00:00Z']]);
  // No backup level: the spot alone. No stamp, a bad one, or no level for the spot: nothing.
  assert.deepEqual(W.outingWatchShared({...PLAN, blv: undefined}).items.map(r => r.id), ['a']);
  for (const bad of [{...PLAN, sent: undefined}, {...PLAN, sent: '2026-10-31'}, {...PLAN, lv: undefined}, {...PLAN, lv: 'fine'}, {...PLAN, day: 'soon'}])
    assert.equal(W.outingWatchShared(bad), null, JSON.stringify(bad));
});

// ------------------------------------------------------------------------------ the words
const section = (spots, extra = {}) => W.outingWatchSection({day: '2026-11-01', today: '2026-10-31', kept: true, forecast: NOW, shared: true, spots, ...extra});
const shared = W.outingWatchShared(PLAN);

test('what has changed since it was shared, against a newer forecast', () => {
  const h = section([{name: 'Port Meadow', role: 'your spot', was: shared.items[0], now: now('a', 'high')},
    {name: 'Wolvercote', role: 'your backup', was: shared.items[1], now: now('b', 'moderate', ADVICE)}]);
  assert.match(h, /<p>1 thing has changed since this outing was shared with you\.<\/p>/);
  assert.match(h, /<li>Level for tomorrow: high risk\. Changed: was low risk\.<\/li>/);
  assert.match(h, /<li>Level for tomorrow: moderate risk\. No change since then\.<\/li>/);
  // The link carries no notice: one now is said as it is, never as changed, and none is never an all-clear.
  assert.match(h, /<li>Official advice: Advice against swimming\. Follow it first\.<\/li>/);
  assert.doesNotMatch(h, /Follow it first\. (Changed|No change)/);
  assert.match(h, /<li>Official notice: none shown\.<\/li>/);
  assert.match(h, /Checked against the forecast issued Sat 13:00; it was shared from the one issued Sat 07:00\./);
  assert.doesNotMatch(h, /planned/);   // these words are about sharing
  const same = section([{name: 'Port Meadow', role: 'your spot', was: shared.items[0], now: now('a', 'low')}]);
  assert.match(same, /<p>Nothing has changed since this outing was shared with you\.<\/p>/);
});

test('opened on the forecast it was shared from, or an older copy: nothing compared, and said so', () => {
  const h = section([{name: 'Port Meadow', role: 'your spot', was: shared.items[0], now: now('a', 'low', null, '2026-10-31T07:00:00Z')}], {forecast: '2026-10-31T07:00:00Z'});
  assert.match(h, /<p>This is the forecast it was shared from\. When a newer forecast is issued, this says what has changed since\.<\/p>/);
  assert.doesNotMatch(h, /Changed:|No change/);
  const older = section([{name: 'Port Meadow', role: 'your spot', was: shared.items[0], now: now('a', 'high', null, '2026-10-30T20:00:00Z')}], {forecast: '2026-10-30T20:00:00Z'});
  assert.match(older, /older than the one it was shared from \(Sat 07:00\), so nothing is compared/);
  assert.doesNotMatch(older, /Changed:/);
});

test('a plan of one\'s own keeps its words', () => {
  const h = section([{name: 'Port Meadow', role: 'your spot', was: {...shared.items[0], at: Date.parse('2026-10-31T07:30:00Z')}, now: now('a', 'high')}], {shared: false});
  assert.match(h, /1 thing has changed since you planned this outing\./);
  assert.match(h, /, planned Sat 0\d:30/);
  assert.match(h, /you planned against the one issued Sat 07:00/);
});

// ------------------------------------------------------------------------------ the tile
const BY = new Map(['a', 'b'].map(id => [id, {id, name: id.toUpperCase()}]));
const col = (id, name) => ({id, name, href: `spot/${id}/`, tone: 'low', headline: 'Low risk tomorrow', why: '', ev: '', meta: ''});
const tile = (o = {}) => O.outingSection({day: '2026-11-01', when: 'morning', spot: 'a', backup: 'b',
  groups: [['In this plan', [BY.get('a'), BY.get('b')]]], backupGroups: [['In this plan', [BY.get('b')]]],
  main: col('a', 'Port Meadow'), alt: col('b', 'Wolvercote'), missing: [], issued: '15:29, 2 h ago', open: true,
  nowMs: new Date(2026, 9, 31, 9).getTime(), ...o});

test('the tile opens as an invitation while the link\'s stamp stands', () => {
  const h = tile({shared: 'Sat 07:00'});
  assert.match(h, /<summary><span>Outing shared with you<span class="k">Port Meadow, backup Wolvercote<\/span><\/span><\/summary>/);
  assert.match(h, /<p class="sub">Shared with you, from the forecast issued Sat 07:00\. Under the two spots: what has changed since\. At the end: alerts and a calendar file for it\. Kept in this browser and in this page's link; sent nowhere\. Change anything here and it becomes your own plan\.<\/p>/);
  assert.match(h, /id="outing-ics"/);   // the calendar file, and the alerts' place, as for one's own outing
  assert.match(h, /id="outing-alert"/);
  const own = tile({shared: ''});
  assert.match(own, /<summary><span>Your outing/);
  assert.match(own, /When you mean to go, where, and somewhere else to go instead\./);
  assert.doesNotMatch(tile({shared: 'Sat 07:00', main: null, alt: null}), /Shared with you/);   // no spot listed: nothing to invite to
});

test('the page compares a shared link with its stamp, and says when it was sent', () => {
  const ow = fs.readFileSync(path.join(SITE, 'outingwatch.js'), 'utf8'), out = fs.readFileSync(path.join(SITE, 'outing.js'), 'utf8');
  assert.match(ow, /const shared = outingWatchShared\(plan\);\n  const was = shared \? shared\.items : !preview && old && old\.day === plan\.day \? old\.items : \[\]/);
  assert.match(ow, /outingWatchSection\(\{ day: plan\.day, today: t, spots, kept, forecast, shared: !!shared, preview,/);
  assert.match(out, /const sent = PLAN\.sent && typeof outingWatchShared === 'function' && outingWatchShared\(PLAN\);/);
  assert.match(out, /shared: sent \? issuedWords\(sent\.forecast\) : '',/);
  // The stamp goes with any change (S2, outingChanged), so the invitation's words go with it.
  assert.equal('sent' in O.outingChanged(PLAN, 'when'), false);
});
