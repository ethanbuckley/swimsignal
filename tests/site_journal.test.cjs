// The swim journal (src/dipcast/site/journal.js): the swims as stored, what the page showed kept with
// each, the copy as a file, and old or odd stored values. The parts that need no page.
// node --test tests/site_journal.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const L = require('../src/dipcast/site/levels.js');
const j = require('../src/dipcast/site/journal.js');

// The swim's day and time are the device's: London's here, as the site's swimmers'.
process.env.TZ = 'Europe/London';
const TODAY = '2026-10-04', ISSUED = '2026-10-04T15:29:52+01:00', LATER = '17:00';
L.setToday(TODAY);
const day = (date, label, risk, rain) => ({ date, label, risk, rain_48h_mm: rain, p_ecoli_gt900: null, in_validated_season: false });
const spot = (extra = {}) => ({
  id: 'stour-dedham', name: 'River Stour, Dedham', kind: 'river', location: { mode: 'river' }, upstream_summary: { overflows: 21 },
  now: { label: 'low', risk: 0.01, discharging_upstream: 0, monitored_upstream: 21 },
  days: [day('2026-10-04', 'low', 0.05, 0), day('2026-10-05', 'moderate', 0.2, 12.4), day('2026-10-06', 'low', 0.1, 3),
    day('2026-10-07', 'low', 0.05, 0.2), day('2026-10-08', 'low', 0.05, 0)],
  river_state: { level_m: 0.197, label: 'low', station: 'Stratford St Mary', observed_at: '2026-10-04T13:45:00Z', typical_low_m: 0.1, typical_high_m: 0.8 },
  water_temp: { temp_c: 14.9, observed_at: '2026-10-04T13:00:00Z', river_km: 2.1, direction: 'upstream', where: 'at Langham' },
  ...extra });
// A photo as a copy holds it: a few bytes of JPEG as a data address.
const pic = (n = 12) => ({ type: 'image/jpeg', full: 'data:image/jpeg;base64,' + Buffer.alloc(n * 3, 7).toString('base64'), thumb: 'data:image/jpeg;base64,' + Buffer.alloc(6, 1).toString('base64') });

test('reads the one-tap log\'s entries, and an older page still reads the new ones', () => {
  const [old] = j.journalEntries(JSON.stringify([{ id: 'wharfe-burnsall', date: '2026-09-30', level: 'low' }]));
  assert.deepEqual(old, { id: 'wharfe-burnsall', date: '2026-09-30', level: 'low', key: 'wharfe-burnsall@2026-09-30', name: '', time: '', minutes: null,
    note: '', photos: 0, at: '', seen: null });
  // The old page kept a swim if it had a string id and date, and showed its level as "<level> risk".
  const s = j.journalNew(spot(), { date: TODAY, time: LATER, minutes: '25', note: 'Cold' }, j.journalSeen(spot(), TODAY, TODAY, ISSUED, LATER), new Date('2026-10-04T16:00:00Z'), () => 0.5);
  const back = JSON.parse(JSON.stringify(s));
  assert.ok(typeof back.id === 'string' && typeof back.date === 'string' && back.level === 'low');
  assert.equal(j.journalEntries(JSON.stringify([back]))[0].key, s.key, 'a new swim keeps its own key');
});

test('old or odd stored values read as absent, never as an error', () => {
  for (const bad of ['', 'not json', '{"id":"a"}', '42', 'null', '"text"', undefined, null]) assert.deepEqual(j.journalEntries(bad), [], String(bad));
  const list = j.journalEntries(JSON.stringify([
    null, 7, 'swim', [], { id: '', date: TODAY }, { id: 'a', date: '2026-02-30' }, { id: 'a', date: '30/09/2026' }, { id: 'a', date: '2026-13-01' }, { id: 5, date: TODAY },
    { id: 'a', date: TODAY, level: 'purple', time: '25:00', minutes: 2.5, note: 'x'.repeat(400), photos: 7, at: 'yesterday', name: { n: 1 },
      seen: { head: 'Low risk', level: 'beige', rain: -3, dis: 4, of: 2, river: { m: 'high' }, temp: { c: 99 }, issued: 1 } },
    { id: 'b', date: TODAY, key: 'k-1234', minutes: '25', photos: -1, seen: 'Low risk' },
    { id: 'c', date: TODAY, key: 'k-1234' },   // the same key again: the first is kept
    { id: 'd', date: TODAY, key: '<script>', minutes: 0 },
  ]));
  assert.deepEqual(list.map(e => e.id), ['a', 'b', 'd']);
  const [a, b, d] = list;
  assert.equal(a.level, null); assert.equal(a.time, ''); assert.equal(a.minutes, null); assert.equal(a.note.length, 280);
  assert.equal(a.photos, 0); assert.equal(a.at, ''); assert.equal(a.name, '');
  assert.deepEqual(a.seen, { head: 'Low risk', level: null, issued: '', rain: null, dis: null, of: null, river: null, temp: null });
  assert.equal(b.minutes, null, 'a number as text is not a number'); assert.equal(b.photos, 0); assert.equal(b.seen, null);
  assert.equal(d.key, `d@${TODAY}`, 'a key that is not one is made again from the spot and day'); assert.equal(d.minutes, null);
});

test('newest first: the day, then the time, then when it was logged', () => {
  const e = (id, date, time, at) => ({ id, date, time, at });
  const list = j.journalEntries([e('a', '2026-10-01', '07:15', ''), e('b', '2026-10-04', '', '2026-10-04T18:00:00.000Z'), e('c', '2026-10-04', '07:40', ''),
    e('d', '2026-09-20', '', ''), e('f', '2026-10-04', '18:30', '')]);
  assert.deepEqual(j.journalSort(list).map(x => x.id), ['f', 'c', 'b', 'a', 'd']);
});

test('keeps what the spot\'s page showed on the day of the swim', () => {
  assert.deepEqual(j.journalSeen(spot(), TODAY, TODAY, ISSUED, LATER),
    { head: 'Low risk', level: 'low', issued: ISSUED, rain: 0, dis: 0, of: 21, river: { m: 0.197, word: 'low water' }, temp: { c: 14.9 } });
  const raised = spot({ days: [day(TODAY, 'high', 0.5, 14.26), ...spot().days.slice(1)], now: { label: 'moderate', discharging_upstream: 2 } });
  const s = j.journalSeen(raised, TODAY, TODAY, ISSUED, LATER);
  assert.equal(s.head, 'High risk: sewage spills'); assert.equal(s.level, 'high'); assert.equal(s.rain, 14.3); assert.equal(s.dis, 2);
});

test('right now\'s spills set the level kept where they are worse than the day\'s forecast', () => {
  const s = j.journalSeen(spot({ now: { label: 'very high', discharging_upstream: 3 } }), TODAY, TODAY, ISSUED, LATER);
  assert.equal(s.head, 'Very high risk: sewage spills'); assert.equal(s.level, 'very high'); assert.equal(s.dis, 3);
  // Raised by spills that have stopped, whose water is still counted: the words say so, as the page does.
  const recent = j.journalSeen(spot({ now: { label: 'moderate', discharging_upstream: 0 } }), TODAY, TODAY, ISSUED, LATER);
  assert.equal(recent.head, 'Moderate risk: recent sewage spills'); assert.equal(recent.dis, 0);
  assert.equal(j.journalSeen(spot({ days: [{ ...day(TODAY, null, null, null) }, ...spot().days.slice(1)], now: { label: 'low' } }), TODAY, TODAY, ISSUED, LATER).head,
    'No forecast for this day', 'a low right now does not make a day without a forecast low');
});

test('nothing is kept for another day, or a day the forecast does not cover', () => {
  assert.equal(j.journalSeen(spot(), '2026-10-03', TODAY, ISSUED, LATER), null, 'logged after the day');
  assert.equal(j.journalSeenWhy(spot(), '2026-10-03', LATER, TODAY, ISSUED), 'No forecast: the page has none for the days before today.');
  assert.equal(j.journalSeen(spot(), '2026-10-09', '2026-10-09', ISSUED, LATER), null, 'a forecast that has run out');
  assert.equal(j.journalSeenWhy(spot(), '2026-10-09', LATER, '2026-10-09', ISSUED), 'No forecast: the one on this device does not cover that day.');
  assert.equal(j.journalSeen(spot({ days: [] }), TODAY, TODAY, ISSUED, LATER), null);
});

test('a swim before the forecast was issued, or without a time, keeps no forecast, and the form says why', () => {
  // The seeded screenshot's 07:40 swim had kept "the forecast issued Sun 4 Oct, 15:29", which did not exist then.
  assert.equal(j.journalSeen(spot(), TODAY, TODAY, ISSUED, '07:40'), null);
  assert.equal(j.journalSeenWhy(spot(), TODAY, '07:40', TODAY, ISSUED), 'No forecast: this one was issued at 15:29, after your swim.');
  assert.equal(j.journalSeen(spot(), TODAY, TODAY, ISSUED, '15:29'), null, 'the minute it was issued, but before its second');
  assert.equal(j.journalSeen(spot(), TODAY, TODAY, ISSUED, '15:30').head, 'Low risk');
  assert.equal(j.journalSeen(spot(), TODAY, TODAY, ISSUED, ''), null);
  assert.equal(j.journalSeenWhy(spot(), TODAY, '', TODAY, ISSUED), 'No forecast: without the time of your swim, it may have been before this forecast was issued at 15:29.');
  assert.equal(j.journalSeen(spot(), TODAY, TODAY, ISSUED, '7.40'), null, 'a time that is not one is no time');
  // A forecast issued the evening before covers a morning swim.
  assert.equal(j.journalSeen(spot(), TODAY, TODAY, '2026-10-03T23:10:00+01:00', '07:40').issued, '2026-10-03T23:10:00+01:00');
  const why = j.journalSeenWhy(spot(), TODAY, '07:40', TODAY, ISSUED);
  assert.equal(j.journalKeptHtml(null, why).match(/<p class="rv-meta">(.*)<\/p>/)[1], why, 'the form says it in the same words');
  assert.equal(j.journalSeenWhy(spot(), TODAY, LATER, TODAY, ISSUED), '');
});

test('a reading the page would not show is not kept', () => {
  const s = j.journalSeen(spot({ river_state: { stale: true, level_m: 0.4, label: 'high' }, water_temp: { temp_c: 15, observed_at: 'later', direction: 'upstream', river_km: 1 } }), TODAY, TODAY, ISSUED, LATER);
  assert.equal(s.river, null); assert.equal(s.temp, null);
  assert.equal(j.journalSeen(spot({ river_state: null, water_temp: undefined }), TODAY, TODAY, ISSUED, LATER).river, null);
});

test('a spot with nothing to forecast keeps its plain level, its rain and its readings', () => {
  const plain = spot({ upstream_summary: { overflows: 0 }, now: {}, river_state: undefined });
  assert.deepEqual(j.journalSeen(plain, TODAY, TODAY, ISSUED, LATER),
    { head: 'No sewage risk from monitored overflows', level: 'no overflows', issued: ISSUED, rain: 0, dis: null, of: null, river: null, temp: { c: 14.9 } });
  const lake = { id: 'x', name: 'X', error: 'An isolated lake: no river flows into it', days: [], upstream_summary: { overflows: 0 } };
  assert.equal(j.journalSeen(lake, TODAY, TODAY, ISSUED, LATER).level, 'no river connection');
});

test('what was kept, in words', () => {
  const w = s => j.journalSeenWords({ head: 'Low risk', level: 'low', issued: '', rain: null, dis: null, of: null, river: null, temp: null, ...s });
  assert.deepEqual(w({ rain: 0, dis: 0, of: 16, river: { m: 0.311, word: 'low water' }, temp: { c: 16.2 } }),
    ['no rain in the last two days', 'none of the 16 overflows upstream discharging', 'river 0.31 m, low water', 'water 16°C']);
  assert.deepEqual(w({ rain: 0.3, dis: 2, of: 15 }), ['under 1 mm of rain in the last two days', '2 of 15 overflows upstream discharging']);
  assert.deepEqual(w({ rain: 14.2, dis: 1, of: 1, river: { m: 1, word: '' } }), ['14 mm of rain in the last two days', 'the overflow upstream discharging', 'river 1.00 m']);
  assert.deepEqual(w({ dis: 0, of: 1 }), ['the overflow upstream not discharging']);
  assert.deepEqual(w({}), []);
});

test('the form\'s checks, in its words', () => {
  const ok = { date: TODAY, time: '07:40', minutes: '25', note: 'Cold' };
  assert.equal(j.journalProblem(ok, TODAY), '');
  assert.equal(j.journalProblem({ ...ok, time: '', minutes: '' }, TODAY), '', 'the time and the minutes are optional');
  assert.match(j.journalProblem({ ...ok, date: '2026-10-05' }, TODAY), /today or before/);
  assert.match(j.journalProblem({ ...ok, date: '' }, TODAY), /today or before/);
  assert.match(j.journalProblem({ ...ok, time: '7.40' }, TODAY), /hours and minutes/);
  for (const m of ['0', '601', '2.5', 'ten', '-5']) assert.match(j.journalProblem({ ...ok, minutes: m }, TODAY), /whole number from 1 to 600/, m);
  assert.match(j.journalProblem({ ...ok, note: 'x'.repeat(281) }, TODAY), /280 characters/);
  assert.match(j.journalProblem(ok, TODAY, j.JOURNAL_LIMITS.swims), /holds 500 swims/);
});

test('a new swim keeps the spot, the draft and what was shown, and no health questions are asked', () => {
  const s = j.journalNew(spot(), { date: TODAY, time: '', minutes: '', note: '  Two herons.  ' }, null, new Date('2026-10-04T16:00:00Z'), () => 0);
  assert.deepEqual({ ...s, key: undefined }, { id: 'stour-dedham', date: TODAY, level: null, key: undefined, name: 'River Stour, Dedham', time: '', minutes: null,
    note: 'Two herons.', photos: 0, at: '2026-10-04T16:00:00.000Z', seen: null });
  assert.match(s.key, /^j[0-9a-z]+$/);
  const form = j.journalFormHtml(TODAY, '17:00');
  assert.ok(!/\b(symptoms?|ill|illness|unwell|doctor|health)\b/i.test(form), 'the form asks nothing about health');
});

test('a copy holds the swims and their photos, and reads back the same', () => {
  const list = j.journalEntries([{ id: 'a', date: TODAY, key: 'k-aaaa', photos: 2, note: 'One' }, { id: 'b', date: '2026-09-30', level: 'moderate' }]);
  const text = j.journalFile(list, { 'k-aaaa-0': pic(), 'k-aaaa-1': pic(20) }, '2026-10-04T16:00:00.000Z');
  const v = JSON.parse(text);
  assert.equal(v.kind, 'swimsignal-journal'); assert.equal(v.version, 1); assert.match(v.about, /keep it private/);
  const back = j.journalRead(text);
  assert.deepEqual(back.swims, list);
  assert.deepEqual(back.photos, { 'k-aaaa': [pic(), pic(20)] });
  assert.deepEqual(j.journalRead(JSON.stringify(list)).swims, list.map(e => ({ ...e, photos: 0 })), 'a bare list of swims is read too, without photos');
});

test('a copy\'s odd parts are dropped, and a file that is not one reads as none', () => {
  for (const t of ['', 'nope', '{}', '{"kind":"other","swims":[]}', '{"kind":"swimsignal-journal","swims":{}}', '7']) assert.equal(j.journalRead(t), null, t);
  const big = { ...pic(), full: 'data:image/jpeg;base64,' + 'A'.repeat(4 * 1024 * 1024 + 4) };
  const text = JSON.stringify({ kind: 'swimsignal-journal', swims: [{ id: 'a', date: TODAY, key: 'k-aaaa', photos: 3 }, { id: 'b', date: 'never' }],
    photos: { 'k-aaaa-0': { ...pic(), type: 'text/html' }, 'k-aaaa-1': pic(), 'k-aaaa-2': big, 'k-zzzz-0': pic(),
      'k-aaaa-3': pic() } });
  const back = j.journalRead(text);
  assert.deepEqual(back.swims.map(e => [e.key, e.photos]), [['k-aaaa', 1]], 'only the good photo, numbered from 0');
  assert.deepEqual(back.photos, { 'k-aaaa': [pic()] });
  assert.equal(j.jnPhotoOk({ ...pic(), full: 'data:image/jpeg;base64,@@@@' }), null);
  assert.equal(j.jnPhotoOk({ ...pic(), thumb: 'data:image/png;base64,AAAA' }), null, 'one type for both');
});

test('adding a copy skips the swims already here, and stops at the journal\'s limits', () => {
  const have = j.journalEntries([{ id: 'a', date: '2026-09-01', key: 'k-0001', photos: 1 }]);
  const incoming = j.journalEntries([{ id: 'a', date: '2026-09-01', key: 'k-0001', photos: 1 }, { id: 'b', date: '2026-09-02', key: 'k-0002', photos: 2 },
    { id: 'c', date: '2026-09-03', key: 'k-0003', photos: 3 }, { id: 'd', date: '2026-09-04', key: 'k-0004' }]);
  const r = j.journalMerge(have, incoming, 3, 4);
  assert.deepEqual(r.added.map(e => [e.key, e.photos]), [['k-0004', 0], ['k-0003', 3]], 'the newest first while there is room');
  assert.equal(r.same, 1); assert.equal(r.over, 1); assert.equal(r.photosLeft, 0);
  assert.equal(r.list.length, 3);
  const r2 = j.journalMerge(have, incoming, 10, 4);
  assert.deepEqual(r2.added.map(e => [e.key, e.photos]), [['k-0004', 0], ['k-0003', 3], ['k-0002', 0]]);
  assert.equal(r2.photosLeft, 2, 'photos past the room left are left out, and said');
});

test('the journal says it is only on this device, and shows what was typed as text', () => {
  const list = j.journalEntries([
    { id: 'stour-dedham', date: TODAY, key: 'k-aaaa', time: '07:40', minutes: 25, note: '<img src=x onerror=alert(1)> cold', photos: 1, name: 'River Stour, Dedham', at: '2026-10-04T16:00:00.000Z',
      seen: { head: 'Moderate risk: sewage spills', level: 'moderate', issued: ISSUED, rain: 14, dis: 2, of: 21, river: null, temp: null } },
    { id: 'gone-spot', date: '2026-09-30', level: 'low', name: '<b>Old</b>' },
    { id: 'x', date: '2026-09-29', key: 'k-late', at: '2026-10-01T10:00:00.000Z' },
  ]);
  const spots = new Map([['stour-dedham', { id: 'stour-dedham', name: 'River Stour, Dedham' }]]);
  const h = j.journalSection(list, { spots, href: id => `/spot/${id}/`, now: new Date('2026-10-04T16:00:00Z') });
  assert.ok(h.includes('<b>Only on this device.</b> 3 swims, newest first') && h.includes('Nothing in it is sent anywhere.'));
  assert.ok(h.includes('&lt;img src=x onerror=alert(1)&gt; cold') && !h.includes('<img src=x'));
  assert.ok(h.includes('&lt;b&gt;Old&lt;/b&gt;') && !h.includes('data-jn-spot="gone-spot"'), 'a spot no longer listed is named, not linked');
  assert.ok(h.includes('<a href="/spot/stour-dedham/" data-jn-spot="stour-dedham">River Stour, Dedham</a> · 25 minutes in the water'));
  assert.ok(h.includes('<span class="badge b-moderate">Moderate risk: sewage spills</span>'));
  assert.ok(h.includes('14 mm of rain in the last two days · 2 of 21 overflows upstream discharging'));
  assert.ok(h.includes('<span class="badge b-low">Low risk</span> <span class="jn-k">in the day\'s forecast</span>'), 'the one-tap log\'s level');
  assert.ok(h.includes('No forecast was kept with this swim.'));
  assert.ok(h.includes('data-jn-photo="k-aaaa-0"') && h.includes('Save a copy') && h.includes('Delete all'));
  assert.ok(!h.includes('jn-all'), 'five or fewer: no "Show all"');
  const many = j.journalEntries(Array.from({ length: 7 }, (_, i) => ({ id: 'a', date: `2026-09-0${i + 1}` })));
  const hm = j.journalSection(many);
  assert.equal((hm.match(/<li class="rv jn" hidden/g) || []).length, 2); assert.ok(hm.includes('Show all 7'));
  const empty = j.journalSection([]);
  assert.ok(empty.includes('Only on this device.') && empty.includes('Add swims from a copy') && !empty.includes('Save a copy') && !empty.includes('Delete all'));
  const form = j.journalFormHtml(TODAY, '17:00');
  assert.ok(form.includes('<b>Only on this device.</b>') && form.includes(`max="${TODAY}"`) && form.includes('value="17:00"') && form.includes('Photos'));
  assert.ok(!j.journalFormHtml(TODAY, '17:00', false).includes('Photos'), 'no photos where the browser cannot keep them');
  assert.ok(j.journalKeptHtml(null, j.journalSeenWhy(spot(), '2026-10-01', '07:00', TODAY, ISSUED)).includes('none for the days before today'));
  assert.ok(!h.includes('Tell Ethan') && !h.includes('feedback.html') && !h.includes('mailto:'), 'a private journal holds no link that sends anything');
});

test('nothing in the journal is sent anywhere', () => {
  const src = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/journal.js'), 'utf8').replace(/^\s*\/\/.*$/gm, '');
  for (const w of ['fetch(', 'XMLHttpRequest', 'sendBeacon', 'WebSocket', 'EventSource', 'method:', 'FormData', '.submit(']) assert.ok(!src.includes(w), w);
  // The page's own hooks into it do not send it either.
  const page = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  const hooks = page.slice(page.indexOf('// ------------------------------------------------------------------------------ swim journal'), page.indexOf('// ------------------------------------------------------------------------------ a picture to share'));
  assert.ok(hooks.includes('journalLogBind') && !/fetch|sendBeacon|XMLHttpRequest/.test(hooks));
});
