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
const PAGE = read('index.html'), JS = read('app.js'), MODEL = read('model.js'), CSS = read('preview.css'), MAP = read('map.js'), ALERTS = read('alerts.js'), HOST = read('host.js');
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
    ['levels.js', 'eatoday.js', 'experience.js', 'lists.js', 'plan.js', 'preview/host.js', 'reviews.js', 'visits.js', 'illness.js',
      'spotscores.js', 'seasonal.js', 'evidence.js', 'measured.js', 'timeline.js', 'since.js', 'findwindow.js', 'journal.js', 'passport.js', 'anypoint.js', 'preview/model.js', 'preview/alerts.js', 'preview/map.js', 'preview/app.js']);
  // Every address is read against the site's root, as the live pages' are: the page says where that is, and where it is under it.
  assert.match(PAGE, /<html lang="en-GB" data-home="preview\/">/); assert.match(PAGE, /<base href="\.\.\/">\n<title>/);
  assert.ok(PAGE.indexOf('<base href="../">') < PAGE.indexOf('href="fonts/'), 'the <base> comes before the first relative address');
  for (const [name, text] of [['index.html', PAGE], ['app.js', JS], ['map.js', MAP], ['alerts.js', ALERTS]]) assert.doesNotMatch(text.replace('<base href="../">', ''), /["'`(]\.\.\//, `${name}: nothing is asked for from "../"`);
  assert.doesNotMatch(CSS, /text-transform:\s*uppercase|linear-gradient|border-radius:\s*(?:999|[1-9]\d)px|letter-spacing:\s*0?\.\d+em/);   // the looks Ethan named as machine-made
  assert.match(CSS, /"Source Serif 4"/); assert.match(CSS, /--bar: #3d5b5d/); assert.match(CSS, /--radius: 8px/);
  const sizes = new Set([...CSS.matchAll(/font(?:-size)?:[^;]*?(\d+)px/g)].map(m => m[1]));
  assert.deepEqual([...sizes], [], 'every font size is one of the six tokens');
});

test('nothing in the scripts stops an older iPhone', () => {
  for (const [name, text] of [['app.js', JS], ['model.js', MODEL], ['map.js', MAP], ['alerts.js', ALERTS], ['host.js', HOST]]) {
    assert.doesNotMatch(text, /\(\?<[=!]/, `${name}: a lookbehind is refused by Safari before 16.4, and stops the whole script`);
    assert.doesNotMatch(text, /behavior:\s*'instant'/, `${name}: refused by Safari before 15.4`);
    assert.doesNotMatch(text, /\.at\(|structuredClone|\?\?=|\|\|=|&&=/, name);
  }
  assert.match(PAGE, /<link rel="preload" href="data\/spots-lite\.json" as="fetch" crossorigin>/);
});

test('nothing is called safe or clean, and no em-dash is written', () => {
  // One sentence may use the word: the alerts' own, the live page's, which says what no alert does not mean.
  const NOT_CLEAN = 'so no alert does not mean the water is clean';
  assert.ok(LIVE.includes(NOT_CLEAN) && JS.includes(NOT_CLEAN));
  for (const [name, text] of [['index.html', PAGE], ['app.js', JS], ['model.js', MODEL], ['preview.css', CSS], ['map.js', MAP], ['alerts.js', ALERTS], ['host.js', HOST]]) {
    assert.doesNotMatch(text.replace(/env\(safe-area-inset-(top|bottom|right)\)/g, '').replace(NOT_CLEAN, ''), /\b(safe|clean|safely|cleaner)\b/i, name);
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
  assert.equal((ALERTS.match(/requestPermission\(/g) || []).length, 1); assert.doesNotMatch(JS + MAP, /requestPermission/);
  // The page itself starts the worker only as one of the site's own pages, and never over the "offline copy off" choice.
  assert.doesNotMatch(MAP, /serviceWorker\.register/); assert.equal((JS.match(/serviceWorker\.register\(/g) || []).length, 1);
  assert.match(JS, /if \(!PREVIEW && 'serviceWorker' in navigator\) \{ let off = false; try \{ off = localStorage\.getItem\('dipcast\.offline'\) === 'off'/);
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
  assert.match(MAP, /fetch\('preview\/map\.json'\)/); assert.match(MAP, /attribution: CONF\.credit/);
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
  assert.match(JS, /const SITE = new URL\('\.\/', document\.baseURI\)\.pathname, HOME = document\.documentElement\.dataset\.home \|\| '', BASE = SITE \+ HOME;/);
  // The live site's own addresses for Plan a swim, Saved and its map open those views, where these pages are the site's.
  assert.equal(M.parseAddress('/plan/', '', '/').view, 'plan'); assert.equal(M.parseAddress('/saved/', '', '/').view, 'saved');
  assert.equal(M.parseAddress('/', '?map=1', '/').view, 'map'); assert.equal(M.parseAddress('/', '?map=1&spot=a', '/').screen, 'place');
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
  let own;
  try { built = prerender(site); own = prerender(site, ''); } finally { process.env.TZ = tz; fs.rmSync(site, {recursive: true, force: true}); }
  assert.deepEqual(Object.keys(built.spots), ['a', 'tarn'], 'a place whose id cannot be a folder has no page');
  const page = built.spots.a;
  assert.match(page, /<h1 id="title" tabindex="-1">River Aire, Somewhere<\/h1>/);
  assert.match(page, /<h2 class="level lv-moderate" id="answer-h">Moderate risk from sewage spills<\/h2>/);   // today, as issued
  assert.match(page, /guides\/photos\/geograph-1\.jpg/);
  assert.match(page, /One monitored storm overflow within 60 km upstream/); assert.doesNotMatch(page, /Reading the overflows upstream|Reading what is known/);
  assert.match(page, /Issued 13:21 ·/); assert.doesNotMatch(page, / ago\b/, 'an age would be wrong by the time the page is read');
  assert.equal(ageless('Issued 13:21, 0 min ago · A forecast'), 'Issued 13:21 · A forecast'); assert.equal(ageless('Issued Tue 13:21, 3 days ago.'), 'Issued Tue 13:21.');
  // Its links are the places' own addresses and the opening's, each a page the build writes.
  assert.match(page, /href="preview\/spot\/a\/\?day=2026-11-28" data-day="2026-11-28"/); assert.match(page, /<a class="brand" href="preview\/">/);
  assert.match(page, /<span class="tag">Preview<\/span>/); assert.match(page, /href="\.\/">the current SwimSignal<\/a>/);
  assert.match(page, /src="guides\/photos\/geograph-1\.jpg"/); assert.match(page, /href="methods\.html"/);
  // As the site's own pages: the same page at the site's addresses, with no word of a preview, and the app it
  // replaced named as the earlier version, at classic/.
  const mine = own.spots.a;
  assert.match(mine, /href="spot\/a\/\?day=2026-11-28" data-day="2026-11-28"/); assert.match(mine, /<a class="brand" href="\.\/">/);
  assert.doesNotMatch(mine, /[Pp]review|current site|current SwimSignal/);
  assert.match(mine, /href="classic\/">the earlier version of SwimSignal<\/a>/); assert.match(mine, /href="classic\/spot\/a\/">This place on the earlier version<\/a>/);
  assert.match(own.home, /href="\?view=map"/); assert.match(built.home, /href="preview\/\?view=map"/);
  assert.match(built.spots.tarn, /No monitored overflow found upstream/);
  assert.match(built.home, /<h1 id="title" tabindex="-1">Where do you swim\?<\/h1>/); assert.match(built.home, /Yorkshire/);
  // Until the forecast is read, a built page's links are plain links: the script leaves them to the browser.
  assert.match(JS, /if \(!DATA \|\| e\.metaKey/);
});

test('as the site\'s own pages: the app is "the earlier version" at classic/, and a sent outing is passed on to it', () => {
  assert.match(JS, /const classic = \(path = ''\) => \(\(PREVIEW \? '' : 'classic\/'\) \+ path\) \|\| '\.\/';/);
  assert.match(JS, /const link = r => \{ const a = P\.queryFor\(r\); return a === '\.\/' \? HOME \|\| '\.\/' : HOME \+ a; \};/);
  // A sent outing is a thing only the app can show: passed on, but never for this page's own Plan. A shared list is shown here.
  assert.match(JS, /if \(!\(route\.view === 'plan' && \/\[#&\]spot=\/\.test\(location\.hash\)\)\) return false;\n  location\.replace\(classic\('plan\/'\) \+ location\.hash\); return true;/);
  assert.match(JS, /if \(PREVIEW \|\| !route \|\| !DATA\) return false;/);
  assert.match(JS, /const sh = readShared\(location\.hash, dates\(\)\); if \(sh\) return sharedHtml\(sh\);/);
  assert.match(JS, /if \(opts\.first && passOn\(\)\) return;/);
  assert.equal(typeof LISTS.readShared, 'function');
  assert.ok(LISTS.readShared('#list=Weekend&spots=a,b', DAYS), 'a shared list is read from the address');
  assert.equal(LISTS.readShared('', DAYS), null);
});

test('as the site\'s own pages they carry the two things the privacy notice says a visitor can turn off, under its name for them', () => {
  // The notice names the place: 'under "Saved spots, offline use and your data" at the bottom of the home page'.
  const NOTICE = fs.readFileSync(path.join(SITE, '../pages/privacy.html'), 'utf8');
  assert.match(NOTICE, /Saved spots, offline use and your data/);
  assert.match(JS, /<details class="yourdata" id="your-data"\$\{dataOpen \? ' open' : ''\}><summary>Saved spots, offline use and your data<\/summary>/);
  assert.match(JS, /\$\{yourDataHtml\(\)\}\n    <details><summary>Data sources and licences<\/summary>/, 'on every page\'s foot');
  assert.match(JS, /if \(PREVIEW\) return '';   \/\/ beside a preview the home page is the app's, which has it/);
  // The live page's words, each of them: the labels and what is said after a press.
  for (const said of ['Turn the offline copy back on', 'Turn off the offline copy', 'Count my visits again', "Don't count my visits",
    'Page views are counted, without cookies.', 'Your browser asks sites not to track it, so your visits are not counted.',
    'This browser is not keeping site data, so this lasts only until you close the page.', 'The offline copy is on again.',
    'The offline copy is off, and deleted from this device.', ' Alerts are off too: they need it.',
    'This browser is not keeping site data, so it cannot keep this choice.', 'Your visits will be counted again from the next page you open.',
    'Your visits from this browser are not counted from the next page you open.']) {
    assert.ok(LIVE.includes(said), `the live page says: ${said}`); assert.ok(JS.includes(said), `and so does this one: ${said}`);
  }
  // The same keys the worker's start and the counter read, so a choice made on either design holds on both.
  const COUNTER = fs.readFileSync(path.join(SITE, 'counter.js'), 'utf8');
  assert.match(COUNTER, /var COUNT_KEY = 'dipcast\.count';/); assert.match(LIVE, /const OFFLINE_KEY = 'dipcast\.offline';/);
  assert.match(JS, /localStorage\.setItem\('dipcast\.count', 'off'\)/); assert.match(JS, /localStorage\.setItem\('dipcast\.offline', 'off'\)/);
  assert.match(JS, /if \(!off\) startWorker\(\); \}/, 'the worker is not started again once turned off');
  assert.match(JS, /if \(on\) \{ startWorker\(\); return kept; \}/);
  // Off means gone: the worker, what it stored, a kept outing, and alerts first, since they arrive through the worker.
  assert.match(JS, /for \(const r of await navigator\.serviceWorker\.getRegistrations\(\)\) await r\.unregister\(\);/);
  assert.match(JS, /if \(k\.startsWith\('dipcast-'\) \|\| k === 'swimsignal-outing'\) await caches\.delete\(k\);/);
  assert.match(fs.readFileSync(path.join(SITE, 'outingpack.js'), 'utf8'), /const CACHE = 'swimsignal-outing', KEY = 'dipcast\.outingpack'/);
  assert.match(JS, /localStorage\.removeItem\('dipcast\.outingpack'\)/);
  assert.ok(JS.indexOf('await window.PVAlerts.turnOff(DATA.push)') < JS.indexOf('const kept = await setOffline(on)'), 'alerts are turned off before the worker goes');
  // The counter's row only where the build put the counter in, and no button where the browser has objected already.
  assert.match(JS, /const c = document\.getElementById\('page-counter'\), counted = !!c && c\.tagName === 'SCRIPT';/);
  assert.match(JS, /const noTrack = \(\) => navigator\.globalPrivacyControl === true \|\| navigator\.doNotTrack === '1';/);
  // Alerts' own line, when the copy is off, points at this page's fold and not at the earlier version's.
  assert.match(JS, /\(PREVIEW \? classic\('#your-data'\) : '#your-data'\) \+ '" data-do="to-data">Turn it back on<\/a>/);
  assert.match(CSS, /\.foot summary \{ cursor: pointer; padding: 12px 0; \}/); assert.match(CSS, /\.yourdata \.textbtn \{ min-height: 44px; \}/);
});

test('the spill map is the live site\'s own script, asked for only when its place on the page is near', () => {
  const PL = require(path.join(SITE, 'plume.js'));
  // The script draws the tile and the map; the page gives it a place, the map's library and the page's own tiles.
  assert.match(JS, /plumeStyle\(document\); el\.classList\.add\('on'\); el\.innerHTML = plumeTile\(s, doc, replay, gen, now\(\)\); mine\.map = plumeBind\(el, s, doc, replay, trace, gen\);/);
  for (const f of ['plumeStyle', 'plumeTile', 'plumeBind']) assert.equal(typeof PL[f], 'function', f);
  assert.match(MAP, /window\.PVMap = \{ home, homeTo, place, load, tiles \};/);
  assert.match(JS, /window\.tiles = window\.PVMap\.tiles;/);
  assert.match(fs.readFileSync(path.join(SITE, 'plume.js'), 'utf8'), /\(typeof tiles === 'function' \? tiles\(\) : L\.tileLayer\(/);
  // Not in the page's own scripts: plume.js, the map's library and the place's three files come when the slot is
  // within a screen of view, as on the live page.
  assert.doesNotMatch(PAGE, /plume\.js/);
  assert.match(JS, /const io = new IntersectionObserver\(es => \{ if \(es\.some\(e => e\.isIntersecting\)\) \{ io\.disconnect\(\); go\(\); \} \}, \{ rootMargin: '100% 0px' \}\);/);
  assert.match(JS, /Promise\.all\(\[plumeLib, window\.PVMap\.load\(\), get\('-plume\.json'\), get\('-replay\.json'\), get\('-trace\.json'\)\]\)/);
  // For a listed place with a daily forecast; a place with no routes file keeps an empty slot that takes no room.
  assert.match(JS, /const plumeWanted = s => !s\.unlisted && !!s\.detail_file && daily\(s\);/);
  assert.match(JS, /if \(!doc \|\| !replay\) return;/);
  assert.match(CSS, /\.spill\.on \{ margin-top: 32px; padding-top: 20px; border-top: 1px solid var\(--line\); \}/);
  assert.doesNotMatch(CSS, /\.spill \{/, 'the empty slot has no room or rule of its own');
  // Kept through a redraw, so the slider stays where it was left; the map is let go when the place is left.
  assert.match(JS, /if \(plume && plume\.id === s\.id\) \{ slot\.replaceWith\(plume\.el\); return; \}/);
  assert.match(JS, /const plumeGone = \(\) => \{ if \(plume && plume\.map\) plume\.map\.remove\(\); plume = null; \};/);
  // What it is: a model estimate, said in the script's own first line under the heading.
  assert.match(PL.PLUME_ESTIMATE, /model estimate/i); assert.match(PL.PLUME_ESTIMATE, /not a measurement/i);
});

test('reviews, notes on a visit and reports of illness are the live site\'s own scripts, drawn into the place\'s page', () => {
  // Loaded as they are, after the few names they expect of their page; the page gives them the place they look for.
  const order = [...PAGE.matchAll(/<script src="([^"]+)"/g)].map(m => m[1]);
  assert.ok(order.indexOf('preview/host.js') < order.indexOf('reviews.js') && order.indexOf('reviews.js') < order.indexOf('visits.js') && order.indexOf('visits.js') < order.indexOf('preview/app.js'));
  const RV = fs.readFileSync(path.join(SITE, 'reviews.js'), 'utf8'), VN = fs.readFileSync(path.join(SITE, 'visits.js'), 'utf8');
  for (const s of [RV, VN]) assert.match(s, /document\.querySelector\('#result \.stack \.tiles'\)/, 'the live scripts still look for this place');
  assert.match(JS, /el\.id = 'result';\n  el\.innerHTML = '<div class="stack"><div class="tiles" hidden><\/div>/);
  assert.match(JS, /mountReviews\(s\); if \(typeof mountVisits === 'function'\) mountVisits\(s\); if \(typeof mountIllness === 'function'\) mountIllness\(s\);/);
  // What they have drawn is kept and put back when the page is drawn again, so a form half written is not lost.
  assert.match(JS, /if \(swim && swim\.id === s\.id\) \{ slot\.replaceWith\(swim\.el\); return; \}/);
  // What they expect of the page: each is there, and each sentence a swimmer reads is the live page's.
  for (const name of ['function showRest(rows, button)', 'function draftTrack(form, spot)', 'const draftForget = (form, spot)']) assert.ok(HOST.includes(name), name);
  for (const said of ["Unsent answers stay in this tab's memory until it is closed or reloaded. Photos must be added again after leaving the page.",
    'Leave this page? What you have written here will be lost.']) { assert.ok(HOST.includes(said), said); assert.ok(LIVE.includes(said), `the live page no longer says: ${said}`); }
  for (const used of ['showRest(', 'draftTrack(', 'draftForget(']) assert.ok(RV.includes(used), `reviews.js no longer calls ${used}`);
  // Nothing of theirs is in a page the build draws: the list of reviews is read in the browser, as on the live page.
  assert.match(JS, /const swimmersHtml = s => typeof mountReviews !== 'function' \|\| !reviewable\(s\) \? ''/);
  // Every class they write has a rule here, so nothing of theirs is left undressed.
  for (const c of ['rv-tile', 't-lab', 't-fig', 't-say', 't-key', 't-more', 'rv-bar', 'rv-list', 'rv-v', 'rv-meta', 'rv-text', 'rv-pics', 'rv-pic', 'rv-acts', 'linkbtn', 'rv-write', 'rv-said',
    'rv-form', 'rv-q', 'rv-opt', 'rv-choice', 'vn-kinds', 'rv-add', 'rv-file', 'rv-consent', 'rv-hp', 'rv-hint', 'rv-send', 'rv-msg', 'rv-report', 'rv-view', 'rv-close', 'rv-previews', 'rv-sure', 'vn-flag', 'vn-caveat'])
    assert.match(CSS, new RegExp(`\\.${c}\\b`), c);
});

test('the record at a place is the live site\'s own: how the forecast has done there, and past spills by month', () => {
  const SC = require(path.join(SITE, 'spotscores.js')), SE = require(path.join(SITE, 'seasonal.js'));
  // The page calls the live scripts for the markup, from the live site's own files.
  assert.match(JS, /scoresLoad\(\)\.then\(d => \{ SCORES = d \|\| null; scoresRead = true;/);
  assert.match(JS, /scoresTile\(s, SCORES\)/); assert.match(JS, /const full = got \? \{ \.\.\.s, \.\.\.\(got\.detail \|\| \{\}\) \} : null/); assert.match(JS, /seasonalTile\(full\)/);
  assert.match(fs.readFileSync(path.join(SITE, 'spotscores.js'), 'utf8'), /const SCORES_FILE = 'data\/spot_scores\.json';/);
  // How the forecast has done: only where it counts an overflow upstream, as on the live page, never at a place with none.
  assert.match(JS, /const wanted = typeof scoresWanted === 'function' && scoresWanted\(s\);/); assert.match(JS, /!wanted \? '' : !scoresRead \?/);
  assert.equal(SC.scoresWanted(spot(ALL)), true); assert.equal(SC.scoresWanted(tarn()), false);
  // What they give is what the page shows: the counts in words, and twelve months.
  const tile = SC.scoresTile(spot(ALL), {min_spills: 10, first_day: '2026-09-29', spots: {a: {overflows: 10, scored_overflows: 10, overflow_days: 300, spill_days: 12, forecasts: 1400, hits: 20, misses: 30, false_alarms: 40, days: 37, first_day: '2026-09-29'}}});
  assert.match(tile, /<section class="tile" id="scores"/); assert.match(tile, /href="verification\.html#warnings"/);
  const months = SE.seasonalTile({...spot(ALL), seasonal: {years: [2024, 2025], overflows: 10, covered_min: 10, days: [62, 57, 62, 60, 62, 60, 62, 62, 60, 62, 60, 62],
    spill: [33, 21, 24, 25, 21, 30, 33, 32, 27, 22, 29, 23], short: {}, made: '2026-10-27'}});
  assert.match(months, /<details class="tile fold" id="seasonal">/); assert.equal((months.match(/<span[^>]*><em>/g) || []).length, 12);
  assert.match(months, /History, not a forecast\./);
  // Kept when the page is drawn again, so a fold opened stays open; and every class they write has a rule here.
  assert.match(JS, /if \(rec && rec\.key === key\) \{ if \(slot !== rec\.el\) slot\.replaceWith\(rec\.el\); return; \}/);
  for (const c of ['record', 'mchart', 's-now', 's-more', 's-bar', 'seasonal', 'fold']) assert.match(CSS, new RegExp(`\\.${c}\\b`), c);
});

test('Saved has the live site\'s own: what changed since you last looked, each place\'s low-risk days, and a list to share', () => {
  const SI = require(path.join(SITE, 'since.js')), FW = require(path.join(SITE, 'findwindow.js'));
  // Since you last looked: the page asks the live rules for the words, only while today is shown, and notes what it showed.
  assert.match(JS, /const sum = isToday && mine\.length && typeof sinceSummaryFor === 'function' \? sinceSummaryFor\(mine, DATA\.generated_at\) : null;/);
  assert.match(JS, /const since = id => isToday && typeof sinceSaid === 'function' \? sinceSaid\(spotOf\(id\), DATA\.generated_at\) : '';/);
  assert.match(JS, /if \(s && placeDay\(s\) === today\(\)\) lookedAt\(\[s\], DATA\.generated_at, saved\);/);
  assert.match(JS, /writeSeen\(new Set\(allSaved\(LISTS\)\)\)/, 'a place unsaved loses its note');
  assert.equal(SI.SEEN_KEY, 'dipcast.seen');   // the live site's own note, so the two pages share one
  // Nothing over the places on a first look, as on the live page.
  assert.equal(SI.sinceSummary([{name: 'A', was: undefined, now: null}]).state, 'none'); assert.match(JS, /sum && sum\.state !== 'none'/);
  // Find a window: the live section, for two places or more, its links to this page's own addresses.
  assert.match(JS, /mine\.length > 1 && typeof fwSection === 'function' \? fwSection\(mine, dates\(\), s => link\(\{ id: s\.id \}\)\) : ''/);
  data([spot(ALL), spot(['low', 'low', 'low', 'low', 'low'], {id: 'b', name: 'B'})]);
  const sec = FW.fwSection([spot(ALL), spot(['low', 'low', 'low', 'low', 'low'], {id: 'b', name: 'B'})], DAYS, s => M.queryFor({id: s.id}));
  assert.match(sec, /<a href="spot\/a\/" data-id="a" class="fw-nm">/); assert.match(sec, /Low risk: Tue 24 Nov to Sat 28 Nov\./); assert.match(sec, /Low risk is not a safety check/);
  // Sharing: the live link's own form, and its words for what the link holds.
  assert.equal(LISTS.shareHash('Weekend', ['a', 'b']), '#list=Weekend&spots=a,b');
  assert.match(JS, /new URL\(link\(\{ view: 'saved' \}\), document\.baseURI\)\.href \+ shareHash\(cur\.name, ids\)/);
  for (const said of ['A link that opens this list on another phone or browser, or for a friend, who can then add it to their own lists.', "It is not kept on this device unless you add it.",
    'Once added, it stays under Saved, where you can set up alerts for its spots.', 'None of the spots in this link is in the forecast now, or the link was cut short.']) {
    assert.ok(JS.includes(said), said); assert.ok(LIVE.includes(said), `the live page no longer says: ${said}`); }
  assert.match(JS, /addSharedList\(LISTS, sh\.name, ids\)/); assert.match(JS, /sameList\(LISTS, sh\.name, spots\.map\(s => s\.id\)\)/);
  assert.match(HOST, /const spotPath = id => `\$\{document\.documentElement\.dataset\.home \|\| ''\}spot\/\$\{encodeURIComponent\(id\)\}\/`;/);
  for (const c of ['place-since', 'since-ev', 'since-sum', 'fw-list', 'fw-nm', 'fw-note', 'fw-apart', 'o-tag', 'sharelist']) assert.match(CSS, new RegExp(`\\.${c}\\b`), c);
});

test('Saved moves or copies a place between lists and opens a list from a pasted link, by the live site\'s own rules', () => {
  // The rules are lists.js's, which the page calls: nothing about a list is worked out twice.
  assert.match(JS, /const kept = setLists\(copy \? copyToList\(LISTS, id, to\.id\) : moveToList\(LISTS, id, fromId, to\.id\)\);/);
  assert.match(JS, /const got = pastedList\(box\.value, location\.origin\);/);
  const two = {current: 'l1', lists: [{id: 'l1', name: 'Weekend', spots: ['a', 'b']}, {id: 'l2', name: 'Club', spots: ['c']}]};
  assert.deepEqual(LISTS.moveToList(two, 'a', 'l1', 'l2').lists.map(l => l.spots), [['b'], ['c', 'a']]);
  assert.deepEqual(LISTS.copyToList(two, 'a', 'l2').lists.map(l => l.spots), [['a', 'b'], ['c', 'a']]);
  // Offered with two lists or more and a place to move; opening a link is offered always, an empty Saved included,
  // since the Home Screen app on an iPhone has no address bar to paste into.
  assert.match(JS, /many && movable\.length \? '<button type="button" class="textbtn" data-do="list-mv">Move or copy a place<\/button>' : ''\}<button type="button" class="textbtn" data-do="list-open">Open a list from a link<\/button>/);
  // What is said is what the live page says.
  for (const said of ['Paste a link to a SwimSignal list first.', 'That is too long to be a link to a list.', 'That is not a link. Paste the whole link, starting https://.',
    'That is a link to another website, not SwimSignal.', "That link has no list of spots in it. A list's link has saved/#list= in it.",
    'Open a list from a link', 'Paste a link to a list, sent to you or copied with Share this list', ' is in ${to.name} already.',
    'This browser is not keeping site data, so this change lasts only for this visit.']) {
    assert.ok(LIVE.includes(said), `the live page says: ${said}`); assert.ok(JS.includes(said), `and so does this one: ${said}`);
  }
  assert.match(JS, /`\$\{copy \? 'Copied' : 'Moved'\} \$\{s\.name\} \$\{copy \? 'to' : `from \$\{from\.name\} to`\} \$\{to\.name\}\.`/);
  // Only a link to a Saved page of this site that holds a list is taken, and it opens as a shared list: read only.
  assert.equal(LISTS.pastedList('https://example.com/saved/#list=A&spots=a', 'https://swimsignal.co.uk').why, 'site');
  assert.equal(LISTS.pastedList('https://swimsignal.co.uk/plan/', 'https://swimsignal.co.uk').why, 'notlist');
  assert.equal(LISTS.pastedList('https://swimsignal.co.uk/saved/#list=A&spots=a,b', 'https://swimsignal.co.uk').hash, '#list=A&spots=a,b');
  assert.match(JS, /listForm = null; history\.pushState\(null, '', link\(\{ view: 'saved', day: route\.day \}\) \+ got\.hash\); draw\(\{ focus: true \}\);/);
  assert.doesNotMatch(JS, /clipboard\.read/, 'nothing is read from the clipboard: the reader pastes');
});

test('Saved compares up to three places by the live site\'s own rules, and every cell says something', () => {
  const X = require(path.join(SITE, 'experience.js'));
  // The rules are experience.js's and plan.js's, which the page calls; the table is this page's own markup.
  assert.match(JS, /const days = spots\.map\(s => compareDays\(s, ds\)\), facts = spots\.map\(s => compareRows\(s, day, DATA\.generated_at\)\), water = spots\.map\(compareWater\);/);
  assert.match(JS, /const ids = cmpIds = planCompareIds\(cmpIds, mine\), ds = dates\(\);/);
  assert.match(JS, /cmpIds = comparisonIds\(\[\.\.\.app\.querySelectorAll\('\[data-cmp\]'\)\]\.map\(x => x\.value\), /);
  assert.match(JS, /if \(mine\.length < 2 \|\| typeof compareRows !== 'function' \|\| typeof evidenceRows !== 'function'\) return '';/, 'nothing to compare until two places are saved');
  // Up to three, the first three until others are chosen, and a choice of one filled up again.
  const three = ['a', 'b', 'c', 'd'].map(id => ({id}));
  assert.deepEqual(PLAN.planCompareIds(null, three), ['a', 'b', 'c']);
  assert.deepEqual(PLAN.planCompareIds(['d', 'b'], three), ['d', 'b']);
  assert.deepEqual(X.comparisonIds(['a', 'a', 'zz', 'b'], three), ['a', 'b']);
  // A place with a daily forecast has a cell a day; one without has one cell for the five, in its headline's words.
  const d = X.compareDays(spot(ALL), DAYS);
  assert.equal(d.same, false); assert.deepEqual(d.days.map(x => x.level), ALL);
  const t = X.compareDays(tarn(), DAYS);
  assert.equal(t.same, true); assert.doesNotMatch(t.days[0].words, /\blow\b/i);
  assert.match(JS, /: i \? '' : `<td class="same" rowspan="\$\{ds\.length\}"\$\{hd\('cmp-days', j\)\}>\$\{cell\(d\.days\[0\]\)\}\. The same on every day\.<\/td>`/);
  // Every row of facts has words in every column: missing data says it is not known.
  for (const s of [spot(ALL), tarn()]) for (const [label, html] of X.compareRows(s, DAYS[0], GEN, NOW)) assert.ok(String(html).trim().length > 3, `${s.id}: ${label}`);
  // The water today: a missing reading or gauge is said, never left blank.
  assert.match(JS, /: vt\('none', 'No reading'\),/); assert.match(JS, /\? vt\('none', 'No gauge'\) : rs\.stale \?/);
  // A level's words carry its colour; the day shown is the row shaded; no column is called the best.
  assert.match(JS, /const cell = x => `<span class="lvl \$\{P\.cls\(x\.level\)\}">\$\{esc\(x\.words\)\}<\/span>`/);
  assert.match(JS, /<tr\$\{iso === day \? ' class="on" aria-current="true"' : ''\}>/);
  assert.doesNotMatch(JS.slice(JS.indexOf('function compareHtml'), JS.indexOf('function redrawCompare')), /\b(best|winner|recommended)\b/i);
  // What a lower level is not, in this page's own words (the live table's sentence uses a word this page never does).
  assert.match(JS, /A lower level is the forecast for sewage pollution, not a safety check: check the signs at the water\./);
  // A place's own file is asked for once, for its guide; the table is drawn again where it was scrolled to.
  assert.match(JS, /for \(const id of cmpIds \|\| \[\]\) if \(!details\.has\(id\)\) loadDetail\(id\)\.then\(redrawCompare\);/);
  assert.match(CSS, /table\.cmp \{ width: 100%; min-width: calc\(var\(--cols, 2\) \* 150px\); table-layout: fixed;/);
});

test('the swim journal and the passport are the live site\'s own, on this device only', () => {
  const JN = require(path.join(SITE, 'journal.js')), JS_JN = fs.readFileSync(path.join(SITE, 'journal.js'), 'utf8');
  assert.equal(JN.JOURNAL_KEY, 'dipcast.swims');   // the live site's own, so a swim logged on either page is in both journals
  // The live script binds "Log a swim" and draws the form; the page gives it the names it looks for.
  assert.match(JS_JN, /const b = document\.getElementById\('swam'\); if \(!b\) return;/); assert.match(JS_JN, /const acts = b\.closest\('\.actions'\); if \(!acts\) return;/);
  assert.match(JS, /<div class="actions"><button type="button" class="btn" id="swam" aria-expanded="false">Log a swim<\/button><\/div><p class="meta" id="swam-msg" role="status" aria-live="polite"><\/p>/);
  assert.match(JS, /journalLogBind\(s, DATA\.generated_at\);/);
  // The journal names a swim's place from the forecast the page holds, by the live page's name for it.
  assert.match(JS_JN, /typeof DATA !== 'undefined' && DATA \? new Map\(DATA\.spots\.map/); assert.match(JS, /window\.DATA = DATA;/);
  // On Saved: the journal and the passport, each drawn by its own script; a logged swim's link goes to the journal there.
  assert.match(JS, /el\.innerHTML = journalCard\(\) \+ \(typeof passportSection === 'function' \? passportSection\(DATA\.spots\) : ''\);/);
  assert.match(JS, /journalBindSection\(\); if \(typeof passportBind === 'function'\) passportBind\(\);/);
  assert.match(HOST, /const savedPath = \(\) => \{ const home = document\.documentElement\.dataset\.home \|\| ''; return home \? `\$\{home\}\?view=saved` : 'saved\/'; \};/);
  assert.match(JS, /location\.hash === '#journal' && typeof journalFocus === 'function'\) journalFocus\(\);/);
  // It makes no request: nothing in the journal leaves the browser.
  assert.doesNotMatch(JS_JN, /\bfetch\(/);
  for (const c of ['yourswims', 'jn-where', 'jn-seen', 'jn-file', 'jn-when', 'jn-kept', 'pp-sum', 'pp-badge']) assert.match(CSS, new RegExp(`\\.${c}\\b`), c);
});

test('any river or lake tapped on the map has a forecast: the live site\'s own arithmetic, at an address that reaches no server', () => {
  const AP = fs.readFileSync(path.join(SITE, 'anypoint.js'), 'utf8');
  // The live script's page wiring is for the live page's own map and does not run here; its arithmetic is what is called.
  assert.match(AP, /if \(typeof window !== 'undefined' && typeof map !== 'undefined'\) \{\n  map\.on\('click', AnyPoint\.onMapClick\);/);
  assert.doesNotMatch(PAGE + JS + MAP, /id="map"/, 'no element named map here, or the live wiring would wake');
  assert.match(JS, /AnyPoint\.point\(route\.point\[0\], route\.point\[1\]\)\.then\(d => \{ P\.prepareOne\(d, DATA, now\(\)\); d\.id = id; POINTS\.set\(id, d\);/);
  assert.match(AP, /squares, point, open, onMapClick, POINT_ZOOM \};/);
  // Where someone tapped is after the #, which a browser never sends; a link to it still opens the same point.
  const at = M.parseAddress('/', '?day=2026-11-28', '/', '#point=53.94820,-1.87950');
  assert.deepEqual(at, {screen: 'place', id: 'point-53.94820,-1.87950', point: [53.9482, -1.8795], day: SAT});
  data([spot(ALL)]);
  assert.equal(M.queryFor({id: at.id, day: SAT}), '?day=2026-11-28#point=53.94820,-1.87950'); assert.equal(M.queryFor({id: at.id}), './#point=53.94820,-1.87950');
  assert.doesNotMatch(M.queryFor({id: at.id, day: SAT}).split('#')[0], /5[0-9]\.\d|point/, 'nothing of the place before the #');
  assert.equal(M.parseAddress('/', '?point=53.9,-1.8', '/', '').screen, 'find', 'a point in the query is not read: it would reach the server');
  for (const far of ['#point=10,20', '#point=53.9,4.2', '#point=x,y', '#point=53.9', '#point=53.9,-1.8&x=1']) assert.equal(M.parseAddress('/', '', '/', far).screen, 'find', far);
  assert.equal(M.parseAddress('/spot/a/', '', '/', '#point=53.9,-1.8').id, 'a', 'a place\'s own page stays that place');
  assert.equal(M.pointOf('54.36,-2.935').id, 'point-54.36000,-2.93500');
  // A point is made ready as a listed place is, and is never offered what only a listed place has.
  const d = M.prepareOne({id: 'point-53.94820,-1.87950', unlisted: true, name: 'River Wharfe', kind: 'river', lat: 53.9482, lon: -1.8795, upstream_summary: {overflows: 10},
    now: {label: 'low', risk: 0.02}, days: DAYS.map(x => ({date: x, label: 'low', risk: 0.05})), contributors: []}, {generated_at: GEN}, NOW);
  assert.equal(d.days.length, 5); assert.equal(M.answer(d, SAT, data([spot(ALL)]), NOW).level, 'low');
  assert.match(JS, /if \(s\.unlisted\) return \['Unlisted point: not hand-checked'/); assert.match(JS, /\$\{s\.unlisted \? '' : `<button type="button" class="tool" data-do="keep"/);
  assert.match(JS, /Not one of the listed places: nobody has checked it by hand, and it has no rain forecast of its own and no E\.&nbsp;coli estimate\./);
  // Further out than the live map's own zoom a tap zooms in and asks again; outside the area it says so.
  assert.match(JS, /const need = AnyPoint\.POINT_ZOOM \|\| 9;/); assert.match(JS, /That point is outside Britain and Ireland/);
  assert.match(MAP, /if \(best \|\| !HOME\.onWater\) HOME\.onPick\(best \? best\.id : null\); else HOME\.onWater\(e\.latlng\.lat, e\.latlng\.lng, HOME\.map\.getZoom\(\)\);/);
  for (const said of ["A listed spot is checked by hand and gets its own rain forecast and E.&nbsp;coli estimate.", 'Request this as a spot']) { assert.ok(JS.includes(said), said); assert.ok(AP.includes(said), `anypoint.js no longer says: ${said}`); }
});

test('what the level rests on, lab results and the evidence timeline are the live site\'s own, for a listed place', () => {
  const EV = require(path.join(SITE, 'evidence.js')), TL = fs.readFileSync(path.join(SITE, 'timeline.js'), 'utf8');
  assert.match(JS, /evidenceTile\(full, at, DATA\.generated_at\)/); assert.match(JS, /measuredTile\(full, at\)/); assert.match(JS, /timelineTile\(full\)/);
  assert.match(JS, /const recordHtml = s => typeof evidenceTile !== 'function' \|\| s\.unlisted \? ''/, 'a point tapped on the map has no record');
  // The timeline reads its files when its fold is opened, by its own listener, and names the forecast's time from the page's.
  assert.match(TL, /document\.addEventListener\('toggle', timelineOpen, true\);/); assert.match(TL, /typeof DATA === 'object' && DATA \? DATA\.generated_at : null/);
  // What the live script gives for a place: its items as rows, each with its age and whose it is.
  const tile = EV.evidenceTile({...spot(ALL), contributors: []}, NOW, GEN);
  assert.match(tile, /<details class="tile fold" id="evidence">/); assert.match(tile, /<div class="factor"><div class="f-l">/); assert.match(tile, /<div class="f-src">/);
  assert.equal(EV.evidenceTile({...spot(ALL), unlisted: true}, NOW, GEN), '');
  for (const c of ['factors', 'factor', 'f-l', 'f-v', 'f-d', 'f-src', 'ev-gap']) assert.match(CSS, new RegExp(`\\.${c}\\b`), c);
});
