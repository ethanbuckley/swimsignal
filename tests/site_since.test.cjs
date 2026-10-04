// Since you last looked (src/dipcast/site/since.js): what a saved spot showed, compared with what it
// shows now, as one line on its card; and the note kept on the device, read back whatever is in it.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const L = require('../src/dipcast/site/levels.js');
const S = require('../src/dipcast/site/since.js');
L.setToday('2026-10-04');   // a Sunday: the forecast's own day, as the page sets it from spots.json
const DATES = ['2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07', '2026-10-08'];
const OLD = '2026-10-02T17:31:00+01:00', NEW = '2026-10-04T15:29:52.301035+01:00';
// Times on the device's own clock, so the words do not depend on the time zone the tests run in.
const at = (m, d, h, min) => new Date(2026, m - 1, d, h, min).getTime();
const FRIDAY = at(10, 2, 18, 20);
const RISK = {low: 0.05, moderate: 0.2, high: 0.5, 'very high': 0.8};
// A river spot with three overflows upstream, at level l today, every feed current.
const spot = (l, now = {}, extra = {}) => ({id: 'wharfe', name: 'Wharfe', kind: 'river', source: 'curated', upstream_summary: {overflows: 3},
  location: {mode: 'river'}, now: {label: 'low', risk: 0, discharging_upstream: 0, feed_down_upstream: 0, stale_upstream: 0, ...now},
  days: DATES.map((date, i) => ({date, label: i ? 'low' : l, risk: RISK[i ? 'low' : l]})), ...extra});
const seen = (s, forecast = OLD, t = FRIDAY) => S.seenRecord(s, forecast, t);
const line = (was, now) => S.sinceLine(seen(was), seen(now, NEW, Date.now()));

test('a level that moved says what it was, when, and what it is now, with "risk" on both', () => {
  assert.equal(line(spot('low'), spot('moderate')), 'Was low risk when you looked on Friday at 18:20; now moderate risk.');
  assert.equal(line(spot('very high'), spot('low')), 'Was very high risk when you looked on Friday at 18:20; now low risk.');
  // The plain level in its own words; an algae check or a rating is what can raise it.
  const clear = {...spot('low'), upstream_summary: {overflows: 0}, source: 'designated', location: {mode: 'lake'}};
  assert.equal(L.level(clear), L.NO_OVERFLOWS);
  const algae = {...clear, algae: {date: '2026-10-01', level: 2, phrase: 'some at intervals'}};
  assert.equal(line(clear, algae), 'Was no sewage risk from monitored overflows when you looked on Friday at 18:20; now moderate risk.');
});

test('the day is the forecast\'s own word within the week before it, else the date', () => {
  const r = S.seenRecord(spot('low'), OLD, 0), now = seen(spot('high'), NEW);
  const said = t => S.sinceLine({...r, at: t}, now).replace(/^Was low risk when you looked (.*); now high risk\.$/, '$1');
  assert.equal(said(at(10, 4, 9, 5)), 'today at 09:05');
  assert.equal(said(at(10, 3, 23, 59)), 'on Saturday at 23:59');
  assert.equal(said(at(9, 28, 7, 0)), 'on Monday at 07:00');   // six days back
  assert.equal(said(at(9, 27, 7, 0)), 'on 27 September at 07:00');   // a week back: "on Sunday" would be today
  assert.equal(said(new Date(2025, 8, 24, 18, 20).getTime()), 'on 24 September 2025 at 18:20');
  assert.equal(said(at(10, 5, 8, 0)), 'on 5 October at 08:00');   // the phone's clock ahead of the forecast's day: never "tomorrow"
});

test('nothing is said on a first look, when nothing changed, or for the same forecast', () => {
  assert.equal(S.sinceLine(undefined, seen(spot('high'), NEW)), '');
  assert.equal(line(spot('moderate'), spot('moderate')), '');
  // The same forecast seen again cannot have changed; an older one (a copy opened offline) is not news.
  assert.equal(S.sinceLine(seen(spot('low'), NEW), seen(spot('high'), NEW)), '');
  assert.equal(S.sinceLine(seen(spot('low'), NEW), seen(spot('high'), OLD)), '');
  // A spot whose forecast failed in this update has nothing to compare, and no note is made of it.
  const failed = {...spot('low'), error: 'forecast failed: no rain'};
  assert.equal(S.seenRecord(failed, NEW, Date.now()), null);
  assert.equal(S.sinceLine(seen(spot('low')), S.seenRecord(failed, NEW, Date.now())), '');
  // An isolated lake's level does not change from day to day, and its words do not fit the line.
  const isolated = {id: 'lake', days: [], error: 'An isolated lake with no river connection in the network'};
  assert.equal(S.seenRecord(isolated, NEW, 0).level, null);
});

test('an overflow upstream starting or stopping is said when the level stays', () => {
  assert.equal(line(spot('low'), spot('low', {discharging_upstream: 2})), 'No overflow upstream was discharging when you looked on Friday at 18:20; now 2 are.');
  assert.equal(line(spot('low'), spot('low', {discharging_upstream: 1})), 'No overflow upstream was discharging when you looked on Friday at 18:20; now 1 is.');
  assert.equal(line(spot('high', {discharging_upstream: 3}), spot('high')), '3 overflows upstream were discharging when you looked on Friday at 18:20; all have stopped.');
  assert.equal(line(spot('high', {discharging_upstream: 1}), spot('high')), '1 overflow upstream was discharging when you looked on Friday at 18:20; it has stopped.');
  assert.equal(line(spot('low', {discharging_upstream: 2}), spot('low', {discharging_upstream: 5})), '');   // still spilling: no news
  // A feed down or behind drops its overflows from the count: that is not a spill stopping, either way.
  assert.equal(line(spot('high', {discharging_upstream: 3}), spot('high', {feed_down_upstream: 4})), '');
  assert.equal(line(spot('high', {discharging_upstream: 3}), spot('high', {stale_upstream: 2})), '');
  assert.equal(line(spot('low', {feed_down_upstream: 4}), spot('low', {discharging_upstream: 1})), '');
  // A discharge is a discharge whatever the feed's state, so the line can say one started.
  assert.equal(line(spot('low'), spot('low', {discharging_upstream: 1, stale_upstream: 2})), 'No overflow upstream was discharging when you looked on Friday at 18:20; now 1 is.');
  // No overflow upstream at all: nothing to say about spills.
  assert.equal(S.seenRecord({...spot('low'), upstream_summary: {overflows: 0}}, NEW, 0).discharging, null);
});

test('one line a spot: the level first, then the rating, then a spill', () => {
  assert.equal(line(spot('low'), spot('high', {discharging_upstream: 4})), 'Was low risk when you looked on Friday at 18:20; now high risk.');
  const rated = (c, y) => ({classification: {class: c, year: y}});
  assert.equal(line(spot('low', {}, rated('good', 2025)), spot('low', {discharging_upstream: 1}, rated('excellent', 2026))),
    'Was rated good for 2025 when you looked on Friday at 18:20; now rated excellent for 2026.');
  assert.equal(line(spot('low', {}, rated('good', 2025)), spot('low', {}, rated('good', 2026))),
    'Was rated good for 2025 when you looked on Friday at 18:20; now rated good for 2026.');   // a new year's rating is news
  assert.equal(line(spot('low', {}, {classification: {}}), spot('low', {}, rated('excellent', 2026))),
    'Was not yet rated when you looked on Friday at 18:20; now rated excellent for 2026.');
  // A rating of poor raises the level, so the level says it; the card's own line gives the reason.
  assert.equal(line(spot('low', {}, rated('good', 2025)), spot('low', {}, rated('poor', 2026))), 'Was low risk when you looked on Friday at 18:20; now high risk.');
});

test('a note is kept for the newest forecast seen, and a failed one leaves the last', () => {
  const m = new Map();
  S.noteSeen(m, [spot('low')], OLD, FRIDAY);
  assert.deepEqual(m.get('wharfe'), {id: 'wharfe', level: 'low', discharging: 0, rating: null, forecast: OLD, at: FRIDAY});
  S.noteSeen(m, [{...spot('high'), error: 'forecast failed: timeout'}], NEW, FRIDAY + 1);
  assert.equal(m.get('wharfe').level, 'low');
  S.noteSeen(m, [spot('high')], NEW, FRIDAY + 2);
  assert.equal(m.get('wharfe').level, 'high');
  S.noteSeen(m, [spot('moderate')], OLD, FRIDAY + 3);   // an older copy, opened offline: the newer note stays
  assert.deepEqual([m.get('wharfe').level, m.get('wharfe').at], ['high', FRIDAY + 2]);
  S.noteSeen(m, [spot('high')], NEW, FRIDAY + 4);   // the same forecast again: the later look
  assert.equal(m.get('wharfe').at, FRIDAY + 4);
});

test('stored values that are not what the page writes read as not seen, and never stop the page', () => {
  for (const text of [null, '', 'garbage', '{"wharfe":{}}', '42', 'null', '"text"', '[1, "x", null, true, []]']) assert.equal(S.readSeen(text).size, 0, String(text));
  const good = {id: 'wharfe', level: 'low', discharging: 0, rating: 'good 2025', forecast: OLD, at: FRIDAY};
  const odd = [{...good, id: 7}, {...good, level: 'purple'}, {...good, level: 'Low'}, {...good, level: undefined}, {...good, discharging: -1},
    {...good, discharging: 1.5}, {...good, discharging: '2'}, {...good, rating: 'great 2025'}, {...good, rating: 'good'}, {...good, at: '1759425600000'},
    {...good, at: null}, {...good, forecast: 'yesterday'}, {...good, forecast: 12}, {id: 'wharfe'}];
  for (const x of odd) assert.equal(S.readSeen(JSON.stringify([x])).size, 0, JSON.stringify(x));
  const read = S.readSeen(JSON.stringify([...odd, good, {...good, id: 'lake', level: L.NO_OVERFLOWS, discharging: null, rating: 'unrated'}]));
  assert.deepEqual([...read.keys()], ['wharfe', 'lake']);   // the odd ones dropped, the good ones kept
  assert.deepEqual(read.get('wharfe'), good);
  // Two notes for one spot: the later in the list wins.
  assert.equal(S.readSeen(JSON.stringify([good, {...good, level: 'high'}])).get('wharfe').level, 'high');
});

// ------------------------------------------------------------------------------ in the page
// since.js with its globals, as the page loads it: levels.js and experience.js first, a stand-in storage.
function page(stored, {blocked = false} = {}) {
  const dir = path.join(__dirname, '../src/dipcast/site/'), items = new Map(stored === undefined ? [] : [[S.SEEN_KEY, stored]]);
  const localStorage = {
    getItem: k => { if (blocked) throw new Error('SecurityError'); return items.has(k) ? items.get(k) : null; },
    setItem: (k, v) => { if (blocked) throw new Error('SecurityError'); items.set(k, String(v)); },
    removeItem: k => { if (blocked) throw new Error('SecurityError'); items.delete(k); },
  };
  const ctx = vm.createContext({localStorage});
  for (const f of ['experience.js', 'levels.js', 'since.js']) vm.runInContext(fs.readFileSync(dir + f, 'utf8'), ctx);
  vm.runInContext('setToday("2026-10-04")', ctx);
  const run = (f, ...a) => vm.runInContext(f, ctx)(...a);
  return {run, items, stored: () => JSON.parse(items.get(S.SEEN_KEY) || 'null')};
}
const eden = (l, now = {}) => ({...spot(l, now), id: 'eden', name: 'Eden'});

test('the page keeps a note for each saved spot shown, and the line stays for the visit', () => {
  const p = page(JSON.stringify([seen(spot('low')), seen(eden('high'))]));
  const saved = new Set(['wharfe', 'eden']);
  assert.equal(p.run('sinceSaid', spot('moderate'), NEW), '<p class="place-since">Was low risk when you looked on Friday at 18:20; now moderate risk.</p>');
  assert.equal(p.run('sinceSaid', eden('high'), NEW), '');   // no change: no line
  p.run('lookedAt', [spot('moderate'), eden('high'), {...spot('low'), id: 'unsaved'}], NEW, saved);
  assert.deepEqual(p.stored().map(x => [x.id, x.level, x.forecast]), [['wharfe', 'moderate', NEW], ['eden', 'high', NEW]]);
  // Drawn again in the same visit (a removal undone, another tab's change): the same line.
  assert.match(p.run('sinceSaid', spot('moderate'), NEW), /Was low risk when you looked on Friday at 18:20/);
  // The next visit compares with this one: the same forecast, so nothing.
  const next = page(p.items.get(S.SEEN_KEY));
  assert.equal(next.run('sinceSaid', spot('moderate'), NEW), '');
});

test('a spot unsaved loses its note, and the last one removes the key', () => {
  const p = page(JSON.stringify([seen(spot('low')), seen(eden('high'))]));
  p.run('writeSeen', new Set(['eden']));
  assert.deepEqual(p.stored().map(x => x.id), ['eden']);
  p.run('writeSeen', new Set());
  assert.equal(p.items.has(S.SEEN_KEY), false);
});

test('odd or blocked storage gives no line and never stops the page', () => {
  for (const stored of ['not json', '{"a":1}', JSON.stringify([{id: 'wharfe', level: 'low'}])]) {
    const p = page(stored);
    assert.equal(p.run('sinceSaid', spot('high'), NEW), '', stored);
    p.run('lookedAt', [spot('high')], NEW, new Set(['wharfe']));   // the odd value is replaced by a good note
    assert.deepEqual(p.stored().map(x => [x.id, x.level]), [['wharfe', 'high']]);
  }
  const blocked = page(undefined, {blocked: true});
  assert.equal(blocked.run('sinceSaid', spot('high'), NEW), '');
  assert.doesNotThrow(() => blocked.run('lookedAt', [spot('high')], NEW, new Set(['wharfe'])));
  assert.doesNotThrow(() => blocked.run('writeSeen', new Set()));
});
