// Find a window on Saved (findwindow.js, a prototype): each saved spot's days in the next five whose displayed
// SwimSignal forecast is Low, adjacent days as one range, each day taken on its own; today as its level shows it,
// spills right now included; no window without a day-by-day forecast; days, never hours; no ranking; an official notice on a line
// of its own and never a reason to call another spot safer. node --test tests/site_find_window.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { join } = require('node:path');
const L = require('../src/dipcast/site/levels.js');
const ea = require('../src/dipcast/site/eatoday.js');
const W = require('../src/dipcast/site/findwindow.js');

const SITE = join(__dirname, '../src/dipcast/site');
const DATES = ['2026-10-28', '2026-10-29', '2026-10-30', '2026-10-31', '2026-11-01'];
L.setToday(DATES[0]);
const day = (date, label) => ({ date, risk: label === 'low' ? 0.01 : 0.5, label, expected_spilling_overflows: label === 'low' ? 0 : 2,
  rain_48h_mm: 1, p_ecoli_gt900: 0.02, in_validated_season: false });
const spot = (labels, extra = {}) => ({ id: 'x', name: 'River X', kind: 'river', lat: 51, lon: -1, upstream_summary: { overflows: 2 },
  assumptions: { max_upstream_km: 15 }, now: { label: 'low', discharging_upstream: 0 }, contributors: [],
  days: DATES.map((d, i) => day(d, labels[i])), ...extra });
const NOTICE = { line: 'Environment Agency: advice against bathing (harmful algae) since 19 Jun 2026', publisher: 'Environment Agency',
  link: 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj2310-11945', since: '2026-06-19', checked: '2026-10-26', state: 'checked' };

test('Low days, adjacent ones as one range, each day on its own', () => {
  const f = W.fwFind(spot(['low', 'low', 'high', 'low', 'moderate']), DATES);
  assert.deepEqual(f.ranges, [{ from: DATES[0], to: DATES[1], n: 2 }, { from: DATES[3], to: DATES[3], n: 1 }]);
  assert.deepEqual(W.fwWords(f), ['Low risk: Wed 28 Oct to Thu 29 Oct and Sat 31 Oct.']);
  // A later higher day does not take a Low day out.
  assert.deepEqual(W.fwFind(spot(['low', 'very high', 'very high', 'very high', 'very high']), DATES).ranges, [{ from: DATES[0], to: DATES[0], n: 1 }]);
  // All five, one range.
  assert.deepEqual(W.fwWords(W.fwFind(spot(['low', 'low', 'low', 'low', 'low']), DATES)), ['Low risk: Wed 28 Oct to Sun 1 Nov.']);
  assert.deepEqual(W.fwWords(W.fwFind(spot(['moderate', 'high', 'moderate', 'high', 'moderate']), DATES)), ['No day in the next five is at low risk here.']);
});

test('today is as its displayed level shows it: spills right now raise it, so it is no window', () => {
  const s = spot(['low', 'low', 'moderate', 'moderate', 'moderate'], { now: { label: 'high', discharging_upstream: 3 } });
  assert.equal(L.dayLevel(s, DATES[0]), 'high');   // levels.js raises today by right now's spills
  assert.deepEqual(W.fwWords(W.fwFind(s, DATES)), ['Low risk: Thu 29 Oct.']);
  // Low right now leaves a Low today as it is.
  assert.deepEqual(W.fwFind(spot(['low', 'low', 'moderate', 'moderate', 'moderate']), DATES).ranges, [{ from: DATES[0], to: DATES[1], n: 2 }]);
});

test('a day with no level is not Low, breaks a range, and is named', () => {
  const s = spot(['low', 'low', 'low', 'low', 'low']);
  s.days[2] = { date: DATES[2] };   // no rain data for the day: no level
  const f = W.fwFind(s, DATES);
  assert.notEqual(L.dayLevel(s, DATES[2]), 'low');
  assert.deepEqual(f.ranges.map(r => [r.from, r.to]), [[DATES[0], DATES[1]], [DATES[3], DATES[4]]]);
  assert.deepEqual(W.fwWords(f), ['Low risk: Wed 28 Oct to Thu 29 Oct and Sat 31 Oct to Sun 1 Nov.', 'No forecast for Fri 30 Oct.']);
});

test('no day-by-day forecast: no window, said so, never Low', () => {
  const plain = spot(['low', 'low', 'low', 'low', 'low'], { upstream_summary: { overflows: 0 } });
  assert.equal(L.daily(plain), false);
  const f = W.fwFind(plain, DATES);
  assert.deepEqual(f, { daily: false, ranges: [], unknown: [] });
  assert.deepEqual(W.fwWords(f), ['This spot has no day-by-day pollution forecast, so there is no window to find here.']);
  const failed = spot(['low', 'low', 'low', 'low', 'low'], { error: 'forecast failed: rain' });
  assert.equal(W.fwFind(failed, DATES).daily, false);
});

test('the tile: spots in the order given, the notice apart from the levels, days not hours, no "safe" or "best"', () => {
  const a = spot(['low', 'low', 'high', 'high', 'high'], { id: 'a', name: 'Frensham <Great> Pond', official: [NOTICE] });
  const b = spot(['high', 'high', 'low', 'low', 'low'], { id: 'b', name: 'River Wey' });
  const h = W.fwSection([a, b], DATES, s => `spot/${s.id}/`);
  assert.ok(h.indexOf('data-id="a"') < h.indexOf('data-id="b"'));   // the list's order, not a ranking
  assert.ok(h.includes('Frensham &lt;Great&gt; Pond'));
  // The notice in its own words, on its own line, before the levels, and said to be apart from them.
  const brief = ea.eaTodayBrief(a);
  const at = s => h.indexOf(s);
  assert.ok(at(`<p class="o-tag">${brief}</p>`) > 0 && at(`<p class="o-tag">${brief}</p>`) < at('Low risk: Wed 28 Oct to Thu 29 Oct.'));
  assert.ok(h.includes('<p class="fw-apart">The official notice is not part of these levels: read it first.</p>'));
  // Only the spot with a notice carries the line; the other is not said to be safer or better for lacking one.
  assert.equal((h.match(/fw-apart/g) || []).length, 1);
  assert.doesNotMatch(h, /\bsafer?\b(?! check)|\bbest\b|\bbetter\b|\bhour(s|ly)?\b(?!\.)/i);
  assert.match(h, /One level covers a whole day, not an hour\./);
  assert.match(h, /Low risk is not a safety check/);
  assert.equal(W.fwSection([], DATES, () => ''), '');
});

test('the page draws it on Saved, after the comparison, from the five days it has', () => {
  const page = fs.readFileSync(join(SITE, 'index.html'), 'utf8');
  assert.match(page, /if \(spots\.length && typeof fwSection === 'function'\) v \+= fwSection\(spots, fiveDays\(\), s => spotPath\(s\.id\)\);/);
  assert.ok(page.indexOf('compareSection(savedCompare(spots))') < page.indexOf('fwSection(spots, fiveDays()'));
  // After levels.js and eatoday.js, whose names it reads.
  for (const before of ['levels.js', 'eatoday.js']) assert.ok(page.indexOf(`<script src="${before}">`) < page.indexOf('<script src="findwindow.js">'), before);
  // No request: the script fetches nothing and stores nothing.
  assert.doesNotMatch(fs.readFileSync(join(SITE, 'findwindow.js'), 'utf8'), /fetch\(|localStorage|sessionStorage/);
});


test('the notice line follows its kind: a restricting notice says advice and follow; any other stays a notice to read', () => {
  const restricting = spot(['low', 'low', 'high', 'high', 'high'], { id: 'r', name: 'Frensham Great Pond', official: [{ ...NOTICE, restricts: true }] });
  const neutral = spot(['low', 'low', 'high', 'high', 'high'], { id: 'n', name: 'Status Pond', official: [{ ...NOTICE,
    line: 'City of London: swimming status notice (members only this week) since 20 Oct 2026', publisher: 'City of London', restricts: false }] });
  const legacy = spot(['low', 'low', 'high', 'high', 'high'], { id: 'l', name: 'Legacy Pond', official: [{ ...NOTICE }] });
  assert.equal(W.fwApart(restricting), 'The official advice is not part of these levels: follow it first.');
  assert.equal(W.fwApart(neutral), 'The official notice is not part of these levels: read it first.');
  assert.equal(W.fwApart(legacy), 'The official notice is not part of these levels: read it first.');
  const h = W.fwSection([restricting, neutral, legacy], DATES, s => `spot/${s.id}/`);
  // Each notice in its own words, before its levels; the windows themselves are the same whatever the notice.
  for (const s of [restricting, neutral, legacy]) {
    const at = h.indexOf(`<p class="o-tag">${ea.eaTodayBrief(s)}</p>`);
    assert.ok(at > 0 && at < h.indexOf('Low risk: Wed 28 Oct to Thu 29 Oct.', at), s.name);
  }
  assert.equal((h.match(/follow it first/g) || []).length, 1);   // the restricting one only
  assert.equal((h.match(/Low risk: Wed 28 Oct to Thu 29 Oct\./g) || []).length, 3);
  assert.doesNotMatch(h, /\bsafer?\b(?! check)|\bbest\b|\bbetter\b/i);
});
