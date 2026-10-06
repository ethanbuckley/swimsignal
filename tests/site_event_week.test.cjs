// The event week on the organisers' page (organisers.js, docs/MARKETS-2026-10.md T4 and T5): the
// laboratory test dates from British Triathlon's guidance, the day the forecast first covers the
// event, the calendar file, and the control for alerts about the date.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const O = require('../src/dipcast/site/organisers.js');
const L = require('../src/dipcast/site/levels.js');

const GEN = '2026-10-04T00:16:57+01:00', NOW = Date.parse(GEN) + 2 * 3600e3;
const BASE = 'https://swimsignal.co.uk/';
const DATA = {generated_at: GEN, lead_skill: {spill: [1, 0.84, 0.79, 0.7, 0.59], water: [1, 0.75, 0.69, 0.55, 0.55]}, credits: {}};
const PUSH = {url: 'https://swimsignal-push.example.workers.dev/', key: 'B' + 'A'.repeat(86)};
const day = (date, label, risk) => ({date, label, risk, expected_spilling_overflows: 1, p_ecoli_gt900: 0.1, in_validated_season: false, rain_48h_mm: 2});
const ilkley = {id: 'bw-uke4100-08901', name: 'Wharfe at Cromwheel, Ilkley', kind: 'river', source: 'designated', location: {mode: 'river'},
  assumptions: {max_upstream_km: 60}, now: {label: 'low'}, upstream_summary: {overflows: 15, with_live_feed: 15, without_live_feed: 0},
  classification: {class: 'poor', year: 2025}, contributors: [],
  days: ['2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07', '2026-10-08'].map(d => day(d, 'low', 0.01))};

test('a month before is the same day of the month before, or that month\'s last day', () => {
  assert.equal(O.monthBefore('2027-06-12'), '2027-05-12');
  assert.equal(O.monthBefore('2027-01-15'), '2026-12-15');   // across a year
  assert.equal(O.monthBefore('2027-03-31'), '2027-02-28');   // February is shorter
  assert.equal(O.monthBefore('2028-03-31'), '2028-02-29');   // a leap year
  assert.equal(O.monthBefore('2027-05-31'), '2027-04-30');
  assert.equal(O.monthBefore('2027-03-01'), '2027-02-01');
});

test('the five dates: three tests, the forecast\'s first day and the event, across month ends', () => {
  const dates = iso => O.eventDates(iso).map(d => d.date);
  assert.deepEqual(dates('2027-06-12'), ['2027-05-12', '2027-05-29', '2027-06-05', '2027-06-08', '2027-06-12']);
  assert.deepEqual(dates('2027-03-03'), ['2027-02-03', '2027-02-17', '2027-02-24', '2027-02-27', '2027-03-03']);
  assert.deepEqual(dates('2027-01-02'), ['2026-12-02', '2026-12-19', '2026-12-26', '2026-12-29', '2027-01-02']);
  assert.deepEqual(dates('2027-03-29'), ['2027-02-28', '2027-03-15', '2027-03-22', '2027-03-25', '2027-03-29']);   // across the clocks going forward
  for (const bad of ['2027-02-30', '2027-13-01', '2027-6-12', 'next week', '', null, undefined]) assert.equal(O.eventDates(bad), null, String(bad));
  assert.equal(O.realDate('2028-02-29'), true);
  assert.equal(O.realDate('2027-02-29'), false);
});

test('beyond the five days the page gives the dates to plan for; inside them, the day view as before', () => {
  L.setToday('2026-10-04');
  const june = O.view(ilkley, '2027-06-12', DATA, BASE, NOW);
  assert.ok(june.includes('<h3 id="day-h">Saturday 12 June 2027</h3>'));
  assert.ok(june.includes('first appears on <b>Tuesday 8 June 2027</b>'));
  assert.ok(june.includes('<h3 id="dates-h">Dates to plan for</h3>'));
  assert.ok(june.includes('For a one-off event, British Triathlon\'s water quality guidance suggests laboratory tests a month, two weeks and a week before.'));
  assert.ok(june.includes('the result takes at least 48 hours'));
  for (const [d, what] of [['Wednesday 12 May 2027', 'Laboratory test, about a month before'], ['Saturday 29 May 2027', 'Laboratory test, two weeks before'],
    ['Saturday 5 June 2027', 'Laboratory test, a week before: the last in time to change plans'], ['Tuesday 8 June 2027', 'The forecast first covers the event day'],
    ['Saturday 12 June 2027', 'The event']]) assert.ok(june.includes(`<dt>${d}</dt><dd>${what}</dd>`), d);
  assert.ok(june.includes('id="ics">Add these dates to your calendar</button>') && !june.includes('This date has passed'));
  // The fifth day is inside the forecast: its day view, no dates. The day after is beyond it.
  const fifth = O.view(ilkley, '2026-10-08', DATA, BASE, NOW);
  assert.ok(fifth.includes('ev-level') && !fifth.includes('Dates to plan for') && !fifth.includes('id="ics"'));
  const sixth = O.view(ilkley, '2026-10-09', DATA, BASE, NOW);
  assert.ok(sixth.includes('Dates to plan for') && sixth.includes('<h3 id="day-h">Friday 9 October</h3>'));   // this year: no year
  // Tests that have passed are said so, and left out of the calendar file.
  const soon = O.view(ilkley, '2026-10-12', DATA, BASE, NOW);
  assert.equal(soon.split('This date has passed.').length - 1, 2);
  assert.ok(soon.includes('<dt>Monday 5 October</dt><dd>Laboratory test, a week before: the last in time to change plans</dd>'));
  assert.ok(O.view(ilkley, '2026-10-03', DATA, BASE, NOW).includes('That day has passed'));
});

test('the checklist in the page words the same guidance', () => {
  const page = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/organisers.html'), 'utf8');
  assert.ok(page.includes('For a one-off event British Triathlon suggests tests a month, two weeks and a week before, the last in time to change plans.'));
  assert.ok(page.includes('the result takes at least 48 hours'));
  assert.ok(page.includes('The forecast on this page covers the event day from four days before.'));
});

// ------------------------------------------------------------------ the calendar file
// A small reader for what RFC 5545 asks of these files: CRLF endings, lines of at most 75 octets,
// folded with a space, BEGIN and END in pairs, and in each event one UID, DTSTAMP, DTSTART and DTEND,
// with commas and semicolons in text escaped.
function readIcs(text) {
  assert.ok(text.endsWith('\r\n'), 'ends with CRLF');
  assert.ok(!/\r(?!\n)|(?<!\r)\n/.test(text), 'every line ends with CRLF');
  const physical = text.slice(0, -2).split('\r\n');
  for (const line of physical) assert.ok(Buffer.byteLength(line, 'utf8') <= 75, `over 75 octets: ${line}`);
  assert.ok(!physical.join('').includes('�'), 'no character split by a fold');
  const lines = text.slice(0, -2).replace(/\r\n /g, '').split('\r\n');
  const stack = [], cal = {props: {}, events: []};
  let ev = null;
  for (const line of lines) {
    const m = /^([A-Z-]+)((?:;[A-Z-]+=[^:;]+)*):(.*)$/.exec(line);
    assert.ok(m, `not a content line: ${line}`);
    const [, name, params, value] = m;
    if (name === 'BEGIN') { stack.push(value); if (value === 'VEVENT') ev = {}; continue; }
    if (name === 'END') { assert.equal(stack.pop(), value, 'BEGIN and END pair'); if (value === 'VEVENT') { cal.events.push(ev); ev = null; } continue; }
    const target = ev || cal.props;
    assert.ok(!(name in target), `${name} twice`);
    target[name] = {params, value};
  }
  assert.equal(stack.length, 0);
  assert.equal(cal.props.VERSION.value, '2.0');
  assert.ok(cal.props.PRODID.value);
  const unescape = v => { assert.ok(!/(?<!\\)(?:\\\\)*[;,]/.test(v), `unescaped , or ; in ${v}`); return v.replace(/\\([\\;,])/g, '$1').replace(/\\n/g, '\n'); };
  for (const e of cal.events) {
    for (const p of ['UID', 'DTSTAMP', 'DTSTART', 'DTEND', 'SUMMARY']) assert.ok(e[p], `event without ${p}`);
    assert.match(e.DTSTAMP.value, /^\d{8}T\d{6}Z$/);
    assert.equal(e.DTSTART.params, ';VALUE=DATE'); assert.match(e.DTSTART.value, /^\d{8}$/);
    e.summary = unescape(e.SUMMARY.value); e.description = unescape(e.DESCRIPTION.value);
  }
  assert.equal(new Set(cal.events.map(e => e.UID.value)).size, cal.events.length, 'UIDs differ');
  return cal;
}
const ymd = s => `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6)}`;

test('the calendar file reads as iCalendar: all-day events, folded at 75 octets, text escaped', () => {
  L.setToday('2026-10-06');
  const odd = {...ilkley, id: 'llyn-padarn', name: 'Llyn Padarn; café, “north” \\ side 🏊'};
  const text = O.ics(odd, '2027-06-12', BASE, Date.parse('2026-10-06T12:00:00Z'));
  const cal = readIcs(text);
  assert.deepEqual(cal.events.map(e => ymd(e.DTSTART.value)), ['2027-05-12', '2027-05-29', '2027-06-05', '2027-06-08', '2027-06-12']);
  for (const e of cal.events) {
    const start = ymd(e.DTSTART.value), end = new Date(start + 'T00:00:00Z'); end.setUTCDate(end.getUTCDate() + 1);
    assert.equal(ymd(e.DTEND.value), end.toISOString().slice(0, 10), 'a day long');
    assert.ok(e.summary.endsWith(': Llyn Padarn; café, “north” \\ side 🏊'), e.summary);
    assert.ok(e.description.includes('https://swimsignal.co.uk/organisers.html#spot=llyn-padarn&date=2027-06-12'));
    assert.equal(e.URL.value, 'https://swimsignal.co.uk/organisers.html#spot=llyn-padarn&date=2027-06-12');
    assert.equal(e.DTSTAMP.value, '20261006T120000Z');
  }
  assert.equal(cal.events[0].summary, 'Laboratory water test, a month before the event: Llyn Padarn; café, “north” \\ side 🏊');
  assert.ok(cal.events[0].description.includes('the result takes at least 48 hours'));
  assert.ok(cal.events[4].description.startsWith('A forecast, not a water test'));
  // Folding counts octets, not characters: a line of two-byte letters folds sooner.
  assert.deepEqual(O.icsFold('X:' + 'é'.repeat(40)).split('\r\n').map(l => Buffer.byteLength(l)), [74, 9]);
  assert.equal(O.icsFold('X:' + 'a'.repeat(73)), 'X:' + 'a'.repeat(73));   // 75 octets: no fold
});

test('the calendar file for an event five days off, line for line', () => {
  L.setToday('2026-10-06');
  const s = {id: 'semerwater', name: 'Semerwater'};
  const expected = [
    'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//SwimSignal//Event dates//EN', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH',
    'BEGIN:VEVENT', 'UID:2026-10-11-forecast-semerwater@swimsignal.co.uk', 'DTSTAMP:20261006T093000Z',
    'DTSTART;VALUE=DATE:20261007', 'DTEND;VALUE=DATE:20261008', 'SUMMARY:The forecast first covers the event: Semerwater',
    'DESCRIPTION:SwimSignal\'s pollution risk forecast for Sunday 11 October firs',
    ' t appears today\\, as the last of its five days\\, and is updated several ti',
    ' mes a day. A forecast\\, not a water test. https://swimsignal.co.uk/organis',
    ' ers.html#spot=semerwater&date=2026-10-11',
    'URL:https://swimsignal.co.uk/organisers.html#spot=semerwater&date=2026-10-1', ' 1',
    'TRANSP:TRANSPARENT', 'END:VEVENT',
    'BEGIN:VEVENT', 'UID:2026-10-11-event-semerwater@swimsignal.co.uk', 'DTSTAMP:20261006T093000Z',
    'DTSTART;VALUE=DATE:20261011', 'DTEND;VALUE=DATE:20261012', 'SUMMARY:Event day: Semerwater',
    'DESCRIPTION:A forecast\\, not a water test: check the signs at the water bef',
    ' ore you swim. https://swimsignal.co.uk/organisers.html#spot=semerwater&dat', ' e=2026-10-11',
    'URL:https://swimsignal.co.uk/organisers.html#spot=semerwater&date=2026-10-1', ' 1',
    'TRANSP:TRANSPARENT', 'END:VEVENT', 'END:VCALENDAR', ''].join('\r\n');
  const text = O.ics(s, '2026-10-11', BASE, Date.parse('2026-10-06T09:30:00Z'));
  assert.equal(text, expected);   // the three tests have passed, so they are left out
  readIcs(text);
});

// ------------------------------------------------------------------ alerts for the date
test('the date alert control appears only where the build says the Worker takes dates, and not for a past day', () => {
  L.setToday('2026-10-04');
  const has = (data, iso) => O.view(ilkley, iso, data, BASE, NOW).includes('id="date-alert"');
  assert.equal(has(DATA, '2027-06-12'), false);                                   // alerts off
  assert.equal(has({...DATA, push: PUSH}, '2027-06-12'), false);                  // alerts on, an older Worker
  assert.equal(has({...DATA, push: {...PUSH, dates: true}}, '2027-06-12'), true);
  assert.equal(has({...DATA, push: {...PUSH, dates: true}}, '2026-10-06'), true);  // inside the five days: its level can still change
  assert.equal(has({...DATA, push: {...PUSH, dates: true}}, '2026-10-03'), false);
  assert.ok(O.view(ilkley, '2027-06-12', {...DATA, push: {...PUSH, dates: true}}, BASE, NOW).includes('data-from="2027-06-08"'));
});

test('what the date alert control says, and the list it sends', () => {
  L.setToday('2026-10-04');
  const sub = {endpoint: 'https://fcm.googleapis.com/fcm/send/a'}, id = ilkley.id;
  assert.match(O.dateAlert(null, [], id, '2027-06-12', '2027-06-08'), /First turn on alerts in this browser, from the <a href="saved\/">Saved page<\/a>\./);
  const ask = O.dateAlert(sub, [], id, '2027-06-12', '2027-06-08');
  assert.ok(ask.startsWith('<h3 id="alert-h">Alerts for this date</h3>'));
  assert.ok(ask.includes('A notification when the forecast for this day first appears, on Tuesday 8 June 2027, and again each time its level changes.'));
  assert.ok(ask.indexOf('What asking sends') < ask.indexOf('Alert me about this date'));   // consent before the button
  assert.ok(ask.includes('It keeps up to 10 dates and forgets each one after it has passed.'));
  assert.ok(O.dateAlert(sub, [], id, '2026-10-06', '').includes('A notification each time this day\'s level changes.'));
  const on = O.dateAlert(sub, [{spot: id, date: '2027-06-12'}], id, '2027-06-12', '2027-06-08');
  assert.ok(on.includes('<b>Alerts are on for this date.</b>') && on.includes('data-on="1">Stop alerts for this date'));
  const ten = Array.from({length: 10}, (_, i) => ({spot: id, date: `2027-07-${String(i + 1).padStart(2, '0')}`}));
  const full = O.dateAlert(sub, ten, id, '2027-06-12', '2027-06-08');
  assert.ok(full.includes('You have alerts for 10 dates, the most there can be.') && !full.includes('<button'));
  // The list kept in this browser: only for this push address, and without dates that have passed.
  const raw = JSON.stringify({endpoint: sub.endpoint, dates: [{spot: id, date: '2026-10-03'}, {spot: id, date: '2027-06-12'}, {spot: id, date: 'soon'}]});
  assert.deepEqual(O.keptDates(raw, sub.endpoint, '2026-10-04'), [{spot: id, date: '2027-06-12'}]);
  assert.deepEqual(O.keptDates(raw, 'https://other/', '2026-10-04'), []);
  assert.deepEqual(O.keptDates('{bad', sub.endpoint, '2026-10-04'), []);
  const one = O.withDate([], id, '2027-06-12', true);
  assert.deepEqual(one, [{spot: id, date: '2027-06-12'}]);
  assert.equal(O.withDate(one, id, '2027-06-12', true), one);   // no duplicate
  assert.deepEqual(O.withDate(one, id, '2027-06-12', false), []);
  assert.equal(O.MAX_DATES, 10);
});
