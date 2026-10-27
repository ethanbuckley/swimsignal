// What would change this plan (src/dipcast/site/outingwatch.js): under the outing's two columns, for its
// spot and its backup, the official advice, the level for the outing's day and the river at the gauge, each
// said as it is now and, once a newer forecast is out, whether it has changed since the outing was planned;
// and the note kept in this browser that it compares with.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const L = require('../src/dipcast/site/levels.js');
const E = require('../src/dipcast/site/eatoday.js');
const S = require('../src/dipcast/site/since.js');
const W = require('../src/dipcast/site/outingwatch.js');
L.setToday('2026-10-26');   // a Monday
const DATES = ['2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30'];
const SAT = '2026-10-31';
// Issue times and the device's clock, in local time, so the words do not depend on the zone the tests run in.
const iso = (d, h, m) => new Date(2026, 9, d, h, m).toISOString();
const OLD = iso(26, 7, 0), NEW = iso(26, 21, 40);
const PLANNED = new Date(2026, 9, 26, 7, 5).getTime(), NOW = new Date(2026, 9, 26, 22, 0).getTime();
const RISK = {low: 0.05, moderate: 0.2, high: 0.5, 'very high': 0.8};

// Frensham Great Pond's reviewed notice, as data/advisories/approved.json has it.
const APPROVED = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/advisories/approved.json'), 'utf8')).approvals
  .find(a => a.spot_id === 'bw-ukj2310-11945');
const notice = (line = APPROVED.line) => ({line, publisher: APPROVED.publisher, link: APPROVED.link, since: APPROVED.start, checked: '2026-10-26', state: 'checked'});
// A spot with overflows upstream, at level l on the outing's day (Wednesday 28 Oct), low on the others.
const spot = (id, name, l = 'low', extra = {}) => ({id, name, kind: 'river', source: 'designated', upstream_summary: {overflows: 2}, location: {mode: 'river'},
  now: {label: 'low', risk: 0, discharging_upstream: 0, feed_down_upstream: 0, stale_upstream: 0}, official: [],
  days: DATES.map(date => ({date, label: date === DATES[2] ? l : 'low', risk: RISK[date === DATES[2] ? l : 'low']})), ...extra});
// The River Wey's gauge at Tilford, as spots.json had it on 26 Oct 2026.
const gauge = (label = 'low', extra = {}) => ({station: 'Tilford', river: 'River Wey', level_m: 0.217, typical_low_m: 0.139, typical_high_m: 1.4, label,
  observed_at: new Date(NOW - 36e5).toISOString(), age_hours: 1, stale: false, distance_km: 3, same_river: true, ...extra});
const frensham = (l, official = []) => spot('bw-ukj2310-11945', 'Frensham Great Pond', l, {kind: 'lake', official});
const wey = (l, rs = gauge(), extra = {}) => spot('osm-wey-waverley', 'River Wey, Waverley', l, {river_state: rs, ...extra});
const DAY = DATES[2];
const rec = (s, forecast, at) => W.outingWatchRecord(s, DAY, forecast, at, at);
const lines = (a, b) => W.outingWatchLines(rec(a, OLD, PLANNED), rec(b, NEW, NOW));
const section = (spots, extra = {}) => W.outingWatchSection({day: DAY, today: L.today(), kept: true, forecast: NEW, passed: null, spots, ...extra});
const text = html => html.replace(/<[^>]+>/g, ' ').replace(/&#39;/g, "'").replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();
const planned = S.issuedWords(new Date(PLANNED).toISOString()), issuedOld = S.issuedWords(OLD), issuedNew = S.issuedWords(NEW);

// ------------------------------------------------------------------------------ each thing
test('nothing changed: each thing as it is, "No change since then", and the forecast pair', () => {
  const r = lines(wey('low'), wey('low'));
  assert.equal(r.compared, true);
  assert.equal(r.changed, 0);
  assert.deepEqual(r.lines, ['Official advice: none shown. No change since then.', 'Level for Wednesday: low risk. No change since then.',
    'River at the gauge at Tilford: low water. No change since then.']);
  const h = text(section([{name: 'River Wey, Waverley', role: 'your spot', was: rec(wey('low'), OLD, PLANNED), now: rec(wey('low'), NEW, NOW)}]));
  assert.ok(h.startsWith('What would change this plan Nothing has changed since you planned this outing.'), h);
  assert.ok(h.includes(`River Wey, Waverley , your spot, planned ${planned}`), h);
  assert.ok(h.includes(`Checked against the forecast issued ${issuedNew}; you planned against the one issued ${issuedOld}.`), h);
  assert.ok(h.includes('The river is a separate hazard, not part of the pollution level.'), h);
});

test('a new forecast that moved the day\'s level: what it was and what it is, with its noun', () => {
  const r = lines(wey('low'), wey('moderate'));
  assert.equal(r.changed, 1);
  assert.equal(r.lines[1], 'Level for Wednesday: moderate risk. Changed: was low risk.');
  const h = text(section([{name: 'Wey', role: 'your spot', was: rec(wey('low'), OLD, PLANNED), now: rec(wey('very high'), NEW, NOW)}]));
  assert.ok(h.includes('1 thing has changed since you planned this outing.'), h);
  assert.ok(h.includes('Level for Wednesday: very high risk. Changed: was low risk.'), h);
  // Never a bare level word, never "safe", "clean" or "clear".
  assert.doesNotMatch(h, /\b(low|moderate|high)\b(?! risk| water)/);
  assert.doesNotMatch(h, /\b(safe|clean|clear)\b/i);
});

test('the river at the gauge: rising fast, high water, a stale reading and a gauge gone quiet', () => {
  const rising = gauge('normal', {rise_6h_m: 0.42, rise_from: new Date(NOW - 5 * 36e5).toISOString(), rise_to: new Date(NOW - 36e5).toISOString()});
  assert.equal(lines(wey('low'), wey('low', rising, {flow_state: 'rising fast'})).lines[2], 'River at the gauge at Tilford: rising fast. Changed: was low water.');
  assert.equal(lines(wey('low', gauge('normal')), wey('low', gauge('high'))).lines[2], 'River at the gauge at Tilford: high water. Changed: was usual level.');
  assert.equal(lines(wey('low'), wey('low', gauge('low', {stale: true}))).lines[2], 'River at the gauge at Tilford: no current reading. Changed: was low water.');
  assert.equal(lines(wey('low'), wey('low', null)).lines[2], 'River at the gauge at Tilford: no reading in this update. Changed: was low water.');
  // A rise the build said was fast but whose last reading is over six hours old is not said as rising (flowFacts).
  const old = gauge('normal', {rise_6h_m: 0.42, rise_from: new Date(NOW - 12 * 36e5).toISOString(), rise_to: new Date(NOW - 7 * 36e5).toISOString()});
  assert.equal(lines(wey('low', gauge('normal')), wey('low', old, {flow_state: 'rising fast'})).lines[2], 'River at the gauge at Tilford: usual level. No change since then.');
  // A lake's gauge says where it sits against its usual range, as the Lake level tile does.
  const lake = gauge('normal', {water: 'lake', station: 'Waterhead', level_m: 0.73, typical_low_m: 0.23, typical_high_m: 1.0});
  assert.deepEqual(W.owRiver(wey('low', lake), NOW, NEW), {word: 'in its usual range', gauge: 'Waterhead', lake: true});
  assert.equal(lines(wey('low', lake), wey('low', {...lake, level_m: 1.2})).lines[2], 'Lake at the gauge at Waterhead: above its usual range. Changed: was in its usual range.');
  // No gauge: no river line at all, and no river in the closing words.
  const r = lines(frensham('low'), frensham('low'));
  assert.equal(r.lines.length, 2);
  const h = text(section([{name: 'Frensham Great Pond', role: 'your spot', was: rec(frensham('low'), OLD, PLANNED), now: rec(frensham('low'), NEW, NOW)}]));
  assert.ok(h.includes('look again at the official advice, Wednesday\'s level: both can change'), h);
  assert.doesNotMatch(h, /river/i);
});

// ------------------------------------------------------------------------------ official advice
test('official advice comes first, appears, changes and goes, and is never softened', () => {
  const brief = E.eaTodayBrief(frensham('low', [notice()]));
  const shown = lines(frensham('low'), frensham('low', [notice()]));
  assert.equal(shown.lines[0], `Official advice: ${brief}. Follow it first. Changed: none was shown then.`);
  assert.equal(shown.changed, 1);
  const same = lines(frensham('low', [notice()]), frensham('low', [notice()]));
  assert.equal(same.lines[0], `Official advice: ${brief}. Follow it first. No change since then.`);
  const other = notice('Environment Agency: advice against bathing (pollution incident) since 20 Oct 2026');
  const changed = lines(frensham('low', [notice()]), frensham('low', [other]));
  assert.equal(changed.lines[0], `Official advice: ${E.eaTodayBrief(frensham('low', [other]))}. Follow it first. Changed: was ${brief}.`);
  const gone = lines(frensham('low', [notice()]), frensham('low'));
  assert.equal(gone.lines[0], `Official advice: none shown here now. Changed: was ${brief}. That is not an all-clear: check the Environment Agency's own page before you swim.`);
  // A lower level beside a notice still has the notice first; the level never moves for it.
  const both = lines(frensham('moderate', [notice()]), frensham('low', [notice()]));
  assert.deepEqual(both.lines, [`Official advice: ${brief}. Follow it first. No change since then.`, 'Level for Wednesday: low risk. Changed: was moderate risk.']);
});

test('a page without eatoday.js, or a note from it, compares no official advice and makes none up', () => {
  const a = {...rec(frensham('low'), OLD, PLANNED), official: undefined}, b = {...rec(frensham('low', [notice()]), NEW, NOW)};
  assert.equal(W.outingWatchLines(a, b).lines[0], `Official advice: ${E.eaTodayBrief(frensham('low', [notice()]))}. Follow it first.`);
  const c = W.outingWatchLines(a, {...b, official: undefined});
  assert.equal(c.lines[0], 'Level for Wednesday: low risk. No change since then.');
});

// ------------------------------------------------------------------------------ when nothing is compared
test('the same forecast, as the outing is planned: what each shows now, and that later visits will compare', () => {
  const r = W.outingWatchLines(rec(wey('low'), NEW, NOW), rec(wey('low'), NEW, NOW));
  assert.equal(r.compared, false);
  assert.deepEqual(r.lines, ['Official advice: none shown.', 'Level for Wednesday: low risk.', 'River at the gauge at Tilford: low water.']);
  const h = text(section([{name: 'Wey', role: 'your spot', was: null, now: rec(wey('low'), NEW, NOW)}]));
  assert.ok(h.includes('This browser has noted what each shows now. When a newer forecast is issued, this says what has changed.'), h);
  assert.ok(h.includes(`Checked against the forecast issued ${issuedNew}.`), h);
  assert.doesNotMatch(h, /planned against|No change|Changed/);
  // Storage blocked: said, rather than promise a compare that cannot come.
  assert.ok(text(section([{name: 'Wey', role: 'your spot', was: null, now: rec(wey('low'), NEW, NOW)}], {kept: false}))
    .includes('This browser cannot keep a note, so it cannot say later what has changed.'));
});

test('an older forecast on screen than the one planned with (a copy opened offline) compares nothing and says why', () => {
  const h = text(W.outingWatchSection({day: DAY, today: L.today(), kept: true, forecast: OLD, passed: null,
    spots: [{name: 'Wey', role: 'your spot', was: rec(wey('low'), NEW, NOW), now: rec(wey('high'), OLD, NOW)}]}));
  assert.ok(h.includes(`This copy shows the forecast issued ${issuedOld}, older than the one you planned against (${issuedNew}), so nothing is compared.`), h);
  assert.doesNotMatch(h, /Changed|No change|things? ha(s|ve) changed/);
});

test('no forecast for the day yet: said as that, never as a level, and compared honestly', () => {
  const short = l => wey(l, gauge(), {days: DATES.slice(0, 2).map(date => ({date, label: 'low', risk: 0.05}))});   // no row for Wednesday
  assert.equal(L.dayLevel(short('low'), DAY), L.NO_FORECAST);
  const none = W.outingWatchLines(rec(short('low'), OLD, PLANNED), rec(short('low'), NEW, NOW));
  assert.equal(none.lines[1], 'Level for Wednesday: no forecast for Wednesday in this update. No change since then.');
  assert.equal(lines(short('low'), wey('high')).lines[1], 'Level for Wednesday: high risk. Changed: was no forecast for Wednesday in this update.');
  assert.equal(lines(wey('low'), short('low')).lines[1], 'Level for Wednesday: no forecast for Wednesday in this update. Changed: was low risk.');
  const nodata = wey('low', gauge(), {days: DATES.map(date => ({date, label: null, risk: null}))});   // a row with no data
  assert.equal(L.dayLevel(nodata, DAY), L.NO_FORECAST);
  const h = text(section([{name: 'River Wey, Waverley', role: 'your spot', was: null, now: rec(short('low'), NEW, NOW)}]));
  assert.ok(h.includes('This update has no forecast for Wednesday at River Wey, Waverley: look again before you go.'), h);
});

test('a spot with no daily forecast keeps its own level words, with no "risk" stuck on', () => {
  const plain = {...frensham('low'), upstream_summary: {overflows: 0}, location: {mode: 'lake'}};
  assert.equal(W.outingWatchLines(rec(plain, OLD, PLANNED), rec(plain, NEW, NOW)).lines[1], 'Level for Wednesday: no monitored overflow found upstream. No change since then.');
  assert.equal(W.owLevel(L.NOT_COVERED, DAY), 'not covered by the forecast');
});

// ------------------------------------------------------------------------------ the day and the backup
test('the outing\'s day has passed: a plain line, and the same spots followed from now', () => {
  const h = text(section([{name: 'Wey', role: 'your spot', was: null, now: rec(wey('low'), NEW, NOW)}], {passed: '2026-10-24'}));
  assert.ok(h.includes('Your outing on Saturday 24 October has passed. It now follows the same spots for Wednesday.'), h);
  assert.doesNotMatch(h, /Changed|No change/);
  // A plan whose own day is behind today (a page left open): one plain line, nothing compared.
  const past = text(W.outingWatchSection({day: '2026-10-25', today: L.today(), kept: true, forecast: NEW, passed: null,
    spots: [{name: 'Wey', role: 'your spot', was: rec(wey('low'), OLD, PLANNED), now: rec(wey('high'), NEW, NOW)}]}));
  assert.equal(past, "What would change this plan This outing's day has passed, so nothing is compared with it.");
});

test('before the day: what to look at again before leaving, in the day\'s own words', () => {
  const one = d => text(W.outingWatchSection({day: d, today: L.today(), kept: true, forecast: NEW, passed: null,
    spots: [{name: 'Wey', role: 'your spot', was: null, now: W.outingWatchRecord(wey('low'), d, NEW, NOW, NOW)}]}));
  assert.ok(one(DATES[0]).includes("Before you leave, look again at the official advice, today's level and the river: each can change, and a newer forecast may be issued. Then check the signs at the water."));
  assert.ok(one(DATES[1]).includes("Before you leave tomorrow, look again at the official advice, tomorrow's level and the river"));
  assert.ok(one(DAY).includes("Before you leave on Wednesday, look again at the official advice, Wednesday's level and the river"));
});

test('the spot and the backup each get their own list; no backup, only the spot', () => {
  const two = section([{name: 'Frensham Great Pond', role: 'your spot', was: rec(frensham('low'), OLD, PLANNED), now: rec(frensham('moderate'), NEW, NOW)},
    {name: 'River Wey, Waverley', role: 'your backup', was: rec(wey('low'), OLD, PLANNED), now: rec(wey('low', gauge('high')), NEW, NOW)}]);
  assert.equal((two.match(/<ul class="outing-watch-list">/g) || []).length, 2);
  assert.ok(text(two).includes('2 things have changed since you planned this outing.'));
  assert.ok(two.indexOf('your spot') < two.indexOf('your backup'));
  const one = section([{name: 'Frensham Great Pond', role: 'your spot', was: null, now: rec(frensham('low'), NEW, NOW)}]);
  assert.equal((one.match(/<ul/g) || []).length, 1);
  assert.doesNotMatch(one, /backup/);
  assert.equal(section([]), '');
});

test('names, notices and gauges are data: escaped', () => {
  const bad = '<img src=x onerror=alert(1)>&"\'';
  const s = wey('low', gauge('low', {station: bad}), {name: bad, official: [notice(`Environment Agency: advice against bathing ${bad}`)]});
  const h = section([{name: bad, role: 'your spot', was: rec(s, OLD, PLANNED), now: rec(s, NEW, NOW)}]);
  assert.doesNotMatch(h, /<img/);
  assert.ok(h.includes('&lt;img src=x onerror=alert(1)&gt;&amp;&quot;&#39;'));
});

// ------------------------------------------------------------------------------ the note
test('the note: a spot keeps what it showed when planned; a new spot, backup or day is noted afresh', () => {
  const a = wey('low'), b = frensham('low');
  const first = W.outingWatchNote(null, {day: DAY}, {main: a, backup: null}, OLD, PLANNED);
  assert.deepEqual(first.items.map(r => [r.id, r.forecast, r.at]), [[a.id, OLD, PLANNED]]);
  // A later visit, same outing: the note is unchanged, so the compare stays against the plan.
  const again = W.outingWatchNote(first, {day: DAY}, {main: wey('high'), backup: null}, NEW, NOW);
  assert.deepEqual(again, first);
  // A backup added: the spot keeps its note, the backup is noted now.
  const backed = W.outingWatchNote(first, {day: DAY}, {main: a, backup: b}, NEW, NOW);
  assert.deepEqual(backed.items.map(r => [r.id, r.at]), [[a.id, PLANNED], [b.id, NOW]]);
  // Spot and backup swapped: each keeps its own note.
  assert.deepEqual(W.outingWatchNote(backed, {day: DAY}, {main: b, backup: a}, NEW, NOW + 1).items.map(r => [r.id, r.at]), [[b.id, NOW], [a.id, PLANNED]]);
  // Another day: noted afresh. No spot: nothing kept.
  assert.deepEqual(W.outingWatchNote(backed, {day: DATES[3]}, {main: a, backup: b}, NEW, NOW + 2).items.map(r => r.at), [NOW + 2, NOW + 2]);
  assert.equal(W.outingWatchNote(backed, {day: DAY}, {main: null, backup: null}, NEW, NOW), null);
});

test('the note read back: what this file writes, and anything else as no note', () => {
  const n = W.outingWatchNote(null, {day: DAY}, {main: frensham('low', [notice()]), backup: wey('low')}, OLD, PLANNED);
  assert.deepEqual(W.outingWatchRead(JSON.stringify(n)), n);
  for (const bad of [null, '', 'not json', '[]', '{"day":"x","items":[]}', JSON.stringify({day: DAY, items: [{id: 'a'}]}),
    JSON.stringify({...n, items: n.items.map(r => ({...r, level: 'fine'}))}), JSON.stringify({...n, items: n.items.map(r => ({...r, day: DATES[0]}))}),
    JSON.stringify({...n, items: n.items.map(r => ({...r, river: {word: 'x'.repeat(61), gauge: 'g', lake: false}}))})]) {
    assert.equal(W.outingWatchRead(bad), null, String(bad));
  }
});

test('in the page: noted in this browser, drawn under the two columns, and removed with the spot', () => {
  const store = new Map();
  global.localStorage = {getItem: k => store.has(k) ? store.get(k) : null, setItem: (k, v) => store.set(k, String(v)), removeItem: k => store.delete(k)};
  let drawn = '';
  const tile = {querySelector: q => q === '.outing-pair' ? {insertAdjacentHTML: (where, h) => { assert.equal(where, 'afterend'); drawn = h; }} : null};
  try {
    W.outingWatchDraw(tile, {day: DAY}, {main: wey('low'), backup: null}, OLD, PLANNED);
    assert.equal(JSON.parse(store.get(W.OUTING_WATCH_KEY)).items[0].forecast, OLD);
    assert.match(text(drawn), /This browser has noted what each shows now/);
    W.outingWatchDraw(tile, {day: DAY}, {main: wey('moderate'), backup: null}, NEW, NOW);
    assert.match(text(drawn), /Level for Wednesday: moderate risk\. Changed: was low risk\./);
    assert.equal(JSON.parse(store.get(W.OUTING_WATCH_KEY)).items[0].forecast, OLD);   // still the plan's
    drawn = '';
    W.outingWatchDraw({querySelector: () => null}, {day: DAY}, {main: null, backup: null}, NEW, NOW);
    assert.equal(store.has(W.OUTING_WATCH_KEY), false);
    assert.equal(drawn, '');
    // Storage that throws: still drawn, and says it cannot keep the note.
    global.localStorage = {getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); }, removeItem: () => {}};
    W.outingWatchDraw(tile, {day: DAY}, {main: wey('low'), backup: null}, NEW, NOW);
    assert.match(text(drawn), /cannot keep a note/);
  } finally { delete global.localStorage; }
});

test('in the page: an earlier outing\'s day that has passed is said on every draw of the visit, though its note is replaced', () => {
  const file = require.resolve('../src/dipcast/site/outingwatch.js');
  delete require.cache[file];
  const V = require(file);   // a page just opened: nothing read yet
  const store = new Map([[V.OUTING_WATCH_KEY, JSON.stringify(V.outingWatchNote(null, {day: '2026-10-24'}, {main: wey('low'), backup: null}, OLD, PLANNED))]]);
  global.localStorage = {getItem: k => store.has(k) ? store.get(k) : null, setItem: (k, v) => store.set(k, String(v)), removeItem: k => store.delete(k)};
  let drawn = '';
  const tile = {querySelector: () => ({insertAdjacentHTML: (where, h) => { drawn = h; }})};
  try {
    for (let i = 0; i < 2; i++) {
      V.outingWatchDraw(tile, {day: DAY}, {main: wey('low'), backup: null}, NEW, NOW);
      assert.match(text(drawn), /Your outing on Saturday 24 October has passed\. It now follows the same spots for Wednesday\./, `draw ${i}`);
    }
    assert.equal(JSON.parse(store.get(V.OUTING_WATCH_KEY)).day, DAY);
  } finally { delete global.localStorage; delete require.cache[file]; }
});

// ------------------------------------------------------------------------------ the page's wiring
test('the page loads outingwatch.js, the outing calls it once, and the offline copy keeps it', () => {
  const read = p => fs.readFileSync(path.join(__dirname, '..', p), 'utf8');
  const page = read('src/dipcast/site/index.html');
  assert.ok(page.indexOf('<script src="since.js">') < page.indexOf('<script src="outingwatch.js">'));
  assert.equal((read('src/dipcast/site/outing.js').match(/outingWatchDraw\(/g) || []).length, 1);
  assert.match(read('src/dipcast/site/sw.js'), /`outingwatch\.js\?v=\$\{BUILD\}`/);
  // Nothing is fetched: no network call in the file.
  assert.doesNotMatch(read('src/dipcast/site/outingwatch.js'), /fetch\(|XMLHttpRequest|sendBeacon/);
});
