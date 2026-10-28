// Keeping a plan's outing (src/dipcast/site/outing.js, with spotdate.js): "Alert me about this outing" through
// the push Worker's alerts for a date, sent exactly as the organisers' page sends them, and "Add to calendar".
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const L = require('../src/dipcast/site/levels.js');
const O = require('../src/dipcast/site/outing.js');
const SD = require('../src/dipcast/site/spotdate.js');
const Org = require('../src/dipcast/site/organisers.js');
const read = f => fs.readFileSync(path.join(__dirname, '..', f), 'utf8');

L.setToday('2026-10-31');   // a Saturday
const DAY = '2026-11-01';
const SUB = {endpoint: 'https://fcm.googleapis.com/fcm/send/abc', toJSON() { return {endpoint: this.endpoint, keys: {p256dh: 'k', auth: 'a'}}; }};
const byId = new Map([['frensham', {id: 'frensham', name: 'Frensham Great Pond'}], ['wey', {id: 'wey', name: 'River Wey at Waverley'}]]);
const PLAN = {day: DAY, spot: 'frensham', backup: 'wey', when: 'morning'};
const pairs = O.outingPairs(PLAN, byId);
const fill = n => Array.from({length: n}, (_, i) => ({spot: 'other', date: `2026-12-${String(i + 1).padStart(2, '0')}`}));

// ------------------------------------------------------------------------------ what is asked for
test('the outing\'s pairs: its spot, then its backup, each on the plan\'s day; only listed spots', () => {
  assert.deepEqual(O.outingPairs(PLAN), [{spot: 'frensham', date: DAY}, {spot: 'wey', date: DAY}]);
  assert.deepEqual(pairs.map(p => p.name), ['Frensham Great Pond', 'River Wey at Waverley']);
  assert.deepEqual(O.outingPairs({day: DAY, spot: 'frensham'}), [{spot: 'frensham', date: DAY}]);
  assert.deepEqual(O.outingPairs({day: DAY, spot: 'frensham', backup: 'gone'}, byId).map(p => p.spot), ['frensham']);   // no longer listed
  assert.deepEqual(O.outingPairs({day: DAY}), []);
});

test('the request is the organisers\' page\'s: the subscription and the whole list of {spot, date}, nothing else', async () => {
  const sent = [];
  const fetcher = async (url, init) => { sent.push({url, init}); return {ok: true, status: 200, text: async () => ''}; };
  const on = O.outingList([{spot: 'semerwater', date: '2027-06-12'}], pairs, true);
  await SD.sendDates('https://push.example/', SUB, on, fetcher);
  const off = O.outingList(on, pairs, false);
  await SD.sendDates('https://push.example/', SUB, off, fetcher);
  assert.equal(sent[0].url, 'https://push.example/subscribe');
  assert.equal(sent[0].init.method, 'POST');
  assert.equal(sent[0].init.headers['Content-Type'], 'application/json');
  const body = JSON.parse(sent[0].init.body);
  assert.deepEqual(Object.keys(body), ['subscription', 'dates']);   // no spots, no weekly: the Worker keeps those
  assert.deepEqual(body.subscription, SUB.toJSON());
  // Names never leave the browser: each pair is the two fields push/src/dates.js keeps.
  assert.deepEqual(body.dates, [{spot: 'semerwater', date: '2027-06-12'}, {spot: 'frensham', date: DAY}, {spot: 'wey', date: DAY}]);
  // Stopping sends the list without the outing's pairs; an organiser's date stays.
  assert.deepEqual(JSON.parse(sent[1].init.body), {subscription: SUB.toJSON(), dates: [{spot: 'semerwater', date: '2027-06-12'}]});
  // The organisers' page builds its body with the same function, so the two cannot drift.
  assert.equal(SD.datesBody(SUB, off), JSON.stringify({subscription: SUB.toJSON(), dates: off}));
  assert.match(read('src/dipcast/site/organisers.js'), /await SD\(\)\.sendDates\(data\.push\.url, sub, dates\)/);
  assert.match(read('src/dipcast/site/outing.js'), /await D\.sendDates\(DATA\.push\.url, st\.sub, next\)/);
});

test('a refusal and a lost connection come back as words for the page', async () => {
  const no = status => async () => ({ok: false, status, text: async () => 'at most 10 dates'});
  await assert.rejects(SD.sendDates('https://p/', SUB, [], no(400)), /^Error: at most 10 dates$/);
  await assert.rejects(SD.sendDates('https://p/', SUB, [], no(503)), /the alert service answered 503/);
  await assert.rejects(SD.sendDates('https://p/', SUB, [], async () => { throw new TypeError('offline'); }), /could not be reached/);
});

test('the cap is the Worker\'s, and the spot goes before the backup when only one fits', () => {
  assert.equal(SD.MAX_DATES, Number(/export const MAX_DATES = (\d+);/.exec(read('push/src/dates.js'))[1]));
  assert.equal(Org.MAX_DATES, SD.MAX_DATES);
  assert.deepEqual(O.outingAsk([], pairs), {on: [], add: pairs, left: []});
  const nine = O.outingAsk(fill(9), pairs);
  assert.deepEqual([nine.add.map(p => p.spot), nine.left.map(p => p.spot)], [['frensham'], ['wey']]);
  const ten = O.outingAsk(fill(10), pairs);
  assert.deepEqual([ten.add, ten.left.length], [[], 2]);
  // Pairs already on take no room: ten with the outing's spot among them leaves the backup out, nothing more.
  const withSpot = [...fill(9), {spot: 'frensham', date: DAY}];
  assert.deepEqual(O.outingAsk(withSpot, pairs), {on: [pairs[0]], add: [], left: [pairs[1]]});
  // The list sent never passes the cap.
  assert.equal(O.outingList(fill(9), nine.add, true).length, 10);
});

// ------------------------------------------------------------------------------ what the tile says
test('alerts on: what is stored, that it is forgotten after the day, and a way to stop it', () => {
  const ask = O.outingAlert({state: 'on', pairs, list: []});
  assert.ok(ask.includes('A notification each time tomorrow\'s level or official notice changes at Frensham Great Pond and River Wey at Waverley.'));
  assert.ok(ask.indexOf('What asking sends') < ask.indexOf('Alert me about this outing'));   // consent before the button
  assert.ok(ask.includes('not the time, where you start from or the rest of the plan'));
  assert.ok(ask.includes('up to 10 in all, and forgets each one after its date'));
  assert.ok(ask.includes('<a href="privacy.html">Privacy notice</a>'));
  assert.ok(!ask.includes('data-outing-alert="stop"'));
  const on = O.outingAlert({state: 'on', pairs, list: [{spot: 'frensham', date: DAY}, {spot: 'wey', date: DAY}]});
  assert.ok(on.includes('<b>Alerts are on for this outing.</b>'));
  assert.ok(on.includes('Stored by SwimSignal\'s alert service: this browser\'s push address, with Frensham Great Pond and River Wey at Waverley on Sunday 1 November. Each is forgotten after that day.'));
  assert.ok(on.includes('data-outing-alert="stop">Stop alerts for this outing') && !on.includes('data-outing-alert="add"'));
  // The backup added after the spot was asked for: the spot is on, the backup can be added, both can be stopped.
  const half = O.outingAlert({state: 'on', pairs, list: [{spot: 'frensham', date: DAY}]});
  assert.ok(half.includes('<b>Alerts are on for Frensham Great Pond.</b>') && half.includes('It is forgotten after that day.'));
  assert.ok(half.includes('data-outing-alert="add">Alert me about River Wey at Waverley') && half.includes('data-outing-alert="stop"'));
});

test('at the cap: the backup left out, or nothing added, said plainly', () => {
  const nine = O.outingAlert({state: 'on', pairs, list: fill(9)});
  assert.ok(nine.includes('data-outing-alert="add">Alert me about Frensham Great Pond<'));
  assert.ok(nine.includes('Alerts can cover 10 dates at most, so River Wey at Waverley is left out.'));
  const ten = O.outingAlert({state: 'on', pairs, list: fill(10)});
  assert.ok(ten.includes('You have alerts for 10 dates, the most there can be. Stop one of them to add this outing.'));
  assert.ok(!ten.includes('<button'));
});

test('no push here: said plainly, with the calendar file instead; alerts off: the Saved page', () => {
  for (const [state, words] of [['cannot', 'This browser cannot show notifications from websites'], ['ios', 'notifications work only in the Home Screen app'],
    ['inapp', 'Alerts cannot be turned on in the Facebook app\'s browser'], ['blocked', 'Notifications are blocked for this site']]) {
    const h = O.outingAlert({state, pairs, list: [], app: 'Facebook'});
    assert.ok(h.includes(words), state);
    assert.ok(h.includes('Add it to your calendar instead.'), state);
    assert.ok(!h.includes('<button'), state);
  }
  assert.match(O.outingAlert({state: 'off', pairs, list: [], saved: '/saved/'}), /first turn on alerts in this browser, on the <a href="\/saved\/" id="outing-to-alerts">Saved page<\/a>/);
  assert.equal(O.outingAlert({state: 'none', pairs, list: []}), '');   // the site's date alerts are off: nothing said
  // The calendar file is offered whatever the alerts can do, once a spot is chosen.
  const tile = O.outingSection({day: DAY, when: 'morning', spot: 'frensham', groups: [], backupGroups: [], missing: [], issued: 'x', open: true,
    main: {id: 'frensham', name: 'Frensham Great Pond', href: 'spot/frensham/', tone: 'low', headline: 'Low risk'}, alt: null});
  assert.ok(tile.includes('id="outing-ics">Add to calendar</button>') && tile.includes('id="outing-alert"'));
  assert.ok(!O.outingSection({day: DAY, groups: [], backupGroups: [], missing: [], issued: 'x', open: true, main: null, alt: null}).includes('outing-ics'));
  // The tile's opening line says the outing is sent only if alerts are asked for, and only where they can be.
  assert.ok(tile.includes('Kept in this browser and in this plan\'s link; sent nowhere.</p>'));
  assert.ok(O.outingSection({day: DAY, groups: [], backupGroups: [], missing: [], issued: 'x', open: true, main: null, alt: null, dateAlerts: true})
    .includes('sent nowhere unless you ask for alerts about it.</p>'));
});

test('an earlier choice still on is named and can be stopped; names are escaped', () => {
  const asked = [{spot: 'wey', date: '2026-10-31'}, {spot: 'frensham', date: DAY}];
  const list = [{spot: 'wey', date: '2026-10-31'}, {spot: 'frensham', date: DAY}];
  const earlier = O.outingEarlier(asked, list, pairs);
  assert.deepEqual(earlier, [{spot: 'wey', date: '2026-10-31'}]);
  assert.deepEqual(O.outingEarlier(asked, [{spot: 'frensham', date: DAY}], pairs), []);   // stopped elsewhere: nothing to say
  const h = O.outingAlert({state: 'on', pairs, list, earlier: [{...earlier[0], name: 'Wey <b>'}]});
  assert.ok(h.includes('Alerts are still on from an earlier choice for this outing: Wey &lt;b&gt; on Saturday 31 October.'));
  assert.ok(h.includes('data-outing-alert="earlier">Stop those'));
  const odd = O.outingAlert({state: 'on', pairs: [{spot: 'x', date: DAY, name: '<img src=x onerror=alert(1)>'}], list: []});
  assert.ok(!odd.includes('<img') && odd.includes('&lt;img src=x onerror=alert(1)&gt;'));
});

// ------------------------------------------------------------------------------ the calendar file
function unfold(text) {
  assert.ok(text.endsWith('\r\n') && !/\r(?!\n)|(?<!\r)\n/.test(text), 'CRLF line ends');
  for (const line of text.slice(0, -2).split('\r\n')) assert.ok(Buffer.byteLength(line, 'utf8') <= 75, `over 75 octets: ${line}`);
  const props = {};
  for (const line of text.slice(0, -2).replace(/\r\n /g, '').split('\r\n')) {
    const m = /^([A-Z-]+)((?:;[A-Z-]+=[^:;]+)*):(.*)$/.exec(line); assert.ok(m, line);
    if (m[1] !== 'BEGIN' && m[1] !== 'END') { assert.ok(!(m[1] in props), `${m[1]} twice`); props[m[1]] = {params: m[2], value: m[3]}; }
  }
  return props;
}
const unescape = v => { assert.ok(!/(?<!\\)(?:\\\\)*[;,]/.test(v), `unescaped , or ; in ${v}`); return v.replace(/\\n/g, '\n').replace(/\\([\\;,])/g, '$1'); };
const CAL = {day: DAY, when: 'morning', host: 'swimsignal.co.uk', plan: 'https://swimsignal.co.uk/plan/#day=2026-11-01&from=Farnham&at=51.2,-0.8&within=20&when=morning&spot=frensham&backup=wey',
  main: {id: 'frensham', name: 'Frensham Great Pond', url: 'https://swimsignal.co.uk/spot/frensham/#day=2026-11-01'},
  backup: {name: 'River Wey at Waverley', url: 'https://swimsignal.co.uk/spot/wey/#day=2026-11-01'}};

test('the calendar file, field by field: the time window, the spot, links back, the check, no level', () => {
  const text = O.outingIcs(CAL, Date.parse('2026-10-31T09:30:00Z'));
  const p = unfold(text);
  assert.ok(text.startsWith('BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//SwimSignal//Outing//EN\r\nCALSCALE:GREGORIAN\r\nMETHOD:PUBLISH\r\nBEGIN:VEVENT\r\n'));
  assert.ok(text.endsWith('END:VEVENT\r\nEND:VCALENDAR\r\n'));
  assert.equal(p.UID.value, 'outing-2026-11-01-frensham@swimsignal.co.uk');
  assert.equal(p.DTSTAMP.value, '20261031T093000Z');
  // The swimmer's own time, on the device's clock: a local time, morning 06:00 to 12:00.
  assert.deepEqual([p.DTSTART.value, p.DTEND.value], ['20261101T060000', '20261101T120000']);
  assert.equal(p.SUMMARY.value, 'Swim: Frensham Great Pond');
  assert.equal(p.LOCATION.value, 'Frensham Great Pond');
  assert.equal(p.URL.value, CAL.main.url);
  assert.equal(unescape(p.DESCRIPTION.value), ['Check SwimSignal and any official notice before you go.', `Your spot: Frensham Great Pond, ${CAL.main.url}`,
    `Backup: River Wey at Waverley, ${CAL.backup.url}`, `Your plan: ${CAL.plan}`].join('\n'));
  assert.ok(!('TRANSP' in p));
  // No forecast level anywhere in the event: it would be stale by the time the calendar shows it.
  assert.doesNotMatch(text.replace(/\r\n /g, ''), /\b(low|moderate|high|very high) risk\b|\brisk\b/i);
});

test('the calendar file: an hour, the whole day, no backup, and odd names escaped and folded by octets', () => {
  const hour = unfold(O.outingIcs({...CAL, when: '07'}, 0));
  assert.deepEqual([hour.DTSTART.value, hour.DTEND.value], ['20261101T070000', '20261101T080000']);
  const evening = unfold(O.outingIcs({...CAL, when: 'evening'}, 0));
  assert.deepEqual([evening.DTSTART.value, evening.DTEND.value], ['20261101T170000', '20261101T210000']);
  const day = unfold(O.outingIcs({...CAL, when: undefined, day: '2026-12-31'}, 0));
  assert.deepEqual([day.DTSTART.params, day.DTSTART.value, day.DTEND.value, day.TRANSP.value], [';VALUE=DATE', '20261231', '20270101', 'TRANSPARENT']);
  const solo = unfold(O.outingIcs({...CAL, backup: null}, 0));
  assert.ok(!unescape(solo.DESCRIPTION.value).includes('Backup:'));
  const name = 'Llyn Padarn; café, “north” \\ side 🏊\nnew line';
  const odd = O.outingIcs({...CAL, main: {...CAL.main, name}}, 0), p = unfold(odd);
  assert.equal(unescape(p.SUMMARY.value), `Swim: ${name}`);
  assert.equal(unescape(p.LOCATION.value), name);
  assert.ok(!odd.includes('�'));
});

test('the organisers\' file is made by the same helper and reads as before', () => {
  const org = read('src/dipcast/site/organisers.js');
  assert.match(org, /return icsCalendar\('-\/\/SwimSignal\/\/Event dates\/\/EN', events\);/);
  assert.doesNotMatch(org, /const octets|BEGIN:VCALENDAR/);   // no second copy of the lines and folding
  assert.equal(Org.icsFold('X:' + 'a'.repeat(80)), SD.icsFold('X:' + 'a'.repeat(80)));
  // The organisers' line-for-line file stays in tests/site_event_week.test.cjs, unchanged by the move.
  assert.match(read('tests/site_event_week.test.cjs'), /assert\.equal\(text, expected\);/);
});

test('the page loads spotdate.js before outing.js and organisers.js, and the offline copy keeps it', () => {
  const page = read('src/dipcast/site/index.html');
  assert.ok(page.indexOf('<script src="spotdate.js"></script>') > 0 && page.indexOf('<script src="spotdate.js"></script>') < page.indexOf('<script src="outing.js"></script>'));
  const org = read('src/dipcast/site/organisers.html');
  assert.ok(org.indexOf('<script src="spotdate.js"></script>') > 0 && org.indexOf('<script src="spotdate.js"></script>') < org.indexOf('<script src="organisers.js"></script>'));
  assert.match(read('src/dipcast/site/sw.js'), /`spotdate\.js\?v=\$\{BUILD\}`/);
});

test('the calendar file carries each spot\'s verified parking and getting-in facts, with the guide\'s date, and nothing else', () => {
  const guide = {checked: '2026-10-28', how: 'desk', facts: [
    {topic: 'parking', status: 'confirmed', text: 'Pay and display parking at Carding Mill Valley (SatNav SY6 6JG).'},
    {topic: 'entry', status: 'confirmed', text: 'Steps down the bank by the dam.'},
    {topic: 'entry', status: 'suggested', text: 'A swimmer says the shallow end is easier.', from: 'Sam', on: '2026-10-20'},
    {topic: 'rules', status: 'confirmed', text: 'The National Trust invites a dip in the reservoir.'}]};
  assert.deepEqual(O.outingPractical({guide}), [
    'Parking, from its guide (checked 2026-10-28): Pay and display parking at Carding Mill Valley (SatNav SY6 6JG).',
    'Getting in, from its guide (checked 2026-10-28): Steps down the bank by the dam.']);
  // No guide, or one with neither topic: nothing, and no made-up meeting point or put-in.
  assert.deepEqual(O.outingPractical({}), []);
  assert.deepEqual(O.outingPractical({guide: {checked: '2026-10-28', facts: [guide.facts[3]]}}), []);
  const p = unfold(O.outingIcs({...CAL, main: {...CAL.main, practical: O.outingPractical({guide})}, backup: {...CAL.backup, practical: []}}, 0));
  assert.equal(unescape(p.DESCRIPTION.value), ['Check SwimSignal and any official notice before you go.', `Your spot: Frensham Great Pond, ${CAL.main.url}`,
    'Parking, from its guide (checked 2026-10-28): Pay and display parking at Carding Mill Valley (SatNav SY6 6JG).',
    'Getting in, from its guide (checked 2026-10-28): Steps down the bank by the dam.',
    `Backup: River Wey at Waverley, ${CAL.backup.url}`, `Your plan: ${CAL.plan}`].join('\n'));
  // The page passes each spot's guide in when it makes the file.
  const src = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/outing.js'), 'utf8');
  assert.match(src, /practical: outingPractical\(pair\.main\)/);
  assert.match(src, /practical: outingPractical\(pair\.backup\)/);
});
