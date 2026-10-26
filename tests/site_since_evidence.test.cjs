// What changed since you last looked, with its evidence (src/dipcast/site/since.js, sinceEvidence): which
// forecasts were compared, by issue time; what the overflow feeds report now; what is not known, and why;
// and a forecast too old to trust. The line itself is tested in site_since.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const L = require('../src/dipcast/site/levels.js');
const S = require('../src/dipcast/site/since.js');
L.setToday('2026-10-26');   // a Monday
const DATES = ['2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30'];
// Forecast times on the device's own clock, so the words do not depend on the time zone the tests run in.
const OLD = '2026-10-26T07:00:00', NEW = '2026-10-26T15:30:00';
const LOOKED = new Date(2026, 9, 26, 7, 5).getTime(), NOW = new Date(2026, 9, 26, 16, 0).getTime();
const RISK = {low: 0.05, moderate: 0.2, high: 0.5};
const spot = (l, now = {}, extra = {}) => ({id: 'wharfe', name: 'Wharfe', kind: 'river', source: 'curated', upstream_summary: {overflows: 3},
  location: {mode: 'river'}, now: {label: 'low', risk: 0, discharging_upstream: 0, feed_down_upstream: 0, stale_upstream: 0, ...now},
  days: DATES.map((date, i) => ({date, label: i ? 'low' : l, risk: RISK[i ? 'low' : l]})), ...extra});
const pair = (was, now) => [S.seenRecord(was, OLD, LOOKED), S.seenRecord(now, NEW, NOW)];

test('a level that rose: the line, then both issue times and the overflows reported now against then', () => {
  const [a, b] = pair(spot('low'), spot('moderate', {discharging_upstream: 2}));
  assert.equal(S.sinceLine(a, b), 'Was low risk when you looked today at 07:05; now moderate risk.');
  assert.equal(S.sinceEvidence(a, b, NOW), 'Forecasts compared: issued Mon 07:00 and Mon 15:30. 2 overflows upstream reported discharging now, against 0 then.');
  const [c, d] = pair(spot('moderate', {discharging_upstream: 1}), spot('low'));
  assert.equal(S.sinceEvidence(c, d, NOW), 'Forecasts compared: issued Mon 07:00 and Mon 15:30. No overflow upstream reported discharging now, against 1 then.');
  // A level that fell is a lower forecast risk, never "safe".
  assert.doesNotMatch(S.sinceLine(c, d) + S.sinceEvidence(c, d, NOW), /\bsafe/i);
});

test('a count that is not known says so and why, rather than say nothing', () => {
  const [a, b] = pair(spot('low'), spot('moderate', {feed_down_upstream: 2}));
  assert.equal(b.gap, true);
  assert.match(S.sinceEvidence(a, b, NOW), /How many overflows upstream are discharging now is not known: a feed upstream is down or has not updated within six hours\.$/);
  // Not known then, known now: no "against" a number nobody had.
  const [c, d] = pair(spot('low', {stale_upstream: 1}), spot('moderate', {discharging_upstream: 1}));
  assert.match(S.sinceEvidence(c, d, NOW), /1 overflow upstream reported discharging now\.$/);
  // No overflow upstream at all: there is no live count to give, and the evidence says that.
  const none = {upstream_summary: {overflows: 0}};
  const [e, f] = pair(spot('low', {}, none), spot('low', {}, {...none, classification: {class: 'Poor', year: 2026}}));
  assert.match(S.sinceEvidence(e, f, NOW), /No live overflow count for this spot\./);
});

test('a rating that changed names whose rating it is', () => {
  const rated = (c, y) => ({classification: {class: c, year: y}});
  const [a, b] = pair(spot('low', {}, rated('good', 2025)), spot('low', {}, rated('excellent', 2026)));
  assert.match(S.sinceLine(a, b), /^Was rated good for 2025/);
  assert.match(S.sinceEvidence(a, b, NOW), /The rating is the Environment Agency's, from its yearly bathing water classification\./);
});

test('a forecast older than eight hours is said to be out of date', () => {
  const [a, b] = pair(spot('low'), spot('high', {discharging_upstream: 3}));
  assert.doesNotMatch(S.sinceEvidence(a, b, NOW), /out of date/);
  const late = new Date(2026, 9, 27, 2, 0).getTime();   // 10.5 h after the 15:30 forecast
  assert.match(S.sinceEvidence(a, b, late), / This forecast is 11 hours old, so the change may be out of date\.$/);
  assert.equal(S.SINCE_STALE_MIN, 8 * 60);
});

test('nothing to compare: no evidence either', () => {
  assert.equal(S.sinceEvidence(undefined, S.seenRecord(spot('low'), NEW, NOW), NOW), '');
  assert.equal(S.sinceEvidence(S.seenRecord(spot('low'), OLD, LOOKED), null, NOW), '');
});

test('a note kept before the evidence was added (no gap field) still reads, and compares', () => {
  const before = {id: 'wharfe', level: 'low', discharging: 0, rating: null, forecast: OLD, at: LOOKED};   // as written until 26 Oct 2026
  const read = S.readSeen(JSON.stringify([before]));
  assert.deepEqual(read.get('wharfe'), before);
  const now = S.seenRecord(spot('moderate', {discharging_upstream: 2}), NEW, NOW);
  assert.match(S.sinceLine(read.get('wharfe'), now), /^Was low risk/);
  assert.match(S.sinceEvidence(read.get('wharfe'), now, NOW), /2 overflows upstream reported discharging now, against 0 then\./);
  // A gap field that is not a boolean is not what the page writes: not seen.
  assert.equal(S.readSeen(JSON.stringify([{...before, gap: 'yes'}])).size, 0);
});

// ------------------------------------------------------------------------------ which overflows, and the outing
const contributor = (name, start, extra = {}) => ({site_id: name.toUpperCase(), site_name: name, status: 1, latest_event_start: start, weight: 0.5, ...extra});

test('which overflows are discharging, and since when, where the forecast names them', () => {
  const s = spot('moderate', {discharging_upstream: 3}, {contributors: [
    contributor('ILKLEY WWTW', new Date(2026, 9, 26, 9, 10).toISOString()),
    contributor('BEN RHYDDING CSO', new Date(2026, 9, 26, 8, 40).toISOString()),
    contributor('ADDINGHAM CSO', new Date(2026, 9, 25, 22, 0).toISOString(), {status: 0}),   // not discharging now
    contributor('BURLEY CSO', new Date(2026, 9, 26, 6, 0).toISOString(), {latest_event_end: new Date(2026, 9, 26, 7, 0).toISOString()})]});
  const spills = S.sinceSpills(s);
  assert.equal(spills.length, 2);   // stopped and ended ones are left out
  assert.ok(spills[0].since < spills[1].since);   // earliest first
  const [a, b] = pair(spot('low'), s);
  const ev = S.sinceEvidence(a, b, NOW, {spills});
  assert.match(ev, new RegExp(`3 overflows upstream reported discharging now, against 0 then: ${spills[0].name} since Mon 08:40, ${spills[1].name} since Mon 09:10, and 1 more\\.`));
  // None discharging now: no names, whatever was passed.
  const [c, d] = pair(spot('moderate', {discharging_upstream: 1}), spot('low'));
  assert.doesNotMatch(S.sinceEvidence(c, d, NOW, {spills}), /since Mon/);
});

test('the outing planned at this spot is said beside the change; another spot\'s, or a past day\'s, is not', () => {
  const plan = '#day=2026-10-27&from=Ilkley&at=53.92%2C-1.82&within=20&when=morning&spot=wharfe&backup=eden';
  assert.equal(S.sinceOuting('wharfe', plan), 'This is the spot of your outing tomorrow morning.');
  assert.equal(S.sinceOuting('eden', plan), 'This is the backup for your outing tomorrow morning.');
  assert.equal(S.sinceOuting('wharfe', plan.replace('when=morning', 'when=07')), 'This is the spot of your outing tomorrow at 07:00.');
  assert.equal(S.sinceOuting('wharfe', plan.replace('2026-10-27', '2026-10-26')), 'This is the spot of your outing this morning.');
  assert.equal(S.sinceOuting('wharfe', plan.replace('&when=morning', '')), 'This is the spot of your outing tomorrow.');
  assert.equal(S.sinceOuting('other', plan), '');
  assert.equal(S.sinceOuting('wharfe', plan.replace('2026-10-27', '2026-10-25')), '');   // a day gone by
  for (const odd of [null, '', 'garbage', '#spot=wharfe']) assert.equal(S.sinceOuting('wharfe', odd), '', String(odd));
  const [a, b] = pair(spot('low'), spot('moderate', {discharging_upstream: 1}));
  assert.match(S.sinceEvidence(a, b, NOW, {outing: S.sinceOuting('wharfe', plan)}), /now, against 0 then\. This is the spot of your outing tomorrow morning\.$/);
});

test('on the card: the evidence escaped, with the outing read from the plan kept in this browser', () => {
  const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
  const items = new Map([[S.SEEN_KEY, JSON.stringify([S.seenRecord(spot('low'), OLD, LOOKED)])],
    ['dipcast.plan', '#day=2026-10-27&within=20&when=evening&spot=wharfe']]);
  const ctx = vm.createContext({URLSearchParams, localStorage: {getItem: k => items.has(k) ? items.get(k) : null, setItem: (k, v) => items.set(k, v), removeItem: k => items.delete(k)}});
  for (const f of ['experience.js', 'levels.js', 'since.js']) vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site/', f), 'utf8'), ctx);
  vm.runInContext('setToday("2026-10-26")', ctx);
  const s = spot('moderate', {discharging_upstream: 1}, {contributors: [contributor('<b>ODD</b> CSO', new Date(2026, 9, 26, 9, 10).toISOString())]});
  const h = vm.runInContext('sinceSaid', ctx)(s, NEW);
  assert.match(h, /This is the spot of your outing tomorrow evening\./);
  assert.doesNotMatch(h, /<b>/);
  assert.match(h, /&lt;b&gt;/i);
});
