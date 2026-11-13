// Today, the home page (11 Nov 2026; docs/DESIGN.md, "Today: the home page"). With spots saved it opens on what they
// say: a title that counts the saved spots at moderate risk or higher on the day shown, a line that names those levels
// and the day they are all forecast low, and the spills the water companies reported upstream in the last 48 hours.
// A first visit gets the day's count of the listed spots by level and the spots at very high risk. Nothing here
// changes a level: the title counts the cards' own words, and the count is overview()'s.
// node --test tests/site_today_home.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const spots = require('../scripts/prerender_spots.js');

const ROOT = path.join(__dirname, '..');
const PAGE = fs.readFileSync(path.join(ROOT, 'src/dipcast/site/index.html'), 'utf8');
// Wednesday 11 November 2026, issued 06:56: Saturday is the fourth of the five days. November, so London's clock is UTC's.
const GEN = '2026-11-11T06:56:11+00:00', NOW = Date.parse(GEN);
const DAYS = ['2026-11-11', '2026-11-12', '2026-11-13', '2026-11-14', '2026-11-15'];
const RISK = {low: 0.03, moderate: 0.2, high: 0.5, 'very high': 0.72};
const PROFILE = 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj2310-11945';
const notice = {line: 'Environment Agency: advice against bathing (harmful algae) since 19 Jun 2026', publisher: 'Environment Agency',
  link: PROFILE, since: '2026-06-19', checked: '2026-11-11', state: 'checked', restricts: true};
const spot = (id, name, labels, extra = {}) => ({id, name, kind: 'river', source: 'curated', area: 'South West', lat: 50.4, lon: -3.7,
  upstream_summary: {overflows: 4}, location: {mode: 'river'}, contributors: [], assumptions: {max_upstream_km: 60, recent_spill_hours: 48},
  now: {label: 'low', risk: 0, discharging_upstream: 0, recent_upstream: 0, monitored_upstream: 4, monitored_weight: 1, upstream_weight: 1},
  days: DAYS.map((date, i) => ({date, label: labels[i], risk: RISK[labels[i]], expected_spilling_overflows: 0, rain_48h_mm: 1})), ...extra});
const five = l => [l, l, l, l, l];
const DART = spot('dart', 'River Dart, Dartington Pontoon', ['very high', 'high', 'moderate', 'low', 'low']);
const SPITCH = spot('spitch', 'River Dart, Spitchwick', ['moderate', 'moderate', 'low', 'low', 'low']);
const SHARRAH = spot('sharrah', 'River Dart, Sharrah Pool', ['moderate', 'moderate', 'low', 'low', 'low']);
const CADOVER = spot('cadover', 'River Plym, Cadover Bridge', five('low'), {upstream_summary: {overflows: 0},
  now: {label: 'low', risk: 0, discharging_upstream: 0, recent_upstream: 0, monitored_upstream: 0}});
const LOW1 = spot('low1', 'River Barle, Tarr Steps', five('low')), LOW2 = spot('low2', 'River Teign, Fingle Bridge', five('low'));
const ALGAE = spot('algae', 'Frensham Great Pond', five('low'), {kind: 'lake', source: 'designated', location: {mode: 'lake'},
  classification: {class: 'excellent', year: 2025, url: PROFILE}, official: [notice]});
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();

function page(all = [DART, SPITCH, SHARRAH, CADOVER]) {
  const store = {getItem: () => null, setItem() {}, removeItem() {}}, root = 'https://example.org/swim/';
  const ctx = vm.createContext({console, URL, URLSearchParams, Intl, history: {state: null}, location: new URL(root),
    navigator: {onLine: true}, localStorage: store, sessionStorage: store, addEventListener() {}, setTimeout, clearTimeout,
    ROOT: new URL(root), map: null, TOUCH: false, STILL: false});
  ctx.window = ctx;
  vm.runInContext(`Date.now = () => ${NOW};`, ctx);
  for (const f of ['eatoday.js', 'experience.js', 'levels.js', 'lists.js'])
    vm.runInContext(fs.readFileSync(path.join(ROOT, 'src/dipcast/site', f), 'utf8'), ctx);
  vm.runInContext(spots.reached(PAGE, ['homeHead', 'homeYours', 'homeNow', 'homeWorst', 'upstreamFeed', 'homeFeed', 'overview'],
    ['ROOT', 'map', 'TOUCH', 'STILL']), ctx);
  ctx.SPOTS = all;
  vm.runInContext(`setToday("${DAYS[0]}"); DATA = {generated_at: "${GEN}", spots: SPOTS}; VIEW.day = "${DAYS[0]}";`, ctx);
  return ctx;
}
const call = (ctx, f, ...a) => vm.runInContext(f, ctx)(...a);

test('the title counts the saved spots at moderate risk or higher, and the line names their levels and the day they are all low', () => {
  const ctx = page();
  assert.deepEqual({...call(ctx, 'homeHead', [DART, SPITCH, SHARRAH, CADOVER], DAYS[0])}, {head: 'Raised risk today at 3 of your 4 saved spots',
    sub: '1 at very high risk, 2 at moderate risk. All 3 are forecast low risk by Saturday.'});
  assert.deepEqual({...call(ctx, 'homeHead', [DART, SPITCH], DAYS[0])}, {head: 'Raised risk today at both of your saved spots',
    sub: '1 at very high risk, 1 at moderate risk. Both are forecast low risk by Saturday.'});
  // One saved spot: its card says the level, so the line gives only the day it is forecast low.
  assert.deepEqual({...call(ctx, 'homeHead', [SPITCH], DAYS[0])}, {head: 'Raised risk today at your saved spot', sub: 'It is forecast low risk by Friday.'});
  // A day picked: the title is that day's, and "by" looks only at the days after it.
  assert.deepEqual({...call(ctx, 'homeHead', [DART, SPITCH, SHARRAH, CADOVER], DAYS[2])}, {head: 'Raised risk on Friday at 1 of your 4 saved spots',
    sub: '1 at moderate risk. It is forecast low risk by Saturday.'});
  assert.equal(call(ctx, 'homeHead', [DART, SPITCH], DAYS[1]).sub, '1 at high risk, 1 at moderate risk. Both are forecast low risk by Saturday.');
  // The last of the five days, still raised: no day to name.
  const stuck = spot('stuck', 'River Avon, Barton Farm', five('high'));
  assert.deepEqual({...call(ctx, 'homeHead', [stuck, LOW1], DAYS[0])}, {head: 'Raised risk today at 1 of your 2 saved spots', sub: '1 at high risk.'});
});

test('"low risk" is said only when every saved spot has that level and none is under advice restricting swimming', () => {
  const ctx = page();
  assert.deepEqual({...call(ctx, 'homeHead', [LOW1, LOW2], DAYS[0])}, {head: 'Low risk today at both of your saved spots', sub: ''});
  assert.equal(call(ctx, 'homeHead', [LOW1, LOW2, SPITCH], DAYS[3]).head, 'Low risk on Saturday at all 3 of your saved spots');
  assert.equal(call(ctx, 'homeHead', [LOW1], DAYS[0]).head, 'Low risk today at your saved spot');
  // No monitored overflow found upstream is not a low level: the title says only that none is raised.
  assert.deepEqual({...call(ctx, 'homeHead', [LOW1, CADOVER], DAYS[0])}, {head: 'No raised risk today at your 2 saved spots', sub: ''});
  assert.equal(call(ctx, 'homeHead', [CADOVER], DAYS[0]).head, 'No raised risk today at your saved spot');
  // Low for sewage, under the Environment Agency's advice against bathing: never "low risk", and the notice comes first.
  assert.deepEqual({...call(ctx, 'homeHead', [LOW1, ALGAE], DAYS[0])}, {head: 'No raised risk today at your 2 saved spots',
    sub: '1 has an official notice: follow it first.'});
  assert.equal(call(ctx, 'homeHead', [ALGAE], DAYS[0]).sub, 'It has an official notice: follow it first.');
  assert.equal(call(ctx, 'homeHead', [DART, ALGAE], DAYS[0]).sub, '1 at very high risk. It is forecast low risk by Saturday. 1 has an official notice: follow it first.');
  for (const xs of [[DART, SPITCH, CADOVER], [LOW1, ALGAE], [CADOVER]]) for (const d of DAYS) {
    const y = call(ctx, 'homeHead', xs, d);
    assert.doesNotMatch(y.head + ' ' + y.sub, /\b(safe|clean|clear)\b/i);
  }
});

test('the line the page shows ends with when the forecast was issued', () => {
  const ctx = page();
  assert.deepEqual({...call(ctx, 'homeYours', [DART, SPITCH, SHARRAH, CADOVER])}, {head: 'Raised risk today at 3 of your 4 saved spots',
    lede: '1 at very high risk, 2 at moderate risk. All 3 are forecast low risk by Saturday. Updated\u00a0Wed\u00a006:56.'});
  assert.equal(call(ctx, 'homeYours', [LOW1, LOW2]).lede, 'Updated\u00a0Wed\u00a006:56.', 'the time does not break across lines');
});

// South West Water's record on 11 Nov 2026, above Dartington Pontoon (data/spot/osm-dart-dartington.json).
const ov = (site_id, site_name, km, start, end, extra = {}) => ({site_id, company: 'South West Water', site_name, receiving_watercourse: 'RIVER DART',
  status: 0, has_live: true, distance_km: km, lake_distance_km: 0, travel_h: km / 0.72, latest_event_start: start, latest_event_end: end, ...extra});
const KILBURY = ov('SBB00179', 'KILBURY STW_SO_BUCKFASTLEIGH', 10.2, '2026-11-10T09:30:40+00:00', '2026-11-10T09:52:39+00:00');
const PEAR = ov('SBB00917', 'PEAR TREE CROSS_CSO_ASHBURTON', 14.1, '2026-11-10T07:08:05+00:00', '2026-11-10T07:10:05+00:00');
const DARTC = ov('SBB00350', 'DARTINGTON C_CSO_DARTINGTON', 1.2, '2026-11-09T14:06:05+00:00', '2026-11-09T14:10:05+00:00');
const STAVERTON = ov('SBB01166', 'STAVERTON STW_SSO_STAVERTON', 3.4, '2026-03-13T00:23:21+00:00', '2026-03-13T02:23:01+00:00');

test('upstream of the saved spots: the spills reported in the last 48 hours, newest first, each once at its nearest spot', () => {
  const ctx = page();
  const dart = {...DART, contributors: [KILBURY, STAVERTON, DARTC, PEAR]};
  // The same works above a second saved spot, nearer: one row, at that spot, which says the other shares it.
  const totnes = {...spot('totnes', 'River Dart, Totnes Weir', five('low')), contributors: [{...KILBURY, distance_km: 8.0}]};
  const rows = call(ctx, 'upstreamFeed', [dart, totnes], NOW);
  assert.deepEqual(Array.from(rows, x => [x.c.site_id, x.s.id, x.more]), [['SBB00179', 'totnes', 1], ['SBB00917', 'dart', 0], ['SBB00350', 'dart', 0]]);
  const h = call(ctx, 'homeFeed', [dart], NOW), t = text(h);
  assert.match(h, /^<h2 class="t-lab" id="feed-h">/);
  assert.match(t, /^Upstream of your saved spot, last 48 hours /);
  assert.match(t, /Tue 09:30 Kilbury, Buckfastleigh sewage works overflow spilled for 22 minutes\. 10\.2 km upstream of River Dart, Dartington Pontoon /);
  assert.match(t, /Tue 07:08 Pear Tree Cross, Ashburton storm overflow spilled for 2 minutes\. 14\.1 km upstream of River Dart, Dartington Pontoon /);
  assert.match(t, /Mon 14:06 Dartington C storm overflow spilled for 4 minutes\. 1\.2 km upstream of River Dart, Dartington Pontoon /);
  assert.doesNotMatch(t, /Staverton/, 'a spill in March is not in the last 48 hours');
  assert.match(h, /<a href="[^"]*spot\/dart\/" data-id="dart">/, 'a row opens its spot');
  assert.match(text(call(ctx, 'homeFeed', [dart, totnes], NOW)), /8\.0 km upstream of River Dart, Totnes Weir and 1 more of your saved spots /);
  assert.match(t, /The water companies' own reports, for the ten overflows that count most at each saved spot\. A monitor that is off reports nothing\.$/);
});

test('an overflow discharging now comes first and says so; with nothing reported, the tile says "reported", not that nothing spilled', () => {
  const ctx = page();
  const now = {...STAVERTON, status: 1, latest_event_start: '2026-11-11T05:40:00+00:00', latest_event_end: null};
  const dart = {...DART, contributors: [KILBURY, now]};
  assert.deepEqual(Array.from(call(ctx, 'upstreamFeed', [dart], NOW), x => x.c.site_id), ['SBB01166', 'SBB00179']);
  assert.match(text(call(ctx, 'homeFeed', [dart], NOW)), /Wed 05:40 Staverton sewage works storm tank overflow is spilling now\. 3\.4 km upstream of /);
  const quiet = text(call(ctx, 'homeFeed', [{...DART, contributors: [STAVERTON]}, {...SPITCH, contributors: []}], NOW));
  assert.match(quiet, /^Upstream of your saved spots, last 48 hours No spill reported in the last 48 hours by the overflows that count most upstream\. /);
  assert.doesNotMatch(quiet, /\b(safe|clean|clear)\b/i);
  // Longer spills are said in hours, then days; a start after the forecast was issued is not shown as past.
  const long = {...KILBURY, latest_event_start: '2026-11-10T01:00:00+00:00', latest_event_end: '2026-11-11T00:13:00+00:00'};
  assert.match(text(call(ctx, 'homeFeed', [{...DART, contributors: [long]}], NOW)), /spilled for about 23 hours\./);
  const ahead = {...KILBURY, latest_event_start: '2026-11-11T09:00:00+00:00', latest_event_end: '2026-11-11T09:05:00+00:00'};
  assert.equal(call(ctx, 'upstreamFeed', [{...DART, contributors: [ahead]}], NOW).length, 0);
});

test("a first visit's count is the list's own: the figures add up to the spots, and low is the day strip's count", () => {
  const all = [DART, SPITCH, SHARRAH, CADOVER, LOW1, LOW2, ALGAE];
  const ctx = page(all), h = call(ctx, 'homeNow', all), t = text(h);
  assert.match(t, /^Today across the 7 spots 2 at low risk 2 at moderate risk 1 at high or very high risk 1 with no monitored overflow found upstream /);
  assert.match(t, /1 more at low risk is under official advice restricting swimming\.$/);
  assert.match(call(ctx, 'overview', all), /Pollution risk: 2 low, and 1 more at low under official advice restricting swimming · 2 moderate · 1 high or very high · 1 with no monitored overflow found upstream\./);
  // The bar's parts are the same counts, in the level's own classes.
  assert.deepEqual([...h.matchAll(/<i class="(\w+)" style="flex:(\d+) 1 0"><\/i>/g)].map(m => [m[1], +m[2]]),
    [['low', 2], ['moderate', 2], ['veryhigh', 1], ['clear', 1], ['na', 1]]);
  vm.runInContext(`VIEW.day = "${DAYS[3]}";`, ctx);
  assert.match(text(call(ctx, 'homeNow', all)), /^Saturday across the 7 spots 5 at low risk 1 with no monitored overflow found upstream /);
});

test('the spots at very high risk on the day shown, two at most, as rows of the list', () => {
  const avon = spot('avon', 'River Avon, Barton Farm Country Park', ['very high', 'very high', 'high', 'moderate', 'low']);
  const third = spot('third', 'River Tone, French Weir', five('very high'));
  const ctx = page([DART, avon, third, LOW1]);
  const h = call(ctx, 'homeWorst', [DART, avon, third, LOW1]);
  assert.match(h, /<h2 class="t-lab" id="worst-h">.*<span>Very high risk today<\/span><\/h2>/);
  assert.equal((h.match(/<a class="row"/g) || []).length, 2);
  assert.match(text(h), /And 1 more at very high risk today\.$/);
  assert.equal(call(ctx, 'homeWorst', [LOW1, SPITCH]), '', 'none at very high risk: no tile');
  vm.runInContext(`VIEW.day = "${DAYS[1]}";`, ctx);
  assert.match(call(ctx, 'homeWorst', [DART, avon, LOW1]), /<span>Very high risk tomorrow<\/span>/);
});

test('the page: the tab is Today, the saved state is known before the first paint, and the build keeps the first visit\'s opening', () => {
  assert.match(PAGE, /<a href="\.\/" id="nav-list"><svg [^>]*>.*?<\/svg>Today<\/a>/);
  assert.doesNotMatch(PAGE, />Explore<\/a>/);
  const build = fs.readFileSync(path.join(ROOT, 'scripts/build_site.py'), 'utf8');
  assert.match(build, /<\/svg>Today<\/a>'/);
  assert.doesNotMatch(build, /<\/svg>Explore<\/a>/);
  // In the head, before the stylesheet's first paint: nothing is read but whether the saved list has an id in it.
  const head = PAGE.slice(0, PAGE.indexOf('</head>'));
  assert.match(head, /try \{ if \(\/"\/\.test\(localStorage\.getItem\('dipcast\.saved'\) \|\| ''\)\) document\.documentElement\.classList\.add\('has-saved'\); \} catch \(e\) \{\}/);
  assert.match(PAGE, /html\.has-saved #result\[data-built\] \.intro h1, html\.has-saved #result\[data-built\] \.intro \.lede \{ visibility:hidden; \}/);
  // The script's own copy of the first visit's opening is unchanged (build_site.home_lead writes the same); the saved
  // visitor's title replaces it in the same two elements, after it.
  const list = PAGE.slice(PAGE.indexOf('function renderList() {'), PAGE.indexOf('\nconst setSort = '));
  assert.ok(list.indexOf('<h1>Check the water before you go</h1>') < list.indexOf('const yours = saved.length ? homeYours(saved) : null;'));
  assert.match(list, /h = h\.replace\(\/<h1>\[\^<\]\*<\\\/h1><p class="lede">\.\*\?<\\\/p>\/, `<h1>\$\{esc\(yours\.head\)\}<\/h1><p class="lede yours">\$\{esc\(yours\.lede\)\}<\/p>`\);/);
  // The feed's tile is drawn with its heading at once (12 Nov 2026), so the list under it does not move when its files come.
  assert.match(list, /if \(saved\.length\) v \+= `<section class="group tile home-feed loading" id="home-feed" aria-labelledby="feed-h">\$\{feedHead\(saved\.length\)\}<p class="t-say muted">[^<]*<\/p><\/section>`;\n\s+else v \+= '<div id="home-first"><\/div>';/);
  // On a phone the field opens from the header's button; a search in progress keeps it open.
  assert.match(PAGE, /html\.has-saved body\.view-list:not\(\.search-open\) \.lead \.search, html\.has-saved body\.view-list:not\(\.search-open\) #geo-cta \{ display:none; \}/);
  assert.match(PAGE, /<button type="button" class="hbtn phone-only" id="searchbtn" aria-label="Find a spot" aria-expanded="false" aria-controls="q">/);
  assert.match(list, /if \(VIEW\.q\.trim\(\)\) SEARCH_OPEN = true;/);
});
