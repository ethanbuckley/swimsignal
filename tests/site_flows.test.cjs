// "Too high to swim" (roadmap task 8): the sentence under a spot's headline when its river is high
// or rising fast at a gauge on its own river, or a flood alert is in force nearby, from the fields
// build_site.attach_flow_state writes (tests/test_flows.py checks those). Never from a stale reading.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {flowFacts, flowSentence, evidenceRows, floodUnchecked, floodUncheckedLine} = require('../src/dipcast/site/experience.js');
const prerender = require('../scripts/prerender_spots.js');

const NOW = Date.parse('2026-10-03T13:30:00Z'), BUILT = '2026-10-03T14:05:00+01:00';
const gauge = (extra = {}) => ({station: 'Addingham', river: 'River Wharfe', level_m: 2.1, typical_low_m: 0.189, typical_high_m: 1.87,
  index: 1.14, label: 'very high', observed_at: '2026-10-03T13:15:00Z', age_hours: 0.3, stale: false, same_river: true, ...extra});
const ALERT = {severity_level: 3, severity: 'Flood alert', area: 'River Wharfe at Ilkley', area_id: '123WAF456',
  url: 'https://check-for-flooding.service.gov.uk/target-area/123WAF456', raised: '2026-10-03T09:20:22'};
const say = (s, now = NOW, built = BUILT) => flowFacts(s, now, built).map(f => flowSentence(f)).join(' ');

test('a river above its usual range says so, naming the gauge', () => {
  assert.equal(say({flow_state: 'high', river_state: gauge()}), 'River high: the gauge at Addingham is above its usual range.');
});

test('no spot shows "River high" from a stale reading', () => {
  // Stale when the build read it (attach_river_levels clears the level and marks it).
  assert.equal(say({flow_state: 'high', river_state: gauge({stale: true, level_m: null, index: null, label: 'unknown'})}), '');
  // Current when built, but over a day old by the time the page is read.
  assert.equal(say({flow_state: 'high', river_state: gauge()}, NOW + 25 * 36e5, null), '');
  // A build over a day old says nothing of the river or the floods.
  assert.equal(say({flow_state: 'high', river_state: gauge(), flood_alerts: [ALERT]}, NOW + 26 * 36e5), '');
  // No time on the reading: not current.
  assert.equal(say({flow_state: 'high', river_state: gauge({observed_at: null})}), '');
});

test('a fast rise gives the measured rise and the times it ran between, and only for six hours', () => {
  const s = {flow_state: 'rising fast', river_state: gauge({level_m: 0.6, index: 0.24, label: 'normal', rise_6h_m: 0.4,
    rise_from: '2026-10-03T07:45:00Z', rise_to: '2026-10-03T13:30:00Z'})};
  assert.equal(say(s), 'River rising fast: the gauge at Addingham rose 0.40 m between 08:45 and 14:30.');   // UK time
  assert.equal(say(s, NOW + 7 * 36e5), '');   // the last reading in the rise is over six hours old
  assert.equal(say({...s, river_state: {...s.river_state, rise_6h_m: undefined}}), '');
});

test('a spot with a live flood alert in the fixture shows the sentence, and the page puts it under the headline', () => {
  const s = {flow_state: null, river_state: null, flood_alerts: [ALERT]};
  assert.equal(say(s), 'Flood alert in force nearby (Environment Agency): River Wharfe at Ilkley.');
  const two = {...s, flood_alerts: [{...ALERT, severity_level: 2, severity: 'Flood warning', area: 'River Wharfe at Burley'}, ALERT]};
  assert.equal(say(two), 'Flood warning in force nearby (Environment Agency): River Wharfe at Burley and 1 more.');
  assert.equal(say({flood_alerts: []}) + say({}), '');
  // The EA did not answer (null): said, never left to read as none in force.
  assert.equal(say({flood_alerts: null}), '');   // a failed check is not a hazard: the quiet line under the level tile says it (below)
  // The page's own line (index.html, flowLine), run on the same fixture.
  const page = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  const src = page.slice(page.indexOf('const flowLine = '), page.indexOf('\n', page.indexOf('A separate hazard, not part of the pollution level.')));
  const ctx = vm.createContext({flowFacts, flowSentence, DATA: {generated_at: BUILT}, Date: {now: () => NOW}});
  vm.runInContext(src + '\nthis.flowLine = flowLine;', ctx);
  assert.equal(ctx.flowLine(s), '<p class="flow"><b>Flood alert in force nearby</b> (Environment Agency): '
    + '<a href="https://check-for-flooding.service.gov.uk/target-area/123WAF456">River Wharfe at Ilkley</a>. A separate hazard, not part of the pollution level.</p>');
  assert.equal(ctx.flowLine({flow_state: 'high', river_state: gauge(), flood_alerts: [ALERT]}).match(/<b>/g).length, 2);   // both, river first
  assert.equal(ctx.flowLine({flow_state: null, flood_alerts: []}), '');
  assert.equal(ctx.flowLine({flow_state: null, flood_alerts: null}), '');   // no bold line in the answer for a check that failed
  assert.ok(page.includes('flowLine(d) + `<p class="issued">'), 'the line sits in the answer, before the issue time');
});

test('names from the feed are escaped in the page and plain in the comparison', () => {
  const s = {flood_alerts: [{...ALERT, area: 'Beck <b>&</b> "Brook"', url: 'https://check-for-flooding.service.gov.uk/target-area/X"onmouseover="y'}]};
  const html = flowFacts(s, NOW, BUILT).map(f => flowSentence(f, true)).join(' ');
  assert.ok(html.includes('Beck &lt;b&gt;&amp;&lt;/b&gt; &quot;Brook&quot;') && !html.includes('"onmouseover'));
  const built = new Date().toISOString();   // the comparison reads the clock
  const rows = Object.fromEntries(evidenceRows({days: [], ...s}, '2026-10-03', '', built));
  assert.match(rows['Local warnings'], /^Flood alert in force nearby \(Environment Agency\): Beck <b>&<\/b> "Brook"\. Short-term pollution warnings are not fetched/);
  assert.equal(Object.fromEntries(evidenceRows({days: []}, '2026-10-03', '', built))['Local warnings'],
    'Short-term pollution warnings are not fetched by this app. Check official advice and signs at the water.');
});

// 16 Oct 2026: "Flood alerts not checked" in bold above the five days on 48 of 105 pages read like a
// hazard. Now a quiet line under the River or Lake level tile (or Weather, with no gauge), and nothing
// in the answer. The facts and tiles are index.html's own, run as scripts/prerender_spots.js runs them.
function tiles(spot, now = NOW) {
  const store = {getItem: () => null, setItem() {}, removeItem() {}}, root = 'https://example.org/swim/';
  const ctx = vm.createContext({console, URL, URLSearchParams, Intl, history: {state: null}, location: new URL(root),
    navigator: {onLine: true}, localStorage: store, sessionStorage: store, addEventListener() {}, setTimeout, clearTimeout,
    ROOT: new URL(root), map: null, TOUCH: false, STILL: false});
  ctx.window = ctx;
  vm.runInContext(`Date.now = () => ${now};`, ctx);
  for (const f of ['eatoday.js', 'experience.js', 'levels.js', 'lists.js'])
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site', f), 'utf8'), ctx);
  const page = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  vm.runInContext(prerender.reached(page, ['facts', 'tile'], ['ROOT', 'map', 'TOUCH', 'STILL']), ctx);
  vm.runInContext('setToday("2026-10-03");', ctx);
  ctx.S = spot; ctx.DATA_IN = {generated_at: BUILT, spots: [spot]};
  vm.runInContext('DATA = DATA_IN;', ctx);
  return vm.runInContext('facts(S).map(o => [o.label, tile(o)])', ctx);
}
const DAYS = ['2026-10-03', '2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07'];
const river = (extra = {}) => ({id: 'w', name: 'Wharfe', kind: 'river', source: 'curated', upstream_summary: {overflows: 3},
  location: {mode: 'river'}, now: {label: 'low', discharging_upstream: 0}, contributors: [],
  assumptions: {max_upstream_km: 60, recent_spill_hours: 48},
  river_state: gauge({distance_km: 1.2, flow_state: null, rloi: '8001'}), flow_state: null,
  weather: {days: DAYS.map(date => ({date, tmax: 14, sunrise: '07:20', sunset: '18:20'}))},
  days: DAYS.map(date => ({date, risk: 0.01, label: 'low'})), ...extra});
const QUIET = '<p class="t-note">Flood warnings not checked for this forecast. '
  + '<a href="https://check-for-flooding.service.gov.uk/">See the Environment Agency</a>.</p>';

test('flood alerts the EA did not answer: a quiet line under the River level tile, nothing in the answer', () => {
  const t = tiles(river({flood_alerts: null}));
  const level = t.find(([label]) => label === 'River level')[1];
  assert.ok(level.includes(QUIET), level);
  assert.equal(t.filter(([, h]) => h.includes('t-note')).length, 1);   // once, on that tile only
  assert.ok(!level.includes('<b>'));
  // The answer and the five days, as the build writes them: no "not checked", bold or otherwise.
  const top = prerender.prerender({generated_at: BUILT, spots: [river({flood_alerts: null})]}, 'https://example.org/swim/').w;
  assert.ok(!/not checked|Flood/.test(top), top);
  // Checked, with nothing in force: no line.
  assert.ok(tiles(river({flood_alerts: []})).every(([, h]) => !h.includes('t-note')));
  // A page read over a day after its build says nothing of the check.
  assert.ok(tiles(river({flood_alerts: null}), NOW + 26 * 36e5).every(([, h]) => !h.includes('t-note')));
});

test('a lake keeps the line under Lake level, and a spot with no gauge under Weather', () => {
  const lake = river({kind: 'lake', location: {mode: 'lake'}, upstream_summary: {overflows: 0}, flood_alerts: null,
    river_state: gauge({distance_km: 0.4, water: 'lake', river: 'Windermere', station: 'Far Sawrey'})});
  assert.ok(tiles(lake).find(([label]) => label === 'Lake level')[1].includes(QUIET));
  const ungauged = tiles(river({river_state: null, flood_alerts: null}));
  assert.ok(!ungauged.some(([label]) => /level/.test(label)));
  assert.ok(ungauged.find(([label]) => label === 'Weather')[1].includes(QUIET));
});

test('the quiet line in words: the comparison row says it plainly; a spot without the field says nothing', () => {
  assert.equal(floodUnchecked({flood_alerts: null}, NOW, BUILT), true);
  assert.equal(floodUnchecked({flood_alerts: []}, NOW, BUILT), false);
  assert.equal(floodUnchecked({}, NOW, BUILT), false);   // an unlisted point: never asked
  assert.equal(floodUnchecked({flood_alerts: null}, NOW + 26 * 36e5, BUILT), false);
  assert.equal(floodUncheckedLine(), 'Flood warnings not checked for this forecast. See the Environment Agency: https://check-for-flooding.service.gov.uk/');
  const built = new Date().toISOString();   // the comparison reads the clock
  assert.equal(Object.fromEntries(evidenceRows({days: [], flood_alerts: null}, '2026-10-03', '', built))['Local warnings'],
    'Flood warnings not checked for this forecast. See the Environment Agency: https://check-for-flooding.service.gov.uk/ '
    + 'Short-term pollution warnings are not fetched by this app. Check official advice and signs at the water.');
});
