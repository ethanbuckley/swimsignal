// The Saved page as a starting page (2 Nov 2026): the places grouped (lists.js, savedGroups), the summary of what
// changed since this browser last showed them (since.js, sinceSummary), and each spot's alerts (lists.js,
// spotAlert, alertSpots). The summary says no more than the cards' own lines, and never why.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const L = require('../src/dipcast/site/levels.js');
const S = require('../src/dipcast/site/since.js');
const Li = require('../src/dipcast/site/lists.js');
L.setToday('2026-10-04');
const DATES = ['2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07', '2026-10-08'];
const OLD = '2026-10-02T17:31:00+01:00', NEW = '2026-10-04T15:29:52.301035+01:00';
const FRIDAY = new Date(2026, 9, 2, 18, 20).getTime(), SATURDAY = new Date(2026, 9, 3, 9, 5).getTime();
const RISK = {low: 0.05, moderate: 0.2, high: 0.5, 'very high': 0.8};
const spot = (id, l, now = {}) => ({id, name: id, kind: 'river', source: 'curated', upstream_summary: {overflows: 3},
  location: {mode: 'river'}, now: {label: 'low', risk: 0, discharging_upstream: 0, feed_down_upstream: 0, stale_upstream: 0, ...now},
  days: DATES.map((date, i) => ({date, label: i ? 'low' : l, risk: RISK[i ? 'low' : l]}))});
const row = (name, was, now, wasForecast = OLD, t = FRIDAY) => ({name,
  was: was ? S.seenRecord(spot(name, was), wasForecast, t) : undefined, now: S.seenRecord(spot(name, now), NEW, Date.now())});

test('groups: by area with one list, in the order saved; with several lists, the list shown under its name', () => {
  const xs = [{id: 'a', area: 'Yorkshire'}, {id: 'b', area: 'Cumbria'}, {id: 'c', area: 'Yorkshire'}, {id: 'd'}];
  assert.deepEqual(Li.savedGroups(xs).map(([h, g]) => [h, g.map(s => s.id)]), [['Yorkshire', ['a', 'c']], ['Cumbria', ['b']], ['Other', ['d']]]);
  assert.deepEqual(Li.savedGroups(xs, 'Weekend').map(([h, g]) => [h, g.length]), [['Weekend', 4]]);
  assert.deepEqual(Li.savedGroups([]), []);
  assert.deepEqual(Li.savedGroups([], 'Weekend'), []);
});

test('summary: nothing to compare on a first look', () => {
  const x = S.sinceSummary([row('Wharfe', null, 'low'), row('Eden', null, 'low')]);
  assert.equal(x.state, 'none');
  assert.match(x.text, /^This browser has not shown these spots before, so there is nothing to compare yet\./);
  assert.match(S.sinceSummary([row('Wharfe', null, 'low')]).text, /^This browser has not shown this spot before/);
});

test('summary: the same forecast as last time says so, and no change', () => {
  const x = S.sinceSummary([row('Wharfe', 'low', 'moderate', NEW)]);
  assert.equal(x.state, 'same');
  assert.equal(x.text, 'No new forecast since you looked on Friday at 18:20.');
});

test('summary: a newer forecast with nothing the cards would say lists what was checked, not "all clear"', () => {
  const x = S.sinceSummary([row('Wharfe', 'low', 'low'), row('Eden', 'moderate', 'moderate')]);
  assert.equal(x.state, 'quiet');
  assert.equal(x.text, 'Since you looked on Friday at 18:20, no level, rating or official notice changed at your 2 spots, and no overflow upstream was reported starting or stopping.');
  assert.doesNotMatch(x.text, /safe|clean|clear/i);
});

test('summary: the spots that changed, by name, exactly those whose card has a line, and no cause', () => {
  const rows = [row('Wharfe', 'moderate', 'low'), row('Eden', 'high', 'moderate'), row('Dart', 'low', 'low')];
  const x = S.sinceSummary(rows);
  assert.equal(x.state, 'changed');
  assert.deepEqual(x.changed, ['Wharfe', 'Eden']);
  assert.deepEqual(rows.filter(r => S.sinceLine(r.was, r.now)).map(r => r.name), x.changed);
  assert.equal(x.text, 'Since you looked on Friday at 18:20, 2 of your 3 spots changed: Wharfe and Eden. Each card says what changed and which forecasts it compares.');
  assert.doesNotMatch(x.text, /because|due to|rain|spill/i);
  const commas = S.sinceSummary([row('River Wharfe, Burnsall', 'moderate', 'low'), row('River Eden, Lazonby', 'high', 'moderate')]);
  assert.match(commas.text, /changed: River Wharfe, Burnsall; and River Eden, Lazonby\. /);
  const one = S.sinceSummary([row('Wharfe', 'moderate', 'low')]);
  assert.equal(one.text, 'Since you looked on Friday at 18:20, this spot changed. Its card says what changed and which forecasts it compares.');
});

test('summary: looks at different times give no single time; a spot newly saved is counted apart', () => {
  const x = S.sinceSummary([row('Wharfe', 'moderate', 'low'), row('Eden', 'low', 'low', OLD, SATURDAY), row('Dart', null, 'low')]);
  assert.equal(x.text, 'Since you last looked at each, 1 of your 3 spots changed: Wharfe. Its card says what changed and which forecasts it compares. One spot has nothing to compare with yet.');
  // A spot with no forecast this time is not compared, rather than read as a change.
  const gone = S.sinceSummary([{name: 'Wharfe', was: S.seenRecord(spot('Wharfe', 'low'), OLD, FRIDAY), now: null}]);
  assert.equal(gone.state, 'none');
});

test('alerts: which spots are sent; one turned off is left out, and the lists are untouched', () => {
  const saved = new Set(['a', 'b', 'gone']), known = new Set(['a', 'b']);
  assert.deepEqual(Li.alertSpots(saved, known), ['a', 'b']);
  assert.deepEqual(Li.alertSpots(saved, known, ['b']), ['a']);
  assert.deepEqual([...saved], ['a', 'b', 'gone']);
});

test('alerts: each state a card can be in says what it is, plainly', () => {
  const st = x => Li.spotAlert({push: true, email: false, can: 'yes', ...x});
  assert.equal(Li.spotAlert({push: false, email: false}).kind, 'none');
  assert.deepEqual(Li.spotAlert({push: false, email: false}).text, '');
  assert.deepEqual(st({on: null}), {kind: 'checking', text: '', toggle: false, checked: false, link: false});
  assert.deepEqual(st({on: true}), {kind: 'on', text: 'A notification if it reaches high or very high risk.', toggle: true, checked: true, link: false});
  assert.deepEqual(st({on: true, off: true}), {kind: 'muted', text: 'No alerts for this spot. Your other saved spots still have them.', toggle: true, checked: false, link: false});
  assert.deepEqual(st({on: false}), {kind: 'off', text: 'Alerts are off.', toggle: false, checked: false, link: true});
  // The alert service not answering is said, with the tick kept where alerts are on.
  const down = st({on: true, down: true});
  assert.equal(down.kind, 'down'); assert.equal(down.toggle, true);
  assert.match(down.text, /^The alert service did not answer/);
  assert.match(st({on: false, down: true}).text, /^The alert service did not answer, so alerts could not be checked/);
  assert.equal(st({can: 'blocked'}).text, 'Notifications are blocked for this site in your browser settings.');
  assert.equal(st({can: 'blocked'}).link, false);
  for (const can of ['ios', 'inapp', 'offline', 'none']) assert.equal(st({can}).text, 'Notifications cannot be had in this browser.', can);
  // Where email alerts exist, a browser without notifications is pointed to them, and what they cover is said.
  const mail = Li.spotAlert({push: true, email: true, can: 'ios'});
  assert.equal(mail.kind, 'email'); assert.match(mail.text, /cover the spots saved when you sign up/);
  assert.equal(Li.spotAlert({push: false, email: true}).kind, 'email');
  // No state turns alerts on from a card: the consent wording is in the Alerts tile.
  for (const x of [st({on: false}), mail]) assert.equal(x.toggle, false);
});

test('the page sends alerts for the spots left on, and the Saved page draws them through these rules', () => {
  const page = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  assert.match(page, /alertSpots\(SAVED, new Set\(DATA\.spots\.map\(s => s\.id\)\), off\)/);
  assert.match(page, /const spots = alertedSpots\(\);/);
  assert.match(page, /spotAlert\(\{ push: !!DATA\.push, email: !!DATA\.email, can, on: ALERT_UI\.on/);
  assert.match(page, /sinceSummaryFor\(spots, DATA\.generated_at\)/);
  assert.match(page, /savedGroups\(spots, many \? l\.name : null\)/);
  // Storage of the saved spots is unchanged: no new key for the lists or the saved ids.
  assert.match(page, /Saved spots stay in this browser: nothing is sent to SwimSignal\./);
});
