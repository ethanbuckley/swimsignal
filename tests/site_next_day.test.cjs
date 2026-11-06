// After midnight, before the next build (16 Oct 2026, docs/REVIEW-2026-10-16.md 8.1, G1). Every day label
// was keyed to the build's date, and builds come up to 7.7 h apart, so from midnight until the next one
// the page said "Today" for yesterday's row and "Tomorrow: 67 of 105 spots at low risk" about today. Now,
// the page's day is the device's (levels.js, readerDay; until 2 Nov 2026 only while fresh), the rows before it
// leave each spot's five days (fromDay), a spot's page greys yesterday's row, and one quiet line says
// "Issued yesterday at 23:24; today's update is due." The clock here is fixed at 00:30 the day after a
// build at 23:24, in UK time.
// On its own: node --test tests/site_next_day.test.cjs
process.env.TZ = 'Europe/London';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const L = require('../src/dipcast/site/levels.js');

const BUILT = '2026-10-16T23:24:15.271548+01:00';   // Friday 23:24, as spots.json had it
const AT = Date.parse('2026-10-17T00:30:00+01:00');  // Saturday 00:30
const DAYS = ['2026-10-16', '2026-10-17', '2026-10-18', '2026-10-19', '2026-10-20'];   // Fri to Tue, from the build's day
const spot = (id, labels) => ({id, name: id, upstream_summary: {overflows: 1}, location: {mode: 'river'}, now: {risk: 0.01, label: 'low'},
  days: labels.map((l, i) => ({date: DAYS[i], label: l, risk: l === 'low' ? 0.01 : 0.5})),
  contributors: [{site_id: 'X1', p_spill_today: 0.1, p_spill_tomorrow: 0.2, p_spill_days: [0.1, 0.2, 0.3, 0.4, 0.5]}]});

test("the page's day is the device's after midnight", () => {
  assert.equal(L.readerDay(BUILT, AT), '2026-10-17');
  assert.equal(L.readerDay(BUILT, Date.parse('2026-10-16T23:50:00+01:00')), '2026-10-16');   // before midnight
  assert.equal(L.readerDay(BUILT, Date.parse('2026-10-17T07:24:15+01:00')), '2026-10-17');   // 8 h old: still fresh
  // Stale (over 8 h): still the device's day, under the Stale notice. Until 2 Nov 2026 it went back to the
  // build's, and called yesterday "Today" (docs/RELIABILITY-CHECKS-2026-11.md).
  assert.equal(L.readerDay(BUILT, Date.parse('2026-10-17T07:30:00+01:00')), '2026-10-17');
  assert.equal(L.readerDay(BUILT, Date.parse('2026-10-18T09:00:00+01:00')), '2026-10-18');   // a day and a half old
  assert.equal(L.readerDay(BUILT, Date.parse('2026-10-16T22:00:00+01:00')), '2026-10-16');   // a clock behind the build
  // GMT and BST: the build's date is its UK date (build_site stamps generated_at in Europe/London).
  assert.equal(L.readerDay('2026-08-01T00:20:06+01:00', Date.parse('2026-08-01T00:40:00+01:00')), '2026-08-01');   // 23:40 UTC the day before
  assert.equal(L.readerDay('2026-11-01T23:20:06+00:00', Date.parse('2026-11-02T00:30:00Z')), '2026-11-02');
});

test('the rows before the day leave the five days, with the overflows\' chances by day', () => {
  const s = spot('a', ['high', 'low', 'low', 'moderate', 'low']);
  L.fromDay(s, '2026-10-17', '2026-10-16');
  assert.deepEqual(s.days.map(x => x.date), DAYS.slice(1));
  assert.deepEqual(s.past.map(x => x.date), ['2026-10-16']);
  assert.deepEqual(s.contributors[0], {site_id: 'X1', p_spill_today: 0.2, p_spill_tomorrow: 0.3, p_spill_days: [0.2, 0.3, 0.4, 0.5], days_from: '2026-10-17'});
  // Again, nothing moves; a spot's own file merged in later brings its overflows back, and they move once.
  L.fromDay(s, '2026-10-17', '2026-10-16');
  assert.equal(s.days.length, 4); assert.equal(s.contributors[0].p_spill_days.length, 4);
  s.contributors = spot('a', []).contributors;
  L.fromDay(s, '2026-10-17', '2026-10-16');
  assert.deepEqual(s.contributors[0].p_spill_days, [0.2, 0.3, 0.4, 0.5]);
  assert.equal(s.past.length, 1);
  // On the build's own day nothing changes.
  const t = spot('b', ['low', 'low', 'low', 'low', 'low']);
  assert.deepEqual(L.fromDay(t, '2026-10-16', '2026-10-16').days.length, 5);
  assert.equal(t.past, undefined);
  // The headline counts the days left: four after midnight, five on the build's day (the alerts' words).
  L.setToday('2026-10-16');
  try {
    assert.equal(L.headParts(t)[0], 'Low risk for the next five days');
    L.setToday('2026-10-17'); L.fromDay(t, '2026-10-17', '2026-10-16');
    assert.equal(L.headParts(t)[0], 'Low risk for the next four days');
  } finally { L.setToday(null); }
});

// The page's own functions, taken from index.html's script as site_sources.test.cjs does.
const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const pageSrc = html.slice(html.indexOf('<script>\nconst BRAND') + 9, html.lastIndexOf('</script>')).split('\n');
const pageDefs = names => names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`) || l.startsWith(`let ${n} =`));
  assert.ok(i >= 0, `no ${n} in index.html`);
  let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
  return pageSrc.slice(i, j).join('\n'); }).join('\n');
const page = (nowMs, spots) => {
  class FixedDate extends Date { constructor(...a) { super(...(a.length ? a : [nowMs])); } static now() { return nowMs; } }
  const ctx = vm.createContext({Date: FixedDate, navigator: {onLine: true}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site/levels.js'), 'utf8'), ctx);
  vm.runInContext(`let DATA = ${JSON.stringify({generated_at: BUILT, spots})}, VIEW = {day: null}, UPDATE = '';\n`
    + pageDefs(['esc', 'tone', 'dateLabel', 'setDays', 'fiveDays', 'nextDay', 'yesterdayLine', 'lowEligible', 'lowOn',
      'inBand', 'levelPlace', 'BAND_FROM', 'SPILL_EDGES', 'bandPlace', 'spillWord', 'bandSaid', 'dayWx', 'dayRows', 'STALE_MIN', 'ageMin', 'ago', 'agoSpan', 'issued', 'freshness']), ctx);
  for (const f of ['experience.js', 'since.js']) vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site/', f), 'utf8'), ctx);
  vm.runInContext('setDays()', ctx);
  return expr => vm.runInContext(expr, ctx);
};
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();

test('at 00:30 the day after the build, a spot\'s second row is Today, and one line says the update is due', () => {
  //                       Fri     Sat     Sun     Mon      Tue
  const spots = [spot('a', ['high', 'low', 'low', 'high', 'high']), spot('b', ['low', 'high', 'low', 'high', 'high'])];
  const run = page(AT, spots);
  assert.equal(run('today()'), '2026-10-17');
  const rows = run('dayRows(DATA.spots[0])');
  assert.deepEqual([...rows.matchAll(/<span class="d" aria-hidden="true">([^<]+)<\/span>/g)].map(m => m[1]), ['Yesterday', 'Today', 'Sun', 'Mon', 'Tue']);
  assert.match(rows, /^<div class="dkey with-past" aria-hidden="true">.*?<\/div><div class="drows with-past"[^>]*><div class="drow (very)?high past"><span class="sr">Yesterday: (very )?high risk\.<\/span>/);   // greyed, not a button, its word given room
  assert.doesNotMatch(rows, /data-day="2026-10-16"/);
  assert.match(rows, /<button class="drow low" type="button" data-day="2026-10-17"/);
  // The line, where the list, Saved and Plan show their notices; a spot's page says it at its issue time.
  assert.equal(text(run('freshness()')), "Issued yesterday at 23:24; today's update is due.");
  assert.equal(run('freshness(true)'), '');
  assert.match(html, /<p class="issued">\$\{nextDay\(\) \? yesterdayLine\(\) : `Issued \$\{issued\(\)\}, \$\{agoSpan\(\)\} ago`\}<\/p>/);
  // The days on offer are four, from today; the list's strip names them as the phone has them, each with its
  // count at low risk (lowOn, 29 Oct 2026; it replaced the answer line): Saturday is Today, not "Tomorrow".
  assert.equal(run('fiveDays().join()'), DAYS.slice(1).join());
  assert.equal(run('fiveDays().map(d => shortDay(d) + " " + lowOn(d)).join()'), 'Today 1,Sun 2,Mon 0,Tue 0');
  assert.equal(run('dayWord("2026-10-18")'), 'tomorrow');
  // Since you last looked: a look at 23:50 on Friday was yesterday's, not "today".
  assert.match(run(`lookedWhen(${Date.parse('2026-10-16T23:50:00+01:00')})`), /^on Friday at 23:50$/);
});

test('before midnight the days are the build\'s; once stale, still the device\'s, under the Stale notice', () => {
  const before = page(Date.parse('2026-10-16T23:50:00+01:00'), [spot('a', ['high', 'low', 'low', 'high', 'high'])]);
  assert.deepEqual([...before('dayRows(DATA.spots[0])').matchAll(/<span class="d" aria-hidden="true">([^<]+)<\/span>/g)].map(m => m[1]), ['Today', 'Sat', 'Sun', 'Mon', 'Tue']);
  assert.doesNotMatch(before('dayRows(DATA.spots[0])'), /past/);
  assert.equal(before('freshness()'), '');
  assert.equal(before('fiveDays().length'), 5);
  // Reliability checks, 2 Nov 2026: a stale forecast went back to the build's day, so on Saturday at 08:00 Friday's
  // row was "Today". Each row keeps its own date and level; Friday's is Yesterday, and the notice says how old it is.
  const stale = page(Date.parse('2026-10-17T08:00:00+01:00'), [spot('a', ['high', 'low', 'low', 'high', 'high'])]);
  assert.equal(stale('today()'), '2026-10-17');
  assert.deepEqual([...stale('dayRows(DATA.spots[0])').matchAll(/<span class="d" aria-hidden="true">([^<]+)<\/span>/g)].map(m => m[1]), ['Yesterday', 'Today', 'Sun', 'Mon', 'Tue']);
  assert.match(stale('dayRows(DATA.spots[0])'), /<button class="drow low" type="button" data-day="2026-10-17"/);   // Saturday's own level
  assert.equal(stale('fiveDays().join()'), DAYS.slice(1).join());
  assert.equal(stale('nextDay()'), false);   // so a spot's page gives the issue time, not "yesterday ...; today's update is due"
  // Past all five days (six days old): the last row, Tuesday's, two days back, under its own name, not "Yesterday".
  const old = page(Date.parse('2026-10-22T09:00:00+01:00'), [spot('a', ['high', 'low', 'low', 'high', 'high'])]);
  assert.equal(old('today()'), '2026-10-22');
  assert.equal(old('fiveDays().length'), 0);
  assert.deepEqual([...old('dayRows(DATA.spots[0])').matchAll(/<span class="d" aria-hidden="true">([^<]+)<\/span>/g)].map(m => m[1]), ['Tue']);
  assert.match(old('dayRows(DATA.spots[0])'), /<span class="sr">Tuesday 20 October: high risk\.<\/span>/);
  assert.match(text(stale('freshness()')), /^Stale\. This forecast is 8 h 36 min old/);
  assert.doesNotMatch(stale('freshness()'), /today's update is due/);
});
