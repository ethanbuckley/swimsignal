// The live status over a level (levels.js: liveCover, liveHead, liveLine, liveParts; review of PR #463, 30 Oct
// 2026): with no overflow upstream giving a current status, every surface that shows a level leads with
// "Live sewage spill status unavailable" and calls the level the modelled forecast; with some, the counts; with
// all, the counts too. The forecast itself, the levels and the order of the list are unchanged.
// node --test tests/site_live_status.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const spots = require('../scripts/prerender_spots.js');
const L = require('../src/dipcast/site/levels.js');
const ev = require('../src/dipcast/site/evidence.js');
const Embed = require('../src/dipcast/site/embed.js');

const PAGE = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const GEN = '2026-10-30T17:49:00+00:00', NOW = Date.parse('2026-10-30T18:49:00+00:00');
const DAYS = ['2026-10-30', '2026-10-31', '2026-11-01', '2026-11-02', '2026-11-03'];
const RISK = {low: 0.03, moderate: 0.2, high: 0.5};
const spot = (total, mon, labels = ['low', 'low', 'low', 'low', 'low'], now = {}) => ({id: 'a', name: 'A river', kind: 'river', source: 'curated',
  upstream_summary: {overflows: total}, location: {mode: 'river'}, contributors: [], assumptions: {max_upstream_km: 60, recent_spill_hours: 48},
  now: {label: 'low', risk: 0, discharging_upstream: 0, recent_upstream: 0, monitored_upstream: mon, monitored_weight: mon / total, upstream_weight: 1, ...now},
  days: labels.map((l, i) => ({date: DAYS[i], label: l, risk: RISK[l], rain_48h_mm: 1}))});
// The Wye at Symonds Yat, Sandy Lane at Chester and Wharfe at Cromwheel's counts on 30 Oct 2026; and one all reporting.
const ZERO = spot(14, 0, undefined, {no_feed_upstream: 14});
const THIN = spot(13, 1, undefined, {monitored_weight: 0.05, upstream_weight: 1.9});
const MOST = spot(16, 13, undefined, {monitored_weight: 5.03, upstream_weight: 6.76});
const FULL = spot(45, 45);
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();

function page() {
  const store = {getItem: () => null, setItem() {}, removeItem() {}}, root = 'https://example.org/swim/';
  const ctx = vm.createContext({console, URL, URLSearchParams, Intl, history: {state: null}, location: new URL(root),
    navigator: {onLine: true}, localStorage: store, sessionStorage: store, addEventListener() {}, setTimeout, clearTimeout,
    ROOT: new URL(root), map: null, TOUCH: false, STILL: false});
  ctx.window = ctx;
  vm.runInContext(`Date.now = () => ${NOW};`, ctx);
  for (const f of ['eatoday.js', 'experience.js', 'levels.js', 'lists.js'])
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site', f), 'utf8'), ctx);
  vm.runInContext(spots.reached(PAGE, ['answerWords', 'savedCard'], ['ROOT', 'map', 'TOUCH', 'STILL']), ctx);
  vm.runInContext(`setToday("${DAYS[0]}"); DATA = {generated_at: "${GEN}", spots: []};`, ctx);
  return ctx;
}

test('the counts: none, some, all; nothing where there is no count or no daily forecast', () => {
  L.setToday(DAYS[0]);
  assert.deepEqual(L.liveCover(ZERO), {mon: 0, total: 14, kind: 'none'});
  assert.deepEqual(L.liveCover(THIN), {mon: 1, total: 13, kind: 'partial'});
  assert.deepEqual(L.liveCover(MOST), {mon: 13, total: 16, kind: 'partial'});
  assert.deepEqual(L.liveCover(FULL), {mon: 45, total: 45, kind: 'full'});
  assert.equal(L.liveHead(ZERO), 'Live sewage spill status unavailable');
  assert.equal(L.liveHead(THIN), 'Live status from 1 of 13 overflows upstream');
  assert.equal(L.liveHead(FULL), 'Live status from all 45 overflows upstream');
  assert.equal(L.liveCover({...FULL, now: {label: 'low'}}), null, 'an update with no count: not said either way');
  assert.equal(L.liveCover({...FULL, upstream_summary: {overflows: 0}}), null, 'nothing upstream: the plain level says so');
  assert.equal(L.liveCover({...FULL, error: 'forecast failed: x'}), null);
});

test('the levels and the order are unchanged: a missing status is never a level, and a forecast is kept', () => {
  L.setToday(DAYS[0]);
  for (const s of [ZERO, THIN, MOST, FULL]) assert.equal(L.level(s), 'low');
  const raised = spot(14, 0, ['low', 'moderate', 'low', 'low', 'low'], {no_feed_upstream: 14});
  assert.equal(L.level(raised), 'moderate', 'the modelled forecast still raises the level');
  assert.equal(L.nowUnknown(ZERO), true);
  assert.equal(L.nowUnknown(MOST), false);
});

test('the compact headline: list rows, map tooltips, saved lists, the embed, alerts and share cards', () => {
  L.setToday(DAYS[0]);
  assert.equal(L.headline(ZERO), 'Live sewage spill status unavailable: low risk forecast');
  assert.equal(L.headline(THIN), 'Live status from 1 of 13 overflows upstream: low risk forecast');
  assert.equal(L.headline(MOST), 'Low risk for the next five days', 'most of the weight reporting: right now is known, as before');
  assert.equal(L.headline(FULL), 'Low risk for the next five days');
  assert.equal(L.headline(spot(14, 0, ['low', 'moderate', 'low', 'low', 'low'], {no_feed_upstream: 14})), 'Moderate risk tomorrow: sewage spills (modelled, no live status)');
  assert.equal(L.headline(spot(16, 13, ['low', 'moderate', 'low', 'low', 'low'])), 'Moderate risk tomorrow: sewage spills');
  // The embed gives headline() as it is.
  assert.match(text(Embed.card(ZERO, {generated_at: GEN}, NOW)), /Live sewage spill status unavailable: low risk forecast/);
  // Plan a swim's evidence line, today only.
  assert.equal(ev.evidenceNowGap(ZERO, true), 'Live sewage spill status unavailable: forecast only.');
  assert.equal(ev.evidenceNowGap(THIN, true), 'Live status from 1 of 13 overflows upstream: forecast only.');
  assert.equal(ev.evidenceNowGap(FULL, true), '');
  // Every form keeps a level's noun and never says safe or clean.
  for (const s of [ZERO, THIN, MOST, FULL]) assert.doesNotMatch(L.headline(s), /\b(?:low|moderate|high)\b(?! risk)|\bsafe\b|\bclean\b/i);
});

test("the spot's answer: the live status first; with none, the level labelled as the modelled forecast and its inputs", () => {
  const ctx = page(), answer = s => vm.runInContext('answerWords', ctx)(s);
  const zero = answer(ZERO);
  assert.match(zero, /^<p class="live live-off">Live sewage spill status unavailable: none of the 14 overflows upstream reports live, so whether any is spilling is not known\.<\/p>/);
  assert.match(zero, /<\/p><p class="modelled">Modelled forecast<\/p><h2 class="big low" id="risk-headline">Low risk from sewage spills<\/h2><div class="wn"><p class="why">From the rain forecast and each overflow's past spills, not from live readings<\/p>/);
  const thin = answer(THIN);
  assert.match(thin, /^<p class="live">Live status from 1 of 13 overflows upstream: none spilling at the last poll; 12 do not report, so could be spilling unseen\.<\/p><h2 class="big low"/);
  assert.match(thin, /Modelled forecast: most of the model's weight here is on overflows that do not report live/);
  assert.doesNotMatch(thin, /class="modelled"/);
  assert.match(answer(MOST), /^<p class="live">Live status from 13 of 16 overflows upstream: none spilling at the last poll; 3 do not report, so could be spilling unseen\.<\/p><h2 /);
  assert.match(answer(FULL), /^<p class="live">Live status from all 45 overflows upstream: none spilling at the last poll\.<\/p><h2 /);
  // Said once: the line by the issue time no longer repeats the counts.
  for (const s of [ZERO, THIN, MOST, FULL]) assert.equal((text(answer(s)).match(/overflows upstream/g) || []).length, 1);
  // A later day is the rain's forecast: no live line over it.
  assert.doesNotMatch(vm.runInContext('answerWords', ctx)(ZERO, DAYS[2]), /class="live/);
  // The prerendered opening (scripts/prerender_spots.js) is the same function, so it leads the same way.
  const pre = spots.prerender({generated_at: GEN, spots: [ZERO]}, 'https://example.org/swim/').a;
  assert.ok(pre.indexOf('class="live live-off"') > 0 && pre.indexOf('class="live live-off"') < pre.indexOf('id="risk-headline"'));
});

test('a saved card: the live status over the level where nothing reports or right now is not known', () => {
  const ctx = page(), card = s => vm.runInContext('savedCard', ctx)(s);
  assert.match(card(ZERO), /<p class="place-live">Live sewage spill status unavailable<\/p><div class="place-mid"><p class="big low">Low risk<\/p>/);
  assert.match(card(THIN), /<p class="place-live">Live status from 1 of 13 overflows upstream<\/p><div class="place-mid">/);
  assert.doesNotMatch(card(MOST), /place-live/);
  assert.doesNotMatch(card(FULL), /place-live/);
});

test('the share picture draws the live status: first where nothing reports or right now is not known, after the level otherwise', () => {
  assert.match(PAGE, /lead = ans\.cardLive && !head\.startsWith\(ans\.cardLive\), live = ans\.live \? liveHead\(d\) : ''/);
  assert.match(PAGE, /if \(lead\) \{ g\.fillStyle = v\('--ink'\); g\.font = `700 40px \$\{F\}`; y = wrapText\(g, ans\.cardLive \+ \(ans\.blind \? '\. Modelled forecast:' : '\.'\)/);
  assert.match(PAGE, /if \(live && !lead && !head\.startsWith\(live\)\)/);
});
