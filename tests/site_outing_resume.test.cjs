// Your outing on Explore (29 Oct 2026): the plan kept in this browser comes back above the list while its day
// is one of the five and its spot is listed (plan.js, planOuting), in the plan's own words (outing.js,
// outingResumeSaid), as a saved card for that day, so official advice leads and the level is the day's.
// node --test tests/site_outing_resume.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const P = require('../src/dipcast/site/plan.js');
const L = require('../src/dipcast/site/levels.js');
const O = require('../src/dipcast/site/outing.js');

const DATES = ['2026-10-29', '2026-10-30', '2026-10-31', '2026-11-01', '2026-11-02'];
const listed = id => ['wey-waverley', 'bw-frensham', 'thames-henley'].includes(id);

test('a kept outing comes back while its day is one of the five and its spot is listed', () => {
  const o = P.planOuting('#day=2026-10-31&within=20&from=Farnham&at=51.2149,-0.7987&spot=wey-waverley&backup=thames-henley&when=morning&act=paddle', DATES, listed);
  assert.deepEqual({ ...o }, { day: '2026-10-31', spot: 'wey-waverley', backup: 'thames-henley', when: 'morning', act: 'paddle',
    hash: '#day=2026-10-31&from=Farnham&at=51.2149%2C-0.7987&within=20&when=morning&spot=wey-waverley&backup=thames-henley&act=paddle' });
});

test('nothing comes back without a spot or a starting place, for a day gone by, or for a spot no longer listed', () => {
  assert.equal(P.planOuting(null, DATES, listed), null);
  assert.equal(P.planOuting('#day=2026-10-31&within=20', DATES, listed), null);   // a plan, no outing
  assert.equal(P.planOuting('#day=2026-10-27&within=20&spot=wey-waverley', DATES, listed), null);   // its day has gone
  assert.equal(P.planOuting('#within=20&spot=wey-waverley', DATES, listed), null);   // no day of its own
  assert.equal(P.planOuting('#day=2026-10-31&from=Farnham&at=51.2149,-0.7987&spot=gone-spot', DATES, listed), null);
  // No starting place, as a shared link has none: Plan a swim would open without the outing, so no card.
  assert.equal(P.planOuting('#day=2026-10-31&within=20&spot=wey-waverley', DATES, listed), null);
  // A backup no longer listed is dropped, the outing kept, and the way back carries no backup.
  const o = P.planOuting('#day=2026-10-31&within=20&from=here&spot=wey-waverley&backup=gone-spot', DATES, listed);
  assert.equal(o.backup, null);
  assert.doesNotMatch(o.hash, /backup=/);
});

test("the line is the plan's own words, and another activity is told the level is the water's", () => {
  L.setToday('2026-10-29');
  try {
    // The clock is the test's 29 October: left to the real one, on 31 Oct after the morning it said the time had passed.
    assert.deepEqual(O.outingResumeSaid({ day: '2026-10-31', when: 'morning', act: null }, 'River Thames, Henley',
      new Date(2026, 9, 29, 9, 0).getTime()),
      ['Saturday morning, with River Thames, Henley as a backup.']);
    assert.deepEqual(O.outingResumeSaid({ day: '2026-10-29', when: '07', act: 'sup' }, null, new Date(2026, 9, 29, 6, 30).getTime()),
      ['Today at 07:00, paddleboarding.', 'The level is for the water, the same whatever you do on it.']);
    assert.deepEqual(O.outingResumeSaid({ day: '2026-10-30', when: null, act: 'swim' }), ['Tomorrow.']);
    // On the day, a time gone by says so, as the plan does (outingTimeNote); before it, nothing extra.
    const at = h => new Date(2026, 9, 29, h, 30).getTime();
    assert.deepEqual(O.outingResumeSaid({ day: '2026-10-29', when: 'morning', act: null }, null, at(20)),
      ['This morning.', 'That time has already passed today.']);
    assert.deepEqual(O.outingResumeSaid({ day: '2026-10-29', when: 'evening', act: null }, null, at(15)), ['This evening.']);
  } finally { L.setToday(null); }
});

test('the page draws it above Saved spots as a saved card for its day, and hides it while the list is narrowed', () => {
  const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  const fn = html.slice(html.indexOf('function outingResume() {'), html.indexOf('\n}\n', html.indexOf('function outingResume() {')));
  assert.match(fn, /planOuting\(stored\(PLAN_KEY\), planDates\(\), has\)/);
  assert.match(fn, /savedCard\(s, false, o\.day\)/);   // advice first, then the outing day's level (savedCard, eaTodayTag)
  assert.match(html, /const places = outingResume\(\) \+ \(saved\.length \?/);   // first in Your places (renderList)
  assert.match(html, /outingGroup\.hidden = Boolean\(VIEW\.q\.trim\(\) \|\| VIEW\.filter !== 'all' \|\| VIEW\.lowOnly\)/);
  assert.doesNotMatch(fn, /localStorage\.setItem/);   // nothing new is kept
  assert.match(fn, /eaTodayApart\(s\)/);
  // A tap on its spot opens the outing's day, as its link says, not the list's (bindItems passes the list's).
  assert.match(html, /select\(a\.dataset\.id, true, true, outing\.dataset\.day === today\(\) \? null : outing\.dataset\.day\)/);   // with official advice, the line that says the level is not the advice
});
