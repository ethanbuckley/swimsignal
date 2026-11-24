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
const PLAN = require(path.join(SITE, 'plan.js')), LISTS = require(path.join(SITE, 'lists.js'));   // the live site's own rules, which the page calls
const read = f => fs.readFileSync(path.join(SITE, 'preview', f), 'utf8');
const PAGE = read('index.html'), JS = read('app.js'), MODEL = read('model.js'), CSS = read('preview.css'), MAP = read('map.js'), ALERTS = read('alerts.js');
const LIVE = fs.readFileSync(path.join(SITE, 'index.html'), 'utf8');

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
  assert.deepEqual([...PAGE.matchAll(/<script src="([^"]+)"/g)].map(m => m[1]),
    ['../levels.js', '../eatoday.js', '../experience.js', '../lists.js', '../plan.js', 'model.js', 'alerts.js', 'map.js', 'app.js']);
  assert.doesNotMatch(CSS, /text-transform:\s*uppercase|linear-gradient|border-radius:\s*(?:999|[1-9]\d)px|letter-spacing:\s*0?\.\d+em/);   // the looks Ethan named as machine-made
  assert.match(CSS, /"Source Serif 4"/); assert.match(CSS, /--bar: #3d5b5d/); assert.match(CSS, /--radius: 8px/);
  const sizes = new Set([...CSS.matchAll(/font(?:-size)?:[^;]*?(\d+)px/g)].map(m => m[1]));
  assert.deepEqual([...sizes], [], 'every font size is one of the six tokens');
});

test('nothing in the scripts stops an older iPhone', () => {
  for (const [name, text] of [['app.js', JS], ['model.js', MODEL], ['map.js', MAP], ['alerts.js', ALERTS]]) {
    assert.doesNotMatch(text, /\(\?<[=!]/, `${name}: a lookbehind is refused by Safari before 16.4, and stops the whole script`);
    assert.doesNotMatch(text, /behavior:\s*'instant'/, `${name}: refused by Safari before 15.4`);
    assert.doesNotMatch(text, /\.at\(|structuredClone|\?\?=|\|\|=|&&=/, name);
  }
  assert.match(PAGE, /<link rel="preload" href="\.\.\/data\/spots-lite\.json" as="fetch" crossorigin>/);
});

test('nothing is called safe or clean, and no em-dash is written', () => {
  // One sentence may use the word: the alerts' own, the live page's, which says what no alert does not mean.
  const NOT_CLEAN = 'so no alert does not mean the water is clean';
  assert.ok(LIVE.includes(NOT_CLEAN) && JS.includes(NOT_CLEAN));
  for (const [name, text] of [['index.html', PAGE], ['app.js', JS], ['model.js', MODEL], ['preview.css', CSS], ['map.js', MAP], ['alerts.js', ALERTS]]) {
    assert.doesNotMatch(text.replace(/env\(safe-area-inset-(top|bottom)\)/g, '').replace(NOT_CLEAN, ''), /\b(safe|clean|safely|cleaner)\b/i, name);
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
  assert.deepEqual(M.parseQuery('?spot=<script>'), {screen: 'find', view: '', day: null, q: '', area: ''});
  data([spot(ALL)]);
  assert.equal(M.queryFor({id: 'a', day: SAT}), 'spot/a/?day=2026-11-28');
  assert.equal(M.queryFor({id: 'a', day: DAYS[0]}), 'spot/a/', "today's link carries no date, so it never goes out of date");
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

test('the map, the plan and the saved places each have an address, and a place still comes first', () => {
  assert.deepEqual(M.parseQuery('?view=map&day=2026-11-28'), {screen: 'find', view: 'map', day: SAT, q: '', area: ''});
  assert.equal(M.parseQuery('?view=elsewhere').view, '');
  assert.equal(M.parseQuery('?view=saved&spot=a').screen, 'place');   // a place's link wins
  assert.equal(M.queryFor({view: 'saved', day: SAT}), '?view=saved&day=2026-11-28');
  assert.equal(M.queryFor({view: 'plan'}), '?view=plan');
  assert.equal(M.queryFor({view: 'other'}), './');
  // A plan's choices go after the #, in the live site's own form, so they never reach a server and open there too.
  assert.match(JS, /'\?view=plan' \+ planHash\(/);
  assert.doesNotMatch(JS, /q\.set\('(from|at|within)'/);
});

test('saved places are the live site\'s own lists, in this browser only', () => {
  // The same keys as the live page, so a place saved on one is saved on the other.
  assert.equal(LISTS.LISTS_KEY, 'dipcast.lists');
  assert.match(JS, /readLists\(stored\(LISTS_KEY\), stored\(SAVED_KEY\)\)/); assert.match(JS, /SAVED_KEY = 'dipcast\.saved'/);
  assert.match(LIVE, /const SAVED_KEY = 'dipcast\.saved'/);
  const spots = [spot(ALL, {id: 'a'}), spot(['low', 'low', 'low', 'low', 'low'], {id: 'b', name: 'B'}), spot(['low', 'low', 'low', 'low', 'low'], {id: 'c', name: 'C', official: NOTICE})];
  const S = M.savedRows(spots, ['b', 'gone', 'a', 'c'], DAYS[0]);
  assert.deepEqual(S.rows.map(r => r.id), ['b', 'a', 'c']);   // in the order they were saved
  assert.equal(S.gone, 1);
  assert.equal(S.low, 1, 'a place under official advice is not counted as low');
  assert.equal(M.savedRows(spots, ['a'], SAT).rows[0].level, 'moderate');   // the day shown, not today
});

test('the alerts say what the live page says, and nothing is asked of the browser until they are turned on', () => {
  // Each sentence of what is sent, to whom and how to take it back is the live page's, word for word.
  for (const said of ["Turning alerts on sends your browser\\'s push address and the list of your saved spots, and nothing else about you, to SwimSignal\\'s alert service.",
    "Alerts reach you through your browser maker\\'s push service (Google, Apple, Mozilla or Microsoft), encrypted so it cannot read them.",
    'You can turn them off here at any time, which deletes what the alert service holds. An alert can be late or not come at all, so no alert does not mean the water is clean.',
    'Also a weekly note on Thursday evenings: the days with the lowest pollution risk, Friday to Monday, at each saved spot.']) {
    assert.ok(JS.includes(said), `the preview lost: ${said}`); assert.ok(LIVE.includes(said), `the live page no longer says: ${said}`);
  }
  // The two opening sentences are put together on the live page (a notification, or an email): their ends are its own.
  for (const [mine, end] of [['A notification when one of your saved spots reaches', ' when one of your saved spots reaches high or very high risk, at most once a day for each.'],
    [' Another when official advice is newly shown', ' when official advice is newly shown at one of them, also at most once a day for each.']]) {
    assert.ok(JS.includes(mine) && JS.includes(end), mine); assert.ok(LIVE.includes(end), `the live page no longer says: ${end}`);
  }
  // One setting for both pages: the same record, the same service, the same body.
  assert.match(ALERTS, /PUSH_KEY = 'dipcast\.push'/); assert.match(LIVE, /const PUSH_KEY = 'dipcast\.push'/);
  assert.match(ALERTS, /body: JSON\.stringify\(\{ subscription: sub\.toJSON\(\), spots, weekly \}\)/);
  assert.match(LIVE, /body: JSON\.stringify\(\{ subscription: sub\.toJSON\(\), spots, weekly \}\)/);
  // The worker is started and permission asked only inside turnOn, which only the button calls.
  assert.equal((ALERTS.match(/serviceWorker\.register\(/g) || []).length, 1); assert.match(ALERTS, /if \(start\) \{ await navigator\.serviceWorker\.register/);
  assert.equal((ALERTS.match(/requestPermission\(/g) || []).length, 1); assert.doesNotMatch(JS + MAP, /serviceWorker\.register|requestPermission/);
  assert.equal((JS.match(/A\.turnOn\(/g) || []).length, 1);
});

test('a plan keeps the live site\'s groups: low risk is never mixed with no daily level or a higher level', () => {
  const at = (id, lat, extra, labels = ['low', 'low', 'low', 'low', 'low']) => spot(labels, {id, name: id, lat, lon: -1.8, ...extra});
  const spots = [at('low-near', 53.92), at('low-far', 54.05), at('raised', 53.91, {}, ['high', 'high', 'low', 'high', 'high']), tarn({id: 'tarn', lat: 53.93, lon: -1.8}),
    at('advised', 53.905, {official: NOTICE}), at('beyond', 55.5)];
  const from = {lat: 53.9, lon: -1.8}, plan = {...PLAN.PLAN_DEFAULT, day: DAYS[0], within: 20, from: {name: 'Ilkley', ...from}};
  const found = PLAN.planSpots(spots, plan, s => M.kmBetween(from, s) / PLAN.MILE_KM), G = M.planRows(found, DAYS[0], from);
  const g = k => (G.find(x => x.key === k) || {rows: []}).rows.map(r => r.id);
  assert.deepEqual(g('low'), ['low-near', 'low-far', 'advised']);   // nearest first; official advice last, with its notice on the row
  assert.equal(G.find(x => x.key === 'low').rows[2].notice.length > 0, true);
  assert.deepEqual(g('plain'), ['tarn']); assert.deepEqual(g('raised'), ['raised']);
  assert.equal(found.count, 5, 'a place beyond the distance is left out');
  assert.match(G[0].rows[0].said, /^(under a mile|[\d.]+ miles?) north$/);
  // On the day the raised place is low it moves up, with the same date everywhere.
  const thu = PLAN.planSpots(spots, {...plan, day: DAYS[2]}, s => M.kmBetween(from, s) / PLAN.MILE_KM);
  assert.ok(M.planRows(thu, DAYS[2], from).find(x => x.key === 'low').rows.some(r => r.id === 'raised'));
  // The page calls the live site's rules, not copies of them.
  for (const name of ['planSpots', 'planHash', 'readPlan', 'planKept', 'betterDay', 'planAreas']) { assert.equal(typeof PLAN[name], 'function'); assert.match(JS, new RegExp(`\\b${name}\\(`)); }
});

test('the map shows each place at its level for the day, and an overflow as the line shows it', () => {
  const spots = [spot(ALL, {id: 'a'}), tarn({id: 'tarn', lat: 54.4, lon: -3}), spot(ALL, {id: 'adv', official: NOTICE}), spot(ALL, {id: 'nowhere', lat: null})];
  const pts = M.mapPoints(spots, DAYS[3]);
  assert.deepEqual(pts.map(p => [p.id, p.cls, p.advised]), [['a', 'lv-high', false], ['tarn', 'lv-clear', false], ['adv', 'lv-high', true]]);
  assert.equal(M.mapPoints(spots, DAYS[2])[0].cls, 'lv-low');
  for (const c of ['lv-low', 'lv-moderate', 'lv-high', 'lv-veryhigh', 'lv-clear', 'lv-none']) assert.ok(MAP.includes(`'${c}'`), c);   // every class has a colour
  // The overflows: the line's own items at the upstream file's positions.
  const up = [{site_id: 'X1', site_name: 'NEAR CSO', company: 'Yorkshire Water', distance_km: 2, lat: 53.95, lon: -1.9, status: 1, data_state: 'live', feed_updated_at: '2026-11-24T13:10:00+00:00'},
    {site_id: 'X2', site_name: 'FAR CSO', company: 'Yorkshire Water', distance_km: 9, lat: 54.0, lon: -2.0, status: 0, data_state: 'live', feed_updated_at: '2026-11-24T13:10:00+00:00'},
    {site_id: 'X3', site_name: 'UNPLACED CSO', company: 'Yorkshire Water', distance_km: 12, status: 0, data_state: 'live', feed_updated_at: '2026-11-24T13:10:00+00:00'}];
  const s = spots[0], line = M.riverLine(s, up, null, spots, NOW, DAYS[0]), o = M.overflowPoints(line.items, up);
  assert.deepEqual(o.map(p => [p.id, p.mark]), [['X1', 'spilling'], ['X2', 'quiet']]);   // one with no position is on the line only
  assert.equal(o[0].mark, line.items.find(i => i.id === 'X1').mark);
  assert.match(o[1].said, /9\.0 km upstream\.$/);
  // The traced water is read as the live map reads it.
  assert.deepEqual(M.decodeLine('_p~iF~ps|U_ulLnnqC_mqNvxq`@'), [[38.5, -120.2], [40.7, -120.95], [43.252, -126.453]]);
  assert.deepEqual(M.decodeLine(''), []);
});

test('the maps use the live map\'s own library and credit, and open only when asked for', () => {
  for (const hash of ['sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=', 'sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=']) { assert.ok(MAP.includes(hash)); assert.ok(LIVE.includes(hash)); }
  assert.doesNotMatch(PAGE, /leaflet/);   // not in the page: asked for by map.js when a map is first opened
  assert.match(MAP, /fetch\('map\.json'\)/); assert.match(MAP, /attribution: CONF\.credit/);
  assert.match(MAP, /The same places are in the list/); assert.match(JS, /The same places as a list/);   // the list is the map's other way in
});

test('a place has an address of its own, and the links made before it had one still open it', () => {
  const at = (path, search = '') => M.parseAddress(path, search, '/preview/');
  assert.deepEqual(at('/preview/spot/bw-uke4100-08901/', '?day=2026-11-28'), {screen: 'place', id: 'bw-uke4100-08901', day: SAT});
  assert.deepEqual(at('/preview/spot/a/index.html'), {screen: 'place', id: 'a', day: null});
  assert.deepEqual(at('/preview/', '?spot=a&day=2026-11-28'), {screen: 'place', id: 'a', day: SAT});   // an old link
  assert.equal(at('/preview/', '?view=map').view, 'map');
  assert.equal(at('/preview/spot/<script>/').screen, 'find');
  assert.equal(at('/elsewhere/spot/a/').screen, 'find', 'only under where the pages are published');
  assert.equal(M.parseAddress('/spot/a/', '', '/').id, 'a', 'and at the root of a site, were they published there');
  // Every address the page writes is relative to where the pages are published, and every page has a <base> there.
  assert.match(JS, /const BASE = new URL\('\.\/', document\.baseURI\)\.pathname;/);
  assert.match(JS, /if \(!document\.querySelector\('base'\)\)/);
  assert.doesNotMatch(JS, /'\?spot='|q\.set\('spot'/);
});

test('the build draws each page with the page\'s own script, as at the moment the forecast was issued', () => {
  const os = require('node:os');
  const {prerender, ageless} = require(path.join(__dirname, '../scripts/prerender_preview.js'));
  const site = fs.mkdtempSync(path.join(os.tmpdir(), 'pv-built-'));
  fs.mkdirSync(path.join(site, 'data', 'upstream'), {recursive: true}); fs.mkdirSync(path.join(site, 'data', 'spot')); fs.mkdirSync(path.join(site, 'preview'));
  const a = spot(ALL, {id: 'a', detail_file: 'spot/a.json'}), lake = tarn({id: 'tarn'});
  fs.writeFileSync(path.join(site, 'data', 'spots-lite.json'), JSON.stringify({generated_at: GEN, build: {live_feeds: {polled_at: '2026-11-24 13:15:08+00:00'}}, spots: [a, lake, spot(ALL, {id: 'not an id'})]}));
  fs.writeFileSync(path.join(site, 'data', 'spot', 'a.json'), JSON.stringify({id: 'a', contributors: []}));
  fs.writeFileSync(path.join(site, 'data', 'upstream', 'a.json'), JSON.stringify({id: 'a', overflows: [
    {site_id: 'X1', site_name: 'NEAR CSO', company: 'Yorkshire Water', distance_km: 2, lat: 53.95, lon: -1.9, status: 0, data_state: 'live', feed_updated_at: '2026-11-24T13:10:00+00:00'}]}));
  fs.writeFileSync(path.join(site, 'preview', 'hero-photos.json'), JSON.stringify({a: {file: 'geograph-1.jpg', w: 640, h: 427, taken: '2021-06-14', credit: 'A Walker', caption: 'The river.'}}));
  const tz = process.env.TZ; let built;
  try { built = prerender(site); } finally { process.env.TZ = tz; fs.rmSync(site, {recursive: true, force: true}); }
  assert.deepEqual(Object.keys(built.spots), ['a', 'tarn'], 'a place whose id cannot be a folder has no page');
  const page = built.spots.a;
  assert.match(page, /<h1 id="title" tabindex="-1">River Aire, Somewhere<\/h1>/);
  assert.match(page, /<h2 class="level lv-moderate" id="answer-h">Moderate risk from sewage spills<\/h2>/);   // today, as issued
  assert.match(page, /guides\/photos\/geograph-1\.jpg/);
  assert.match(page, /One monitored storm overflow within 60 km upstream/); assert.doesNotMatch(page, /Reading the overflows upstream|Reading what is known/);
  assert.match(page, /Issued 13:21 ·/); assert.doesNotMatch(page, / ago\b/, 'an age would be wrong by the time the page is read');
  assert.equal(ageless('Issued 13:21, 0 min ago · A forecast'), 'Issued 13:21 · A forecast'); assert.equal(ageless('Issued Tue 13:21, 3 days ago.'), 'Issued Tue 13:21.');
  // Its links are the places' own addresses and the opening's, each a page the build writes.
  assert.match(page, /href="spot\/a\/\?day=2026-11-28" data-day="2026-11-28"/); assert.match(page, /<a class="brand" href="\.\/">/);
  assert.match(built.spots.tarn, /No monitored overflow found upstream/);
  assert.match(built.home, /<h1 id="title" tabindex="-1">Where do you swim\?<\/h1>/); assert.match(built.home, /Yorkshire/);
  // Until the forecast is read, a built page's links are plain links: the script leaves them to the browser.
  assert.match(JS, /if \(!DATA \|\| e\.metaKey/);
});
