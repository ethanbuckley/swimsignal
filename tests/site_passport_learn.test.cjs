// The Water-wise questions before a first swim (passport.js, passportLessonCard, 30 Oct 2026): on Saved, where the
// passport will be, a new visitor can answer them; the same `learned` day earns the badge once a swim is logged, and the
// questions then live only in the passport tile. node --test tests/site_passport_learn.test.cjs
const { test, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { join } = require('node:path');
const J = require('../src/dipcast/site/journal.js');
const P = require('../src/dipcast/site/passport.js');

const SITE = join(__dirname, '../src/dipcast/site');
const SPOTS = [{ id: 'r1', kind: 'river' }, { id: 'l1', kind: 'lake' }];
const swim = (id, date) => ({ id, date, time: '10:00', at: `${date}T10:30:00.000Z`, name: id.toUpperCase(), key: `j${id}${date.replace(/-/g, '')}`,
  seen: { head: 'Low risk', level: 'low' } });
const count = (h, re) => (h.match(re) || []).length;

let store;
beforeEach(() => {
  store = new Map();
  global.localStorage = { getItem: k => store.has(k) ? store.get(k) : null, setItem: (k, v) => store.set(k, String(v)), removeItem: k => store.delete(k) };
});
const logSwims = list => store.set('dipcast.swims', JSON.stringify(list));

test('before any swim: the questions on their own, with no history, points or badges', () => {
  const h = P.passportSection(SPOTS);
  assert.match(h, /<section class="sec tile pp pp-learn" id="passport" aria-labelledby="pp-h"><h2 class="sec-h" id="pp-h">Water-wise: reading the forecast<\/h2>/);
  assert.match(h, /<summary>Answer the four questions<\/summary><form class="rv-form" id="pp-lesson-form">/);
  assert.equal(count(h, /type="radio" name="pp-q\d"/g), 8);
  assert.match(h, /No points, and nothing sent: this browser keeps only the day you get all four right\./);
  assert.match(h, /Log a swim in your journal and your swim passport starts here: private, on this device\. Get all four right first and Water-wise is on it from the start\./);
  // Nothing personal to show yet, and nothing to earn here but the day kept.
  assert.doesNotMatch(h, /points<\/p>|pp-sum|pp-badges|data-pp-share|outings|pp-name-form/);
  assert.equal(P.passportLessonCard({}), h);
});

test('answered before a swim: kept once, the card says so, and the badge is there from the first logged swim', () => {
  assert.equal(P.passportLearned('2026-10-30'), true);
  assert.deepEqual([...store.keys()], [P.PASSPORT_KEY]);   // the same storage as the passport's, and nothing else
  const done = P.passportSection(SPOTS);
  assert.match(done, /<summary>The four answers, to read again<\/summary><p class="small">You answered all four on 30 Oct 2026\.<\/p>/);
  assert.doesNotMatch(done, /pp-lesson-form/);
  assert.match(done, /Water-wise will be on your swim passport from your first swim logged in the journal\./);
  // A swim a week later: the passport tile, with Water-wise earned on the day it was learned, and no points for it.
  logSwims([swim('r1', '2026-11-06')]);
  const tile = P.passportSection(SPOTS);
  assert.match(tile, /<b>Water-wise<\/b> <span class="k">earned 30 Oct 2026<\/span>/);
  assert.match(tile, /1 outing · 1 place<\/b> \(1 river\) · 25 points/);   // the outing and the first visit only
  // Answering again later changes nothing.
  assert.equal(P.passportLearned('2026-11-07'), false);
  assert.match(P.passportSection(SPOTS), /earned 30 Oct 2026/);
});

test('after the first swim the questions are in the passport tile only: never twice on the page', () => {
  logSwims([swim('r1', '2026-11-06')]);
  for (const kept of [null, '{"learned":"2026-10-30"}']) {
    if (kept) store.set(P.PASSPORT_KEY, kept);
    const h = P.passportSection(SPOTS);
    assert.equal(count(h, /id="pp-lesson"/g), 1, String(kept));
    assert.equal(count(h, /id="passport"/g), 1);
    assert.doesNotMatch(h, /pp-learn/);
    assert.match(h, /<h2 class="sec-h" id="pp-h">Your swim passport<\/h2>/);
  }
  // A journal emptied again (every swim deleted): back to the questions alone, with the day still kept.
  logSwims([]);
  assert.match(P.passportSection(SPOTS), /pp-learn[\s\S]*You answered all four on 30 Oct 2026/);
});

test('Saved draws one of the two in one place, and the lesson needs nothing from the network or a position', () => {
  const page = fs.readFileSync(join(SITE, 'index.html'), 'utf8');
  assert.equal(count(page, /passportSection\(/g), 1);
  assert.match(page, /if \(typeof passportSection === 'function'\) v \+= passportSection\(DATA\.spots\);/);
  const js = fs.readFileSync(join(SITE, 'passport.js'), 'utf8');
  assert.doesNotMatch(js, /fetch\(|XMLHttpRequest|sendBeacon|navigator\.geolocation/);
  // The message after the last right answer says where the badge will be, before or after a swim.
  assert.match(js, /before \? 'All four right\. Water-wise will be on your passport from your first logged swim\.' : 'All four right: Water-wise is on your passport\.'/);
});
