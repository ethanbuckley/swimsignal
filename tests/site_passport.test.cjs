// The swim passport (passport.js): built from the journal on this device, a few badges and points, never rewarding
// going despite a poor forecast, no streaks, and sharing a badge's name only. node --test tests/site_passport.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { join } = require('node:path');
const J = require('../src/dipcast/site/journal.js');
const P = require('../src/dipcast/site/passport.js');

const SITE = join(__dirname, '../src/dipcast/site');
const KIND = { r1: 'river', r2: 'river', r3: 'river', l1: 'lake' };
const kindOf = id => KIND[id] || null;
const swim = (id, date, level = 'low', extra = {}) => ({ id, date, time: '10:00', at: `${date}T10:30:00.000Z`, name: id.toUpperCase(),
  seen: { head: `${level} risk`, level }, ...extra });
const from = (list, planned = '') => P.passportFrom(J.journalEntries(list), kindOf, planned);

test('counts outings, places and water types, and gives points for outings and first visits', () => {
  const p = from([swim('r1', '2026-06-01'), swim('r1', '2026-06-08'), swim('l1', '2026-06-15')]);
  assert.deepEqual([p.outings, p.places, p.rivers, p.lakes], [3, 2, 1, 1]);
  assert.equal(p.xp, 3 * P.PASSPORT_XP.outing + 2 * P.PASSPORT_XP.newSpot);
  assert.deepEqual([p.first, p.last], ['2026-06-01', '2026-06-15']);
});

test('each badge on the day of the swim that earned it, whatever order the journal holds them in', () => {
  const p = from([swim('r3', '2026-07-20'), swim('r1', '2026-07-01'), swim('l1', '2026-07-05'), swim('r2', '2026-07-10')]);
  assert.deepEqual(p.earned, { 'first-outing': '2026-07-01', 'lake-to-river': '2026-07-05', 'river-explorer': '2026-07-20' });
  // The planner badge comes from the day an outing was first planned with a backup.
  assert.equal(from([swim('r1', '2026-07-01')], '2026-06-30').earned['prepared-planner'], '2026-06-30');
  assert.equal(from([swim('r1', '2026-07-01')]).earned['prepared-planner'], undefined);
});

test('a swim logged when the forecast was high or very high is kept in the record but earns nothing', () => {
  const p = from([swim('r1', '2026-08-01', 'high'), swim('l1', '2026-08-02', 'very high')]);
  assert.deepEqual([p.outings, p.places, p.xp, p.poor], [2, 2, 0, 2]);
  assert.deepEqual(p.earned, {});   // not even First outing
  // The first visit's points go to the first swim that counts.
  const q = from([swim('r1', '2026-08-01', 'very high'), swim('r1', '2026-08-03', 'moderate')]);
  assert.equal(q.xp, P.PASSPORT_XP.outing + P.PASSPORT_XP.newSpot);
  assert.equal(q.earned['first-outing'], '2026-08-03');
  // A swim kept without a forecast counts: nothing says it was poor.
  assert.equal(from([{ id: 'r1', date: '2026-08-01' }]).earned['first-outing'], '2026-08-01');
});

test('a spot no longer listed counts as a place but not as a river or a lake', () => {
  const p = from([swim('gone', '2026-06-01'), swim('r1', '2026-06-02')]);
  assert.deepEqual([p.places, p.rivers, p.lakes], [2, 1, 0]);
});

test('what is kept: only the planned day; anything else reads as nothing', () => {
  assert.deepEqual(P.passportRead('{"planned":"2026-10-28"}'), { planned: '2026-10-28' });
  for (const bad of ['', 'null', '[]', '{"planned":3}', '{"planned":"28/10/2026"}', '{oops']) assert.deepEqual(P.passportRead(bad), {});
  assert.equal(P.PASSPORT_KEY, 'dipcast.passport');
});

test('the card: summary, badges earned or not yet, the rules said, nothing about streaks to keep', () => {
  assert.equal(P.passportCard(from([])), '');
  const h = P.passportCard(from([swim('r1', '2026-06-01'), swim('l1', '2026-06-02', 'high')]));
  assert.match(h, /<b>2 outings · 2 places<\/b> \(1 river, 1 lake\) · 25 points/);
  assert.match(h, /<b>First outing<\/b> <span class="k">earned 1 Jun 2026<\/span> <button type="button" class="linkbtn small" data-pp-share="first-outing">Share<\/button>/);
  assert.match(h, /<b>River explorer<\/b> <span class="k">not yet: Swim at 3 different river spots\.<\/span>/);
  assert.match(h, /1 swim was logged when the forecast was at high risk or very high risk: kept in your record, with no points or badges\./);
  assert.match(h, /never rewards going despite a poor forecast, nor speed, distance, cold or rough water, and it keeps no streaks/);
  assert.match(h, /on this device only: nothing is sent anywhere/);
  assert.doesNotMatch(h, /streak:|in a row|leaderboard/i);
});

test('sharing a badge says its name and nothing about where or when', () => {
  for (const b of P.PASSPORT_BADGES) {
    const t = P.passportShareText(b);
    assert.equal(t, `I earned "${b.name}" on my SwimSignal swim passport.`);
    assert.doesNotMatch(t.replace(b.name, ''), /\d|river|lake|spot|pond/i);   // beyond the badge's own name: no place, no date
  }
});

test('the page draws it under the journal on Saved, binds its shares, and Plan a swim notes a planned backup', () => {
  const page = fs.readFileSync(join(SITE, 'index.html'), 'utf8');
  assert.ok(page.indexOf('<script src="journal.js">') < page.indexOf('<script src="passport.js">'));
  assert.match(page, /if \(typeof passportSection === 'function'\) v \+= passportSection\(DATA\.spots\);/);
  assert.match(page, /const bindSwims = \(\) => \{ if \(typeof journalBindSection === 'function'\) journalBindSection\(\);\n  if \(typeof passportBind === 'function'\) passportBind\(\); \};/);
  assert.match(fs.readFileSync(join(SITE, 'outing.js'), 'utf8'), /if \(pair\.backup && typeof passportPlanned === 'function'\) passportPlanned\(today\(\)\);/);
  // Nothing in it asks a server for anything.
  assert.doesNotMatch(fs.readFileSync(join(SITE, 'passport.js'), 'utf8'), /fetch\(|XMLHttpRequest|sendBeacon/);
});
