// The trial at /next/ (src/dipcast/site/next/; docs/DESIGN.md, "A second site at /next/"): a second swimmer site with its
// own page, stylesheet and script. Its look is free; what it says is not. These hold the rules that are about truth:
// the level is levels.js's own, an official notice comes first, "No monitored overflow found upstream" is never low,
// missing data is said as missing, and nothing is called safe or clean.   node --test tests/site_next.test.cjs
process.env.TZ = 'Europe/London';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const SITE = path.join(__dirname, '../src/dipcast/site');
const L = require(path.join(SITE, 'levels.js')), EA = require(path.join(SITE, 'eatoday.js'));
Object.assign(globalThis, L, EA);   // in the page the two files' names are globals; next.js uses only what they export
const N = require(path.join(SITE, 'next/next.js'));
const PAGE = fs.readFileSync(path.join(SITE, 'next/index.html'), 'utf8');
const JS = fs.readFileSync(path.join(SITE, 'next/next.js'), 'utf8');
const CSS = fs.readFileSync(path.join(SITE, 'next/next.css'), 'utf8');

const GEN = '2026-11-20T12:24:00+00:00', NOW = Date.parse('2026-11-20T14:00:00Z');
const DAYS = ['2026-11-20', '2026-11-21', '2026-11-22', '2026-11-23', '2026-11-24'];
const RISK = {low: 0.05, moderate: 0.2, high: 0.5, 'very high': 0.8};
const spot = (labels, extra = {}) => ({id: 'a', name: 'River Aire, Somewhere', kind: 'river', river: 'River Aire', area: 'Yorkshire', source: 'curated',
  lat: 53.9, lon: -1.8, upstream_summary: {overflows: 10}, location: {mode: 'river'}, assumptions: {max_upstream_km: 60, recent_spill_hours: 48},
  now: {label: 'low', risk: 0.02, discharging_upstream: 0, recent_upstream: 0, monitored_upstream: 10},
  days: labels.map((l, i) => ({date: DAYS[i], label: l, risk: l ? RISK[l] : null, rain_48h_mm: l ? 4 : null, expected_spilling_overflows: l ? 0.2 : null, in_validated_season: false})),
  weather: {days: DAYS.map(d => ({date: d, tmax: 7, sunrise: '07:43', sunset: '16:01', wind_kmh: 15, gust_kmh: 33}))}, ...extra});
const tarn = extra => spot([], {id: 'tarn', name: 'A Tarn', kind: 'lake', river: '', upstream_summary: {overflows: 0}, days: [],
  error: 'An isolated lake: the river network links no monitored storm overflow to it, so the forecast has nothing to say about it.', ...extra});
const NOTICE = [{line: 'Environment Agency: advice against bathing (harmful algae) since 19 Jun 2026', publisher: 'Environment Agency',
  link: 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj2310-11945', since: '2026-06-19', checked: '2026-10-26', state: 'stale', restricts: true}];
const data = spots => N.prepare({generated_at: GEN, build: {live_feeds: {polled_at: '2026-11-20 12:19:09.832693+00:00'}}, spots}, NOW);

test('the page is out of search engines and shares only the rules', () => {
  assert.match(PAGE, /<meta name="robots" content="noindex, nofollow">/);
  const scripts = [...PAGE.matchAll(/<script src="([^"]+)"/g)].map(m => m[1]);
  assert.deepEqual(scripts, ['../levels.js', '../eatoday.js', 'next.js']);
  assert.doesNotMatch(PAGE, /app\.js|page\.css|leaflet/);
  assert.doesNotMatch(CSS, /text-transform:\s*uppercase|box-shadow:\s*0 \d+px \d+px|linear-gradient|border-radius:\s*(?:999|[1-9]\d)px/);   // the looks Ethan named as machine-made
});

test('nothing is called safe or clean, and no em-dash is written', () => {
  for (const [name, text] of [['index.html', PAGE], ['next.js', JS], ['next.css', CSS]]) {
    assert.doesNotMatch(text.replace(/env\(safe-area-inset-bottom\)/g, ''), /\b(safe|clean|safely|cleaner)\b/i, name);   // the phone's inset is CSS's own word
    assert.doesNotMatch(text, /—/, name);
  }
  assert.match(JS, /Sewage spill risk <b>\$\{a\.score\}<\/b> of 100/);   // the 0 to 100 figure's one name
  assert.match(JS, /not a safety check/);
});

test('a low day: the level, its noun, what to do and the live status with its time', () => {
  const s = spot(['low', 'low', 'low', 'low', 'low']), d = data([s]), a = N.answer(s, DAYS[0], d, NOW);
  assert.equal(a.kicker, 'Today, Friday 20 November');
  assert.equal(a.head, 'Low risk from sewage spills');
  assert.equal(a.score, 5);
  assert.equal(a.act, L.ACTION.low);
  assert.match(a.live, /^Live status from all 10 overflows upstream: none spilling at the last poll \(Fri 12:19\)$/);
  assert.equal(N.lowestWords(s), 'Low risk on all five days.');
  assert.ok(a.notes[0].startsWith('This forecast counts sewage from the monitored storm overflows upstream'));
});

test('a very high day says to avoid it and names the lowest of the five', () => {
  const s = spot(['very high', 'high', 'moderate', 'low', 'low']), d = data([s]), a = N.answer(s, DAYS[0], d, NOW);
  assert.equal(a.head, 'Very high risk from sewage spills');
  assert.equal(a.cls, 'lv-veryhigh');
  assert.equal(a.act, 'Avoid swimming here today: choose a lower day or spot.');
  assert.equal(N.lowestWords(s), 'Lowest of the five days: Monday and Tuesday, low risk.');
  assert.equal(N.answer(s, DAYS[3], d, NOW).head, 'Low risk from sewage spills');
  assert.equal(N.answer(s, DAYS[3], d, NOW).live, '');   // the live status is today's, never a later day's
});

test("each day's level is levels.js's own, with the names and their order kept", () => {
  const s = spot(['moderate', 'very high', 'low', 'high', null], {classification: null}), d = data([s]);
  const rows = N.dayRows(s);
  assert.deepEqual(rows.map(r => r.level), ['moderate', 'very high', 'low', 'high', null]);
  for (const r of rows.filter(r => r.level)) assert.equal(r.level, L.dayLevel(s, r.date));
  assert.deepEqual(rows.map(r => r.score), [20, 80, 5, 50, null]);
  assert.deepEqual(['low', 'moderate', 'high', 'very high'].map(l => N.levelWords(l)), ['Low risk', 'Moderate risk', 'High risk', 'Very high risk']);
});

test('missing data is said as missing', () => {
  const s = spot(['low', 'low', null, 'low', 'low']), d = data([s]), a = N.answer(s, DAYS[2], d, NOW);
  assert.equal(a.head, 'No forecast for this day');
  assert.equal(a.score, null);
  assert.equal(N.lowestWords(s), 'Low risk on all four days.');   // counts only the days with a level
  const part = spot(['low', 'low', 'low', 'low', 'low']); part.days[1].rain_missing_share = 0.3;
  assert.match(N.answer(part, DAYS[1], data([part]), NOW).facts.find(f => f[0] === 'Rain')[1], /Part of the rain data for this day is missing\./);
});

test('official advice comes before the forecast, and no day is offered under it', () => {
  const s = spot(['low', 'low', 'low', 'low', 'low'], {official: NOTICE}), d = data([s]), o = N.official(s), a = N.answer(s, DAYS[0], d, NOW);
  assert.equal(o.title, 'Official advice');
  assert.equal(o.first, "Follow this advice first. It is not SwimSignal's, and the forecast below does not include it.");
  assert.equal(o.items[0].checked, 'Not re-checked since 26 Oct 2026.');
  assert.equal(a.act, 'Follow the official advice above first.');
  assert.equal(N.lowestWords(s), '');
  // On the page the notice is drawn before the answer.
  assert.ok(JS.indexOf('${notice}') > 0 && JS.indexOf('${notice}') < JS.indexOf('<div class="answer'));
  // And among other places it is never in the low group, whatever its level.
  const e = N.elsewhere([s, spot(['low', 'low', 'low', 'low', 'low'], {id: 'b', lat: 53.95})], {lat: 53.9, lon: -1.7}, DAYS[0]);
  assert.deepEqual(e.advice.map(r => r.id), ['a']);
  assert.deepEqual(e.low.map(r => r.id), ['b']);
});

test('no monitored overflow found upstream is its own answer, never low', () => {
  const s = tarn(), d = data([s]), a = N.answer(s, '2026-11-20', d, NOW);
  assert.equal(a.head, 'No monitored overflow found upstream');
  assert.equal(a.cls, 'lv-none');
  assert.equal(a.score, null);
  assert.ok(a.notes.includes(L.OTHER_RISKS) && a.notes.includes(L.ISOLATED_WHY));
  assert.equal(N.lowestWords(s), '');
  const e = N.elsewhere([s, spot(['low', 'low', 'low', 'low', 'low'])], {lat: 53.9, lon: -1.7}, DAYS[0]);
  assert.deepEqual(e.plain.map(r => r.id), ['tarn']);
  assert.equal(e.plain[0].words, 'No monitored overflow found upstream');
  assert.ok(!e.low.some(r => r.id === 'tarn'));
});

test('a low forecast with no live reading leads with that, and is called modelled', () => {
  const s = spot(['low', 'low', 'low', 'low', 'low'], {now: {label: 'low', risk: 0, discharging_upstream: 0, monitored_upstream: 0}}), d = data([s]);
  const a = N.answer(s, DAYS[0], d, NOW);
  assert.equal(a.lead, L.LIVE_NONE);
  assert.equal(a.modelled, L.MODELLED_FROM + '.');
});

test('a water rated poor: high on every day, the rating named, no lowest day offered as low', () => {
  const s = spot(['low', 'low', 'low', 'low', 'low'], {source: 'designated', classification: {class: 'poor', year: 2025, url: 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=uke4100-08901'}});
  const d = data([s]), a = N.answer(s, DAYS[0], d, NOW);
  assert.equal(a.head, 'High risk');
  assert.equal(a.sub, 'Rated poor');
  assert.equal(N.lowestWords(s), 'Rated poor, so every day here is at least high risk.');
  assert.equal(a.unchecked.text, "Today's official advice was not checked.");
});

test('a feed over six hours old stops counting as a live reading', () => {
  const s = spot(['low', 'low', 'low', 'low', 'low'], {now: {label: 'low', risk: 0, discharging_upstream: 0, monitored_upstream: 10, monitored_weight: 5, upstream_weight: 5,
    quiet_by_feed: [{company: 'Yorkshire Water', overflows: 10, updated_at: '2026-11-20T06:00:00+00:00', weight: 5}]}});
  N.ageSpot(s, NOW);
  assert.equal(s.now.monitored_upstream, 0);
  const c = {status: 0, data_state: 'live', feed_updated_at: '2026-11-20T06:00:00+00:00'};
  assert.equal(N.markOf(c, NOW), 'unknown');
  assert.match(N.statusSaid(c, NOW), /^not discharging at 20 Nov, 06:00, over six hours ago, so not current$/);
  assert.equal(N.markOf({status: 0, data_state: 'live', feed_updated_at: '2026-11-20T12:00:00+00:00'}, NOW), 'quiet');
  assert.equal(N.markOf({status: -1, data_state: 'offline'}, NOW), 'unknown');   // never drawn as dry
  assert.equal(N.markOf({status: 1, data_state: 'live'}, NOW), 'spilling');
});

test('the line upstream: nearest first, other listed places as stops, and what has no figure left out of the sum', () => {
  const s = spot(['low', 'low', 'low', 'low', 'low']), above = spot(['moderate', 'low', 'low', 'low', 'low'], {id: 'up', name: 'River Aire, Higher', downstream: [['a', 6.5]]});
  data([s, above]);
  const up = [{site_id: 'B', site_name: 'FAR/CSO', company: 'Yorkshire Water', receiving_watercourse: 'Eller Beck', distance_km: 12, travel_h: 17, status: 1, data_state: 'live', spill_hours: 100, lta_spills: 20, weight: 0.4},
    {site_id: 'A', site_name: 'NEAR/CSO', company: 'Yorkshire Water', receiving_watercourse: 'River Aire', distance_km: 0.5, travel_h: 0.6, status: 0, data_state: 'live', feed_updated_at: '2026-11-20T12:00:00+00:00', spill_hours: null, weight: 0.9}];
  const line = N.riverLine(s, up, {contributors: [{site_id: 'A', p_spill_days: [0.013]}]}, [s, above], NOW);
  assert.deepEqual(line.items.map(i => i.id), ['A', 'up', 'B']);
  assert.equal(line.items[0].where.replace(/\u00a0/g, ' '), '0.5 km upstream, under an hour away');   // levels.js keeps the figure and its unit together
  assert.equal(line.items[0].chance, 0.013);
  assert.equal(line.items[1].kind, 'place');
  assert.equal(line.items[1].level, 'Moderate risk');
  assert.equal(line.items[2].into, 'Eller Beck');
  assert.equal(line.items[2].mark, 'spilling');
  assert.deepEqual([line.total, line.spilling, line.unknown], [2, 1, 0]);
  assert.deepEqual(line.hours, {sum: 100, of: 1});
  assert.ok(N.gapPx(30) > N.gapPx(1) && N.gapPx(500) <= 120);
});

test('finding a place: by name, by postcode, by town, and the address of each view', () => {
  const spots = [spot(['low'], {id: 'a'}), spot(['low'], {id: 'w', name: 'Windermere, Millerground', river: 'Windermere', area: 'Cumbria and the Lake District', lat: 54.39, lon: -2.92})];
  assert.deepEqual(N.findSpots(spots, 'winder').map(p => p.id), ['w']);
  assert.deepEqual(N.findSpots(spots, 'aire yorkshire').map(p => p.id), ['a']);
  assert.deepEqual(N.postcodeKeys('ls29 9bz'), {district: 'LS29', sector: 'LS29 9'});
  assert.deepEqual(N.postcodeKeys('LS29'), {district: 'LS29', sector: null});
  assert.equal(N.postcodeKeys('Ilkley'), null);
  assert.deepEqual(N.findTowns([['Ilkley', 53.93, -1.82], ['Ilkeston', 52.97, -1.31]], 'ilkl').map(t => t.name), ['Ilkley']);
  assert.equal(N.milesSaid(9.7, 'north-west'), '6 miles north-west');
  assert.equal(N.milesSaid(0.5), 'under a mile');
  assert.deepEqual(N.parseHash(''), {screen: 'find', explicit: false});
  assert.deepEqual(N.parseHash('#/find'), {screen: 'find', explicit: true});
  assert.deepEqual(N.parseHash('#/a/upstream'), {screen: 'place', id: 'a', view: 'upstream', day: null});
  assert.deepEqual(N.parseHash('#/a?d=2026-11-21'), {screen: 'place', id: 'a', view: 'when', day: '2026-11-21'});
  assert.equal(N.hashFor('a', 'elsewhere', '2026-11-21'), '#/a/elsewhere?d=2026-11-21');
  assert.equal(N.hashFor('a'), '#/a');
});

test('an old forecast says so', () => {
  const d = {generated_at: GEN};
  assert.deepEqual(N.issuedWords(d, NOW), {text: 'Issued Fri 12:24, 2 h ago.', stale: false, note: ''});
  const late = N.issuedWords(d, NOW + 9 * 3600e3);
  assert.ok(late.stale && /11 h old, older than usual/.test(late.note));
});
