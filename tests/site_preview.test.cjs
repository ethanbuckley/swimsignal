// The redesign preview (src/dipcast/site/preview/; docs/DESIGN.md, "A redesign kept as a preview"). Its composition is
// its own; what it says is not. These hold the rules that are about truth: the level is levels.js's own, the modelled
// score and the missing coverage are kept apart from it, an official notice comes first, "No monitored overflow found
// upstream" is never low, one date runs through the whole page, and nothing is called safe or clean.
//   node --test tests/site_preview.test.cjs
process.env.TZ = 'Europe/London';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const SITE = path.join(__dirname, '../src/dipcast/site');
const L = require(path.join(SITE, 'levels.js')), EA = require(path.join(SITE, 'eatoday.js'));
Object.assign(globalThis, L, EA);   // in the page the two files' names are globals; model.js uses only what they export
const M = require(path.join(SITE, 'preview/model.js'));
const read = f => fs.readFileSync(path.join(SITE, 'preview', f), 'utf8');
const PAGE = read('index.html'), JS = read('app.js'), MODEL = read('model.js'), CSS = read('preview.css');

const GEN = '2026-11-24T13:21:00+00:00', NOW = Date.parse('2026-11-24T14:00:00Z');
const DAYS = ['2026-11-24', '2026-11-25', '2026-11-26', '2026-11-27', '2026-11-28'], SAT = DAYS[4];
const RISK = {low: 0.05, moderate: 0.2, high: 0.5, 'very high': 0.8};
const spot = (labels, extra = {}) => ({id: 'a', name: 'River Aire, Somewhere', kind: 'river', river: 'River Aire', area: 'Yorkshire', source: 'curated',
  lat: 53.9, lon: -1.8, upstream_summary: {overflows: 10}, location: {mode: 'river'}, assumptions: {max_upstream_km: 60, recent_spill_hours: 48},
  now: {label: 'low', risk: 0.02, discharging_upstream: 0, recent_upstream: 0, monitored_upstream: 8},
  days: labels.map((l, i) => ({date: DAYS[i], label: l, risk: l ? RISK[l] : null, rain_48h_mm: l ? 4 : null, expected_spilling_overflows: l ? 0.2 : null, in_validated_season: false})),
  weather: {days: DAYS.map(d => ({date: d, tmax: 7, sunrise: '07:43', sunset: '16:01', wind_kmh: 15, gust_kmh: 33}))}, ...extra});
const tarn = extra => spot([], {id: 'tarn', name: 'A Tarn', kind: 'lake', river: '', upstream_summary: {overflows: 0}, days: [],
  error: 'An isolated lake: the river network links no monitored storm overflow to it, so the forecast has nothing to say about it.', ...extra});
const NOTICE = [{line: 'Environment Agency: advice against bathing (harmful algae) since 19 Jun 2026', publisher: 'Environment Agency',
  link: 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj2310-11945', since: '2026-06-19', checked: '2026-10-26', state: 'stale', restricts: true}];
const data = (spots, now = NOW) => M.prepare({generated_at: GEN, build: {live_feeds: {polled_at: '2026-11-24 13:15:08.440499+00:00'}}, spots}, now);
const ALL = ['moderate', 'moderate', 'low', 'high', 'moderate'];

test('the page is out of search engines, shares only the rules, and keeps the live look', () => {
  assert.match(PAGE, /<meta name="robots" content="noindex, nofollow">/);
  assert.deepEqual([...PAGE.matchAll(/<script src="([^"]+)"/g)].map(m => m[1]), ['../levels.js', '../eatoday.js', 'model.js', 'app.js']);
  assert.doesNotMatch(CSS, /text-transform:\s*uppercase|linear-gradient|border-radius:\s*(?:999|[1-9]\d)px|letter-spacing:\s*0?\.\d+em/);   // the looks Ethan named as machine-made
  assert.match(CSS, /"Source Serif 4"/); assert.match(CSS, /--bar: #3d5b5d/); assert.match(CSS, /--radius: 8px/);
  const sizes = new Set([...CSS.matchAll(/font(?:-size)?:[^;]*?(\d+)px/g)].map(m => m[1]));
  assert.deepEqual([...sizes], [], 'every font size is one of the six tokens');
});

test('nothing is called safe or clean, and no em-dash is written', () => {
  for (const [name, text] of [['index.html', PAGE], ['app.js', JS], ['model.js', MODEL], ['preview.css', CSS]]) {
    assert.doesNotMatch(text.replace(/env\(safe-area-inset-top\)/g, ''), /\b(safe|clean|safely|cleaner)\b/i, name);
    assert.doesNotMatch(text, /—/, name);
  }
  assert.match(JS, /not a safety check/);
});

test('one date runs through the answer, the ledger, the line upstream and the places elsewhere', () => {
  const s = spot(ALL), other = spot(['low', 'low', 'low', 'low', 'low'], {id: 'b', name: 'River Aire, Upstream', lat: 53.95}), d = data([s, other]);
  const a = M.answer(s, SAT, d, NOW);
  assert.equal(a.dateLabel, 'Saturday 28 November');
  assert.equal(a.head, 'Moderate risk from sewage spills');
  assert.equal(a.conditions[0].k, 'Rain');
  assert.equal(M.answer(s, DAYS[0], d, NOW).dateLabel, 'Today, Tuesday 24 November');
  const led = M.ledger(s, SAT, d, NOW);
  assert.equal(led[0].label, 'Level on Saturday');
  assert.ok(led.find(r => r.key === 'spill').week.find(w => w.on).date === SAT);
  assert.match(led.find(r => r.key === 'cover').lines.join(' '), /readings from now\. Saturday's level comes from the rain forecast/);
  const line = M.riverLine(s, [{site_id: 'X1', site_name: 'SOMEWHERE/CSO', company: 'Yorkshire Water', distance_km: 2, status: 0, data_state: 'live', feed_updated_at: '2026-11-24T12:48:37+00:00', p_spill_days: [0.5, 0.4, 0.3, 0.2, 0.1]}], null, [s, other], NOW, SAT);
  assert.equal(line.items[0].chance, 0.1, "the overflow's chance is Saturday's, not today's");
  assert.equal(M.elsewhere([s, other], s, SAT, 20, s.id, 'moderate').low[0].week.find(w => w.on).date, SAT);
  assert.equal(M.dayTabs(s, d).map(t => t.short).join(' '), 'Moderate Moderate Low High Moderate');
});

test('the level, the modelled score and the missing coverage are three things', () => {
  const poor = spot(ALL, {classification: {class: 'poor', year: 2025}}), d = data([poor]);
  const a = M.answer(poor, SAT, d, NOW), led = M.ledger(poor, SAT, d, NOW), by = k => led.find(r => r.key === k);
  assert.equal(a.head, 'High risk');
  assert.deepEqual(a.why, ['Rated poor, so every day here is at least high risk.']);
  assert.equal(a.act, L.POOR_ACTION);
  assert.equal(by('level').value, 'High risk');
  assert.match(by('level').lines[0], /^Set by the Environment Agency's rating: poor for 2025/);
  assert.equal(by('spill').value, '20 of 100'); assert.equal(by('spill').word, 'moderate');
  assert.match(by('spill').lines[0], /^On its own: moderate risk\. The poor rating raises the level to high risk\./);
  assert.match(by('spill').lines.join(' '), /Not a probability\./);
  assert.equal(by('cover').value, '8 of 10 report');
  assert.match(by('cover').lines[0], /None spilling at the last poll \(Tue 13:15\)\. 2 do not report, so could be spilling unseen\./);
  assert.equal(M.dayTabs(poor, d).map(t => t.short).join(' '), 'High High High High High');
  assert.deepEqual(by('spill').week.map(w => w.score), [20, 20, 5, 50, 20], 'the days still differ in the score');
});

test('a place with no daily forecast is its own answer, never low, and still follows the day', () => {
  const t = tarn(), s = spot(ALL), d = data([s, t]), a = M.answer(t, SAT, d, NOW);
  assert.equal(a.head, L.COVER[L.NO_RIVER]); assert.equal(a.cls, 'lv-clear'); assert.ok(a.everyDay);
  assert.equal(a.dateLabel, 'Saturday 28 November');
  assert.ok(a.notes.includes(L.OTHER_RISKS));
  assert.deepEqual(M.dayTabs(t, d).map(x => x.short), ['', '', '', '', ''], 'its tabs carry the days, not a level');
  assert.match(M.ledger(t, SAT, d, NOW)[0].lines[0], /^Not a low level/);
  const E = M.elsewhere([s, t], s, SAT, 20, s.id, 'moderate');
  assert.deepEqual(E.low, []); assert.equal(E.plain[0].id, 'tarn');
  assert.deepEqual(M.nextSteps(t, SAT, [s, t]), [], 'nothing to steer away from');
});

test('official advice comes first, is kept apart from the level and is never listed as low', () => {
  const adv = spot(['low', 'low', 'low', 'low', 'low'], {id: 'adv', official: NOTICE}), ok = spot(['low', 'low', 'low', 'low', 'low'], {id: 'ok', lat: 53.95}), d = data([adv, ok]);
  const o = M.official(adv), a = M.answer(adv, SAT, d, NOW);
  assert.equal(o.title, 'Official advice'); assert.ok(o.restricts);
  assert.equal(a.act, 'Follow the official advice above first.');
  assert.equal(a.apart, "This level is SwimSignal's forecast. The official advice above is separate.");
  assert.equal(M.lowerDay(adv, SAT), null);
  const E = M.elsewhere([adv, ok], ok, SAT, 20, 'ok', 'low');
  assert.deepEqual(E.low, []); assert.equal(E.advice[0].id, 'adv');
  assert.deepEqual(M.nextSteps(adv, SAT, [adv, ok]).map(x => x.label), ['One place at low risk nearby']);
  assert.ok(JS.indexOf('officialHtml(o)') < JS.indexOf("dayTabsHtml(P.dayTabs(s, DATA)"), 'drawn before the days and the level');
});

test('a lower place is low, or moderate seen from high; a place at high risk is never offered', () => {
  const here = spot(['high', 'high', 'high', 'high', 'high'], {id: 'here'}), low = spot(['low', 'low', 'low', 'low', 'low'], {id: 'low', lat: 53.92}),
    mod = spot(ALL, {id: 'mod', lat: 53.94}), high = spot(['high', 'high', 'high', 'high', 'high'], {id: 'high', lat: 53.96}), all = [here, low, mod, high];
  data(all);
  const E = M.elsewhere(all, here, SAT, 20, 'here', 'high');
  assert.deepEqual([E.low.map(r => r.id), E.moderate.map(r => r.id), E.folded.map(r => r.id), E.lowerThan], [['low'], ['mod'], ['high'], true]);
  assert.equal(M.nextSteps(here, SAT, all)[0].label, '2 lower-risk places nearby');
  const fromMod = M.elsewhere(all, mod, SAT, 20, 'mod', 'moderate');
  assert.equal(fromMod.lowerThan, false); assert.deepEqual(fromMod.folded.map(r => r.id).sort(), ['here', 'high']);
  assert.deepEqual(M.nextSteps(mod, SAT, all).map(x => x.kind), ['nearby', 'day']);
  assert.deepEqual(M.lowerDay(mod, SAT), {date: DAYS[2], level: 'low'});
  assert.deepEqual(M.nextSteps(low, SAT, all), [], 'a low day has nothing to steer away from');
  assert.equal(M.nextSteps(here, SAT, [here, high]).at(-1).kind, 'nearby-none');
});

test('an old forecast is said to be old, and old feeds stop counting as live', () => {
  const late = Date.parse('2026-11-24T22:40:00Z');
  const s = spot(ALL, {now: {label: 'low', risk: 0.02, discharging_upstream: 0, recent_upstream: 0, monitored_upstream: 10,
    quiet_by_feed: [{company: 'Yorkshire Water', overflows: 10, updated_at: '2026-11-24T12:48:37+00:00'}]}}), d = data([s], late);
  const i = M.issuedWords(d, late);
  assert.ok(i.stale); assert.match(i.note, /^This forecast is 9 h old, older than usual\./);
  assert.equal(M.issuedWords(d, NOW).stale, false); assert.equal(M.issuedWords(d, NOW).text, 'Issued 13:21, 39 min ago');
  assert.equal(M.answer(s, DAYS[0], d, late).lead, L.LIVE_NONE);
  assert.equal(M.ledger(s, DAYS[0], d, late).find(r => r.key === 'cover').value, 'No live reading');
});

test('a shared link keeps its day, and a day that has passed falls back to today', () => {
  assert.deepEqual(M.parseQuery('?spot=bw-uke4100-08901&day=2026-11-28'), {screen: 'place', id: 'bw-uke4100-08901', day: SAT});
  assert.deepEqual(M.parseQuery('?spot=<script>'), {screen: 'find', day: null, q: '', area: ''});
  data([spot(ALL)]);
  assert.equal(M.queryFor({id: 'a', day: SAT}), '?spot=a&day=2026-11-28');
  assert.equal(M.queryFor({id: 'a', day: DAYS[0]}), '?spot=a', "today's link carries no date, so it never goes out of date");
  assert.equal(M.queryFor({day: DAYS[0]}), './');
  assert.match(JS, /This link was for \$\{esc\(P\.longDate\(route\.day\)\)\}/);
});

test("a river's places run from the top down only where each leads to the next", () => {
  const mk = (id, down) => spot(ALL, {id, name: 'River Aire, ' + id, downstream: down});
  const ws = M.waters([mk('c', []), mk('a', [['b', 5], ['c', 12]]), mk('b', [['c', 7]])], SAT);
  assert.deepEqual(ws[0].rows.map(r => r.id), ['a', 'b', 'c']); assert.ok(ws[0].ordered);
  assert.equal(M.waters([mk('a', [['b', 5]]), mk('b', []), mk('z', [])], SAT)[0].ordered, false);
});

test('search finds a place by name, river or area, and reads a postcode as its sector', () => {
  const s = spot(ALL), all = [s, tarn()];
  assert.deepEqual(M.findSpots(all, 'aire some').map(p => p.id), ['a']);
  assert.deepEqual(M.findSpots(all, 'yorkshire').length, 2);
  assert.deepEqual(M.postcodeKeys('ls29 9bz'), {district: 'LS29', sector: 'LS29 9'});
  assert.equal(M.postcodeKeys('Ilkley'), null);
});
