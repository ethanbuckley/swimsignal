// The swim passport's profile (passport.js, 30 Oct 2026): a name the swimmer may choose, the Water-wise questions and
// badge, points and badges that come out the same however often they are worked out, and nothing kept beyond
// dipcast.passport on this device. node --test tests/site_passport_profile.test.cjs
const { test, beforeEach } = require('node:test');
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

// A browser's storage, for the functions that keep things.
let store;
beforeEach(() => {
  store = new Map();
  global.localStorage = { getItem: k => store.has(k) ? store.get(k) : null, setItem: (k, v) => store.set(k, String(v)), removeItem: k => store.delete(k) };
});

// ------------------------------------------------------------------------------ the same every time
test('points and badges are the same however often they are worked out, and a swim imported twice counts once', () => {
  const list = J.journalEntries([swim('r1', '2026-06-01', 'low', { key: 'jaaaa1111' }), swim('l1', '2026-06-02', 'low', { key: 'jbbbb2222' })]);
  const once = P.passportFrom(list, kindOf, { planned: '2026-05-30', learned: '2026-05-31' });
  for (let n = 0; n < 3; n++) assert.deepEqual(P.passportFrom(list, kindOf, { planned: '2026-05-30', learned: '2026-05-31' }), once);
  assert.equal(once.xp, 2 * P.PASSPORT_XP.outing + 2 * P.PASSPORT_XP.newSpot);
  // The same swims again, as entries read twice: no more points, places or badges.
  const twice = P.passportFrom([...list, ...list], kindOf, { planned: '2026-05-30', learned: '2026-05-31' });
  assert.deepEqual(twice, once);
  // The first version's call, with the planned day alone, still works.
  assert.equal(P.passportFrom(list, kindOf, '2026-05-30').earned['prepared-planner'], '2026-05-30');
});

test('the planned day and the Water-wise day are kept once: doing it again changes nothing', () => {
  assert.equal(P.passportPlanned('2026-10-01'), true);
  assert.equal(P.passportPlanned('2026-10-05'), false);
  assert.equal(P.passportLearned('2026-10-02'), true);
  assert.equal(P.passportLearned('2026-10-09'), false);
  assert.deepEqual(P.passportNow(), { planned: '2026-10-01', learned: '2026-10-02' });
  assert.deepEqual([...store.keys()], [P.PASSPORT_KEY]);   // one key, this file's
});

// ------------------------------------------------------------------------------ Water-wise
test('Water-wise: all four right earns the badge, with no points; anything less is said, and earns nothing', () => {
  assert.equal(P.PASSPORT_LESSON.length, 4);
  const right = P.PASSPORT_LESSON.map(x => x.right);
  assert.deepEqual(P.passportLessonCheck(right), { right: 4, wrong: [], done: true });
  const oneOff = right.map((r, i) => i === 2 ? 1 - r : r);
  assert.deepEqual(P.passportLessonCheck(oneOff), { right: 3, wrong: [2], done: false });
  assert.deepEqual(P.passportLessonCheck([right[0]]), { right: 1, wrong: [1, 2, 3], done: false });   // unanswered is not right
  assert.equal(P.passportLessonCheck(null).done, false);
  // The badge comes from the kept day alone, and adds no points.
  const list = J.journalEntries([swim('r1', '2026-06-01')]);
  const without = P.passportFrom(list, kindOf, {}), with_ = P.passportFrom(list, kindOf, { learned: '2026-06-03' });
  assert.equal(with_.earned['water-wise'], '2026-06-03');
  assert.equal(without.earned['water-wise'], undefined);
  assert.equal(with_.xp, without.xp);
});

test('the questions say what the pages say, and their right answers never call water safe', () => {
  const all = P.PASSPORT_LESSON.map(x => `${x.q} ${x.a[x.right]} ${x.why}`).join(' ');
  assert.match(all, /A lower forecast level does not mean safe water\./);
  assert.match(all, /Official advice comes from the authority that issued it: follow it first\./);
  assert.match(all, /one level for the whole of a day; it does not change between morning and evening/);
  assert.match(all, /No monitored overflow found upstream/);
  assert.match(all, /farm runoff or misconnected drains/);
  for (const x of P.PASSPORT_LESSON) {
    assert.equal(x.a.length, 2);
    assert.doesNotMatch(x.a[x.right], /\bsafe\b|\bclean\b|\bfine\b/i);
  }
  // The right answer is not always in the same place.
  assert.ok(new Set(P.PASSPORT_LESSON.map(x => x.right)).size > 1);
});

// ------------------------------------------------------------------------------ the name
test('a name is optional, cleaned, short, and kept only in dipcast.passport', () => {
  assert.equal(P.passportName('  Ethan\u0007   B  '), 'Ethan B');
  assert.equal(P.passportName('x'.repeat(50)).length, P.PASSPORT_NAME_MAX);
  assert.equal(P.passportName('   '), '');
  assert.deepEqual(P.passportMerge({ planned: '2026-10-01' }, { name: 'Sam' }), { planned: '2026-10-01', name: 'Sam' });
  assert.deepEqual(P.passportMerge({ planned: '2026-10-01', name: 'Sam' }, { name: '' }), { planned: '2026-10-01' });   // removed
  // Read back: only what this file writes, each checked.
  assert.deepEqual(P.passportRead('{"planned":"2026-10-01","learned":"x","name":"  A  B ","gps":"51.5,-0.1","streak":9}'), { planned: '2026-10-01', name: 'A B' });
  assert.deepEqual(P.passportRead('["Sam"]'), {});
  assert.deepEqual(P.passportRead('{"name":7}'), {});
});

test('the name heads the tile, escaped, and is never in what a badge shares', () => {
  const p = P.passportFrom(J.journalEntries([swim('r1', '2026-06-01')]), kindOf, {});
  const h = P.passportCard(p, { name: '<b>Sam</b>' });
  assert.match(h, /<h2 class="sec-h" id="pp-h">Swim passport · &lt;b&gt;Sam&lt;\/b&gt;<\/h2>/);
  assert.match(h, /value="&lt;b&gt;Sam&lt;\/b&gt;"/);
  assert.match(h, /Kept on this device only; never shared, not even with a badge\./);
  assert.match(P.passportCard(p, {}), /<h2 class="sec-h" id="pp-h">Your swim passport<\/h2>/);
  for (const b of P.PASSPORT_BADGES) assert.doesNotMatch(P.passportShareText(b), /Sam/);
  // The sharer gets nothing but the badge's text: the share call takes no name (passportBind).
  const js = fs.readFileSync(join(SITE, 'passport.js'), 'utf8');
  assert.match(js, /navigator\.share\(\{ title: 'SwimSignal', text, url \}\)/);
});

test('the tile offers the questions until all are right, then keeps them to read again', () => {
  const p = P.passportFrom(J.journalEntries([swim('r1', '2026-06-01')]), kindOf, {});
  const ask = P.passportCard(p, {});
  assert.match(ask, /<summary>Water-wise: reading the forecast \(4 questions\)<\/summary><form class="rv-form" id="pp-lesson-form">/);
  assert.equal((ask.match(/type="radio" name="pp-q\d"/g) || []).length, 8);
  assert.match(ask, /<b>Water-wise<\/b> <span class="k">not yet: Answer the four questions on reading the forecast, below\.<\/span>/);
  const done = P.passportCard(P.passportFrom(J.journalEntries([swim('r1', '2026-06-01')]), kindOf, { learned: '2026-06-03' }), { learned: '2026-06-03' });
  assert.doesNotMatch(done, /pp-lesson-form/);
  assert.match(done, /You answered all four on 3 Jun 2026\./);
  assert.match(done, /<b>Water-wise<\/b> <span class="k">earned 3 Jun 2026<\/span>/);
});

// ------------------------------------------------------------------------------ local only
test('the passport sends nothing, keeps nothing but its own key, and puts nothing behind a badge', () => {
  const js = fs.readFileSync(join(SITE, 'passport.js'), 'utf8');
  assert.doesNotMatch(js, /fetch\(|XMLHttpRequest|sendBeacon|WebSocket|indexedDB|navigator\.geolocation|getCurrentPosition/);
  // Every write goes through ppKeep, to PASSPORT_KEY.
  assert.deepEqual(js.match(/localStorage\.setItem\([^,]+/g), ['localStorage.setItem(PASSPORT_KEY']);
  assert.doesNotMatch(js, /removeItem|sessionStorage|document\.cookie/);
  // No other script reads the passport, so no page, forecast, guide or notice can depend on it.
  for (const f of fs.readdirSync(SITE).filter(f => /\.(js|html)$/.test(f) && f !== 'passport.js'))
    assert.doesNotMatch(fs.readFileSync(join(SITE, f), 'utf8'), /dipcast\.passport|PASSPORT_KEY|passportNow|passportFrom\(/, f);
  // Nothing that counts days in a row, or reads a swim's length, distance, speed or temperature (the tile's words
  // say it never rewards them; the code must not read them either).
  assert.doesNotMatch(js, /\b[a-z]\.(minutes|distance|speed|temp\w*|water\w*)\b|streak\w*\s*[=(+]|consecutive/i);
  const privacy = fs.readFileSync(join(__dirname, '../src/dipcast/pages/privacy.html'), 'utf8');
  assert.match(privacy, /the day you first answered all the Water-wise questions right, and a name for the passport if you choose one, in your browser's storage on this device, sent nowhere\. Your answers to the questions are not kept\./);
  assert.match(privacy, /never a place, a date or your name/);
});
